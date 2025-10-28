import os
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, UTC

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, AIORateLimiter,
    CommandHandler, ContextTypes,
)

from openai_client import (
    generate_text,
    generate_image,
    generate_video_minimax,
    generate_video_kling,
)

# ---------- базовая настройка ----------
load_dotenv()
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN/BOT_TOKEN is not set")

VIDEO_SEM = asyncio.Semaphore(5)
USER_LOCKS = defaultdict(asyncio.Lock)


def build_app() -> Application:
    return (
        Application.builder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter())  # работает при наличии python-telegram-bot[rate-limiter]
        .build()
    )


# ---------- вспомогательные функции ----------
def now_utc():
    return datetime.now(UTC)

def progress_text(prompt: str, started_at: datetime, avg_sec: int = 90) -> str:
    elapsed = int((now_utc() - started_at).total_seconds())
    remain = max(0, avg_sec - elapsed)
    short_prompt = (prompt[:100] + "…") if len(prompt) > 100 else prompt
    return (
        "🎬 Генерирую видео…\n"
        f"⏳ Осталось примерно {remain} сек\n"
        f"📝 {short_prompt}"
    )


# ---------- команды ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я умею:\n"
        "/text <запрос> — сгенерировать текст\n"
        "/image <описание> — сгенерировать картинку\n"
        "/video [minimax|kling] <описание> — сгенерировать видео\n\n"
        "Примеры:\n"
        "/video minimax котёнок бежит по траве\n"
        "/video kling девушка идёт по пляжу на закате"
    )


async def cmd_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").replace("/text", "", 1).strip()
    if not prompt:
        await update.message.reply_text("Напиши текст после команды. Пример: /text идея для поста")
        return
    try:
        reply = await generate_text(prompt)
        await update.message.reply_text(reply)
    except Exception as e:
        LOG.exception("text error: %r", e)
        await update.message.reply_text("Не удалось сгенерировать текст. Попробуй позже.")


async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").replace("/image", "", 1).strip()
    if not prompt:
        await update.message.reply_text("Напиши описание картинки. Пример: /image рыжий кот в очках")
        return
    try:
        url = await generate_image(prompt)
        await update.message.reply_photo(photo=url, caption="Готово!")
    except Exception as e:
        LOG.exception("image error: %r", e)
        await update.message.reply_text("Не удалось сгенерировать изображение. Попробуй позже.")


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").replace("/video", "", 1).strip()
    if not text:
        await update.message.reply_text(
            "Напиши описание видео. Пример: /video minimax котёнок бежит по траве"
        )
        return

    parts = text.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() in ("minimax", "kling"):
        model = parts[0].lower()
        prompt = parts[1]
    else:
        model = "minimax"
        prompt = text

    if len(prompt) > 600:
        prompt = prompt[:600]

    user_id = update.effective_user.id
    started_at = now_utc()

    # первый статус
    last_shown = None
    status_text = progress_text(prompt, started_at)
    msg = await update.message.reply_text(status_text)
    last_shown = status_text

    async def worker():
        nonlocal last_shown
        async with USER_LOCKS[user_id]:
            async with VIDEO_SEM:
                video_func = generate_video_minimax if model == "minimax" else generate_video_kling

                # мягкий тайм-аут на фоне (видео может рендериться долго из-за очереди)
                refresh_every = 10
                max_wait = 900  # 15 минут максимум
                elapsed = 0
                url = None

                while elapsed < max_wait:
                    try:
                        url = await video_func(prompt)
                        if url:
                            break
                        # если URL ещё нет — подождём и обновим статус
                        await asyncio.sleep(refresh_every)
                        elapsed += refresh_every
                        new_text = progress_text(prompt, started_at, avg_sec=120)
                        # не шлём одинаковый текст, чтобы избежать 400 "Message is not modified"
                        if new_text != last_shown:
                            try:
                                await msg.edit_text(new_text)
                                last_shown = new_text
                            except Exception as e:
                                LOG.warning(f"edit_text warning: {e}")
                    except Exception as e:
                        LOG.error(f"Video generation error: {e}")
                        break

                if url:
                    # удалим статус и пришлём видео
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    try:
                        await update.message.reply_video(video=url, caption="Готово! 🎉")
                    except Exception:
                        await update.message.reply_text(f"Готово! Ссылка: {url}")
                else:
                    try:
                        await msg.edit_text("⚠️ Не удалось сгенерировать видео. Попробуй позже.")
                    except Exception:
                        await update.message.reply_text("⚠️ Не удалось сгенерировать видео. Попробуй позже.")

    context.application.create_task(worker())


def main():
    app = build_app()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("text", cmd_text))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("video", cmd_video))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
