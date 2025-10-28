import os
import logging
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

from openai_client import generate_text, generate_image, generate_video

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
BOT_MODE = os.getenv("BOT_MODE", "polling")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server() -> None:
    """Start a minimal HTTP server so Render sees an open port."""
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send greeting and show the reply keyboard."""
    keyboard = [["📝 Сгенерировать текст", "🎨 Создать изображение", "🎬 Создать видео"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Я бот с AI.\nВыберите действие:", reply_markup=reply_markup)
    context.user_data["awaiting"] = None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses and subsequent prompts."""
    text = update.message.text
    awaiting = context.user_data.get("awaiting")

    if text == "📝 Сгенерировать текст":
        await update.message.reply_text("Введите запрос для генерации текста:")
        context.user_data["awaiting"] = "text"
        return
    if text == "🎨 Создать изображение":
        await update.message.reply_text("Введите запрос для генерации изображения:")
        context.user_data["awaiting"] = "image"
        return
    if text == "🎬 Создать видео":
        await update.message.reply_text("Введите запрос для генерации видео:")
        context.user_data["awaiting"] = "video"
        return

    if awaiting == "text":
        prompt = text.strip()
        if not prompt:
            await update.message.reply_text("Введите корректный запрос для генерации текста.")
            return
        try:
            response = await generate_text(prompt)
            await update.message.reply_text(response)
        except Exception:
            await update.message.reply_text("Произошла ошибка при генерации текста. Попробуйте позже.")
        finally:
            context.user_data["awaiting"] = None
        return

    if awaiting == "image":
        prompt = text.strip()
        if not prompt:
            await update.message.reply_text("Введите корректный запрос для генерации изображения.")
            return
        try:
            image_url = await generate_image(prompt)
            await update.message.reply_photo(photo=image_url)
        except Exception:
            await update.message.reply_text("Произошла ошибка при генерации изображения. Попробуйте позже.")
        finally:
            context.user_data["awaiting"] = None
        return

    if awaiting == "video":
        prompt = text.strip()
        if not prompt:
            await update.message.reply_text("Введите корректный запрос для генерации видео.")
            return
        try:
            video_url = await generate_video(prompt)
            await update.message.reply_video(video=video_url)
        except Exception:
            await update.message.reply_text("Произошла ошибка при генерации видео. Попробуйте позже.")
        finally:
            context.user_data["awaiting"] = None
        return

    await update.message.reply_text("Выберите действие, используя кнопки.")

def build_application() -> Application:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application

def main() -> None:
    """Run the Telegram bot in polling or webhook mode depending on BOT_MODE."""
    # Start simple HTTP server in a background thread to satisfy Render port check
    threading.Thread(target=run_server, daemon=True).start()

    app = build_application()
    mode = BOT_MODE.lower()

    if mode == "webhook":
        # Webhook mode requires WEBHOOK_BASE_URL to be set
        port = int(os.environ.get("PORT", "10000"))
        if not WEBHOOK_BASE_URL:
            raise ValueError("WEBHOOK_BASE_URL must be set in webhook mode")
        url_path = BOT_TOKEN  # use token as secret path
        webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/{url_path}"
        app.run_webhook(listen="0.0.0.0", port=port, url_path=url_path, webhook_url=webhook_url, drop_pending_updates=True)
    else:
        # Default polling mode
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
