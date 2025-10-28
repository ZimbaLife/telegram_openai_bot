import os
import asyncio
import time
from dotenv import load_dotenv
from together import Together
import replicate
from openai import OpenAI

# Загружаем .env
load_dotenv()

# Инициализация клиентов
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
together_client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# ==== ТЕКСТ ====
async def generate_text(prompt: str) -> str:
    """
    Генерация текста через OpenAI (GPT-4o-mini)
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


# ==== ИЗОБРАЖЕНИЯ ====
async def generate_image(prompt: str) -> str:
    """
    Генерация изображения через Replicate (Ideogram v3 Turbo)
    """
    def run_model():
        output = replicate.run(
            "ideogram-ai/ideogram-v3-turbo",
            input={"prompt": prompt}
        )
        return output[0]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_model)


# ==== ВИДЕО ====
async def generate_video(prompt: str) -> str | None:
    """
    Генерация видео через Together AI (MiniMax 01 Director)
    Возвращает URL готового видео или None при ошибке
    """
    job = together_client.videos.create(
        prompt=prompt,
        model="minimax/video-01-director",
        width=1280,     # стандартное 720p
        height=720
    )

    # Проверяем статус каждые 5 секунд
    while True:
        status = together_client.videos.retrieve(job.id)
        if status.status == "completed":
            video_url = getattr(status.outputs, "video_url", None)
            if not video_url:
                # На случай, если API вернёт список или другое поле
                video_url = getattr(status.outputs, "output_url", None) or getattr(status.outputs, "output", None)
            if isinstance(video_url, list):
                return video_url[0]
            return video_url

        elif status.status in ("failed", "cancelled"):
            return None

        time.sleep(5)


