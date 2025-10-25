import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import Conflict
from dotenv import load_dotenv

from openai_client import generate_text, generate_image, generate_video


# Load environment variables from .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


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
    keyboard = [
        ["📝 Сгенерировать текст", "🎨 Создать изображение", "🎬 Создать видео"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот с AI.\nВыберите действие:",
        reply_markup=reply_markup,
    )
    context.user_data["awaiting"] = None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses and subsequent prompts."""
    text = update.message.text
    awaiting = context.user_data.get("awaiting")

    # Determine which action the user selected
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

    # Handle the awaiting state
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

    # Default message if no known command is selected
    await update.message.reply_text("Выберите действие, используя кнопки.")


def main() -> None:
    """Run the Telegram bot and simple HTTP server."""
    # Start simple HTTP server in a background thread to satisfy Render port check
    threading.Thread(target=run_server, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    try:
        application.run_polling()
    except Conflict:
        # Avoid multiple long-polling instances if Render spawns parallel containers
        print("Another instance is running; exiting to avoid conflict.")


if __name__ == "__main__":
    main()
