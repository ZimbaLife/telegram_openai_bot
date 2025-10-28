import os
import time
import logging
import asyncio
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from together import Together

# -------- Base setup --------
load_dotenv()
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("openai_client")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
together_client = Together(api_key=TOGETHER_API_KEY) if TOGETHER_API_KEY else None

# -------- TEXT --------
async def generate_text(prompt: str) -> str:
    """
    Генерация текста через OpenAI (GPT-4o-mini).
    Возвращает строку ответа.
    """
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not set")

    def _call():
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

# -------- IMAGE --------
async def generate_image(prompt: str) -> str:
    """
    Генерация изображения через OpenAI Images API.
    Возвращает URL сгенерированного изображения.
    """
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not set")

    def _call():
        # Можно заменить на другую модель, если используете иную
        resp = openai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        # API возвращает list; берём первый элемент
        return resp.data[0].url

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)

# -------- VIDEO (Together MiniMax 01 Director) --------
def _extract_video_url(outputs) -> Optional[str]:
    # разные модели возвращают video_url / output_url / output (иногда list)
    for key in ("video_url", "output_url", "output"):
        url = getattr(outputs, key, None)
        if isinstance(url, list):
            return url[0] if url else None
        if url:
            return url
    return None

async def generate_video(prompt: str) -> Optional[str]:
    """
    Генерация видео через Together AI (MiniMax 01 Director).
    Возвращает URL видео или None при ошибке.
    """
    if not together_client:
        LOG.error("TOGETHER_API_KEY is not set")
        return None

    try:
        # Значения из официальных примеров Together
        job = together_client.videos.create(
            prompt=prompt,
            model="minimax/video-01-director",
            width=1366,
            height=768,
        )
        LOG.info("Together video job created: id=%s", getattr(job, "id", None))

        # Опрос статуса
        while True:
            status = together_client.videos.retrieve(job.id)
            LOG.info(
                "Video status: id=%s status=%s errors=%s",
                getattr(status, "id", None),
                getattr(status, "status", None),
                getattr(getattr(status, "info", None), "errors", None),
            )

            if status.status == "completed":
                url = _extract_video_url(status.outputs)
                if not url:
                    LOG.error("Completed but no URL in outputs: %s", status.outputs)
                return url

            if status.status in ("failed", "cancelled"):
                LOG.error("Video generation failed. info=%s inputs=%s", status.info, status.inputs)
                return None

            time.sleep(5)

    except Exception as e:
        # тут увидим 401/403/402(insufficient_quota)/404(model) и т.п.
        LOG.exception("Together video exception: %r", e)
        return None

__all__ = ["generate_text", "generate_image", "generate_video"]
