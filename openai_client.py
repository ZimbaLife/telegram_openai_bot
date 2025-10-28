import os
import time
import logging
from together import Together

LOG = logging.getLogger("video")
together_client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

def _require_together_key():
    if not os.getenv("TOGETHER_API_KEY"):
        raise RuntimeError("TOGETHER_API_KEY is not set in environment")

def _extract_video_url(outputs):
    # вместе с video_url могут приходить output_url / output (иногда как список)
    for key in ("video_url", "output_url", "output"):
        url = getattr(outputs, key, None)
        if isinstance(url, list):
            return url[0] if url else None
        if url:
            return url
    return None

async def generate_video(prompt: str) -> str | None:
    """
    Генерация видео через Together AI (MiniMax 01 Director).
    Возвращает URL видео или None при ошибке.
    """
    try:
        _require_together_key()

        # Ровно как в доках Together: 1366x768
        job = together_client.videos.create(
            prompt=prompt,
            model="minimax/video-01-director",
            width=1366,
            height=768,
        )
        LOG.info("Together video job created: id=%s model=%s", getattr(job, "id", None), "minimax/video-01-director")

        # Пуллим статус
        while True:
            status = together_client.videos.retrieve(job.id)
            LOG.info("Video status: id=%s status=%s errors=%s", status.id, status.status, getattr(status.info, "errors", None))

            if status.status == "completed":
                url = _extract_video_url(status.outputs)
                if not url:
                    LOG.error("Completed but no URL in outputs: %s", status.outputs)
                return url

            if status.status in ("failed", "cancelled"):
                # Вытащим причину и залогируем
                LOG.error("Video generation failed: info=%s inputs=%s", status.info, status.inputs)
                return None

            time.sleep(5)

    except Exception as e:
        # Логируем исключение от SDK (например 401/403/404/429/402 No quota)
        LOG.exception("Together video exception: %r", e)
        return None
