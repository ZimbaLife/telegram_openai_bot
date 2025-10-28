import asyncio
import logging
from together import Together
import openai
import os

logger = logging.getLogger(__name__)

# Ключи из .env
openai.api_key = os.getenv("OPENAI_API_KEY")
client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# --- TEXT ---
async def generate_text(prompt: str):
    """Генерация текста через OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[Text] Error: {e}")
        return "Ошибка при генерации текста."


# --- IMAGE ---
async def generate_image(prompt: str):
    """Генерация изображения через OpenAI"""
    try:
        response = openai.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"[Image] Error: {e}")
        return None


# --- MiniMax VIDEO ---
async def generate_video_minimax(prompt: str):
    try:
        response = client.videos.create(
            model="minimax/minimax-01-director",
            prompt=prompt
        )
        video_id = response.id
        logger.info(f"[MiniMax] Started video id={video_id}")

        for _ in range(60):
            await asyncio.sleep(5)
            status = client.videos.retrieve(video_id)
            logger.info(f"[MiniMax] Status: {status.status}")
            if status.status == "succeeded":
                output = getattr(status, "output", [])
                if isinstance(output, list) and len(output) > 0:
                    url = getattr(output[0], "url", None)
                    if url:
                        return url
            if status.status == "failed":
                break
        return None
    except Exception as e:
        logger.error(f"[MiniMax] Error: {e}")
        return None


# --- Kling VIDEO ---
async def generate_video_kling(prompt: str):
    try:
        response = client.videos.create(
            model="kwaivgI/kling-1.6-standard",
            prompt=prompt
        )
        video_id = response.id
        logger.info(f"[Kling] Started video id={video_id}")

        for _ in range(60):
            await asyncio.sleep(5)
            status = client.videos.retrieve(video_id)
            logger.info(f"[Kling] Status: {status.status}")
            if status.status == "succeeded":
                output = getattr(status, "output", [])
                if isinstance(output, list) and len(output) > 0:
                    url = getattr(output[0], "url", None)
                    if url:
                        return url
            if status.status == "failed":
                break
        return None
    except Exception as e:
        logger.error(f"[Kling] Error: {e}")
        return None
