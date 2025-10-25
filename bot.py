import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from openai_client import generate_text, generate_image

# Load environment variables from .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Приветствие и вывод меню с кнопками.
    """
    keyboard = [["📝 Сгенерировать текст", "🎨 Создать изображение"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот с AI.\n"
        "Выберите действие:", reply_markup=reply_markup
    )
    # Сброс состояния ожидания
    context.user_data["awaiting"] = None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатия на кнопки и последующие запросы.
    """
    text = update.message.text
    awaiting = context.user_data.get("awaiting")
    if text == "📝 Сгенерировать текст":
        await update.message.reply_text("Введите запрос для генерации текста:")
        context.user_data["awaiting"] = "text"
    elif text == "🎨 Создать изображение":
        await update.message.reply_text("Опишите картинку, которую хотите получить:")
        context.user_data["awaiting"] = "image"
    else:
        if awaiting == "text":
            if not text.strip():
                await update.message.reply_text("❗ Напиши запрос для генерации текста.")
                return
            await update.message.reply_text("Генерирую ответ... ⏳")
            result = await generate_text(text)
            await update.message.reply_text(result)
            context.user_data["awaiting"] = None
        elif awaiting == "image":
            if not text.strip():
                await update.message.reply_text("❗ Напиши описание для изображения.")
                return
            await update.message.reply_text("Создаю изображение... 🎨")
            image_url = await generate_image(text)
            await update.message.reply_photo(image_url)
            context.user_data["awaiting"] = None
        else:
            await update.message.reply_text("Пожалуйста, выберите действие из меню.")

def main():
    """
    Создаёт и запускает бота в режиме long polling.
    """
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
