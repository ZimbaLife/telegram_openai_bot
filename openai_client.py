import os
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_text(prompt: str) -> str:
    """
    Генерирует текстовый ответ на основе переданной строки prompt
    с использованием модели gpt‑4o‑mini.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

async def generate_image(prompt: str) -> str:
    """
    Генерирует изображение (URL) по описанию prompt
    с использованием OpenAI image API.
    """
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024"
    )
    return result.data[0].url
