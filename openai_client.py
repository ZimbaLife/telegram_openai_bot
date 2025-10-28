import os
import asyncio
import logging
from typing import Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from together import Together

# ---------- базовая настройка ----------
load_dotenv()
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("openai_client")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
together_client = Together(api_key=TOGETHER_API_KEY) if TOGETHER_API_KEY else None


# ---------- ТЕКСТ ----------
async def generate_text(prompt: str) -> str:
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


# ---------- КАРТИНКИ ----------
async def generate_image(prompt: str) -> str:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not set")

    def _call():
        resp = openai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        return resp.data[0].url

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)


# ---------- ВИДЕО (Together MiniMax 01 Director) ----------
def _extract_url(outputs) -> Optional[str]:
    # В разных моделях поле с готовой ссылкой может называться по-разному
    for key in ("video_url", "output_url", "output"):
        url = getattr(outputs, key, None)
        if isinstance(url, list):
            return url[0] if url else None
        if url:
            return url
    return None

async def start_video_job(prompt: str):
    """Стартуем генерацию видео. Возвращаем объект с job.id (или None при ошибке)."""
    if not together_client:
        LOG.error("TOGETHER_API_KEY is not set")
        return None

    loop = asyncio.get_event_loop()
    try:
        job = await loop.run_in_executor(
            None,
            lambda: together_client.videos.create(
                prompt=prompt,
                model="minimax/video-01-director",
                width=1366,
                height=768,
            )
        )
        LOG.info("Created video job id=%s", getattr(job, "id", None))
        return job
    except Exception as e:
        LOG.exception("start_video_job exception: %r", e)
        return None

async def check_video_once(job_id: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Разовая проверка статуса по job_id.
    Возвращаем кортеж: (статус, ссылка_на_видео_или_None, текст_ошибки_или_None)
    Возможные статусы: in_progress | completed | failed | cancelled | unknown
    """
    if not together_client:
        return ("failed", None, "TOGETHER_API_KEY is not set")

    loop = asyncio.get_event_loop()
    try:
        status = await loop.run_in_executor(None, lambda: together_client.videos.retrieve(job_id))
        st = getattr(status, "status", "unknown")
        info = getattr(getattr(status, "info", None), "errors", None)
        url = _extract_url(getattr(status, "outputs", None)) if st == "completed" else None
        LOG.info("Video status: id=%s status=%s errors=%s", job_id, st, info)
        return (st, url, str(info) if info else None)
    except Exception as e:
        LOG.exception("check_video_once exception: %r", e)
        return ("failed", None, f"exception: {e}")


__all__ = ["generate_text", "generate_image", "start_video_job", "check_video_once"]
