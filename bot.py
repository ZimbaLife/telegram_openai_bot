import os
import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, AIORateLimiter,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from openai_client import generate_text, generate_image, start_video_job, check_video_once

# ---------- базовая настройка ----------
load_dotenv()
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN/BOT_TOKEN is not set")

# До 5 видео одновременно на весь бот (подстрой под бюджет Together)
VIDEO_SEM = asyncio.Semaphore(5)
# Не больше одного видео одновременно от одного пользователя
USER_LOCKS = defaultdict(asyncio.Lock)


def build_app() -> Application:
    return (
        Application.builder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter())  # аккуратнее с лимитами Telegram
        .build()
    )


# ---------- утилиты для статуса ----------
def progress_text(prompt: str, started_at: datetime, win=(30, 50)) -> str:
    """
    Простой «сколько осталось»:
    считаем, что среднее время ~90 сек, показываем окно (30–50 сек), которое сдвигается к концу.
    """
    avg = 90
    elapsed = (datetime.utcnow() - started_at).total_seconds()
    remain = max(0, avg - int(elapsed))
    lo = max(0, min(win[0], remain))
    hi = max(lo, min(win[1], remain))
    short_prompt = (prompt[:100] + "…") if len(prompt) > 100 else prompt
    return (
        "🎬 Генерирую видео…\n"
        f"⏳ Осталось примерно {lo}–{hi} сек\n"
        f"📝 Запрос: {short_prompt}"
    )


# ---------- хэндлеры ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Я умею:\n"
        "/text ТВОЙ_ЗАПРОС — сгенерировать текст\n"
        "/image ОПИСАНИЕ — сгенерировать картинку\n"
        "/video ОПИСАНИЕ — сгенерировать видео\n"
        "\nПопробуй, например: /video котёнок бежит по траве на закате"
    )
    await update.message.reply_text(text)


async def cmd_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").replace("/text", "", 1).strip()
    if not prompt:
        await update.message.reply_text("Напиши после команды текст запроса. Пример: /text идеи для поста")
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
    # Берём весь текст после "/video"
    prompt = (update.message.text or "").replace("/video", "", 1).strip()
    if not prompt:
        await update.message.reply_text("Напиши описание видео. Пример: /video котёнок бежит по траве")
        return

    # ограничим слишком длинный текст
    if len(prompt) > 600:
        prompt = prompt[:600]

    user_id = update.effective_user.id
    started_at = datetime.utcnow()

    # мгновенный ответ + две кнопки
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏹ Отменить", callback_data="cancel:pending"),
        InlineKeyboardButton("ℹ️ Статус", callback_data="status:pending"),
    ]])
    msg = await update.message.reply_text(progress_text(prompt, started_at), reply_markup=kb)

    async def worker():
        async with USER_LOCKS[user_id]:   # один ролик на пользователя одновременно
            async with VIDEO_SEM:         # всего не более 5 параллельно
                # 1) запускаем задачу на Together
                job = await start_video_job(prompt)
                if not job:
                    await msg.edit_text("Не удалось запустить генерацию (ключ/квоты/доступ).")
                    return

                # подменим кнопки на рабочие (зная job.id)
                kb2 = InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏹ Отменить", callback_data=f"cancel:{job.id}"),
                    InlineKeyboardButton("ℹ️ Статус", callback_data=f"status:{job.id}"),
                ]])
                try:
                    await msg.edit_text(progress_text(prompt, started_at), reply_markup=kb2)
                except Exception:
                    pass

                # 2) опрос статуса и обновление текста
                backoff = [5, 8, 13, 13, 13]  # шаги ожидания (сек)
                i = 0
                # флаг отмены в памяти чата
                context.chat_data.setdefault("cancel_flags", {})
                context.chat_data["cancel_flags"][job.id] = False

                while True:
                    # отмена?
                    if context.chat_data["cancel_flags"].get(job.id):
                        await msg.edit_text("Генерация остановлена по запросу пользователя.")
                        break

                    status, url, info = await check_video_once(job.id)
                    if status == "completed" and url:
                        LOG.info("✅ Video ready: %s", url)
                        # удалим статус и пришлём результат
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                        try:
                            await update.message.reply_video(video=url, caption="Готово! 🎉")
                        except Exception:
                            await update.message.reply_text(f"Готово! Ссылка: {url}")
                        break

                    if status in ("failed", "cancelled"):
                        await msg.edit_text(f"Не удалось сгенерировать видео. Детали: {info or 'нет'}")
                        break

                    # обновим «осталось примерно …»
                    try:
                        await msg.edit_text(progress_text(prompt, started_at), reply_markup=kb2)
                    except Exception:
                        pass

                    await asyncio.sleep(backoff[min(i, len(backoff)-1)])
                    i += 1

                context.chat_data["cancel_flags"].pop(job.id, None)

    # запускаем «в фоне», чтобы чат не зависал
    context.application.create_task(worker())


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        action, job_id = query.data.split(":", 1)
    except Exception:
        return

    if action == "cancel" and job_id != "pending":
        context.chat_data.setdefault("cancel_flags", {})
        context.chat_data["cancel_flags"][job_id] = True
        await query.edit_message_text("Останавливаю генерацию…")

    elif action == "status" and job_id != "pending":
        status, url, info = await check_video_once(job_id)
        txt = f"Статус: {status}"
        if info:
            txt += f"\nДетали: {info}"
        if status == "completed" and url:
            txt += f"\nСсылка: {url}"
        await query.edit_message_text(txt)


def main():
    app = build_app()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("text", cmd_text))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("video", cmd_video))
    app.add_handler(CallbackQueryHandler(on_callback))

    # Режим: polling (простой и надёжный)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

