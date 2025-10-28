import asyncio
import logging
from together import Together

logger = logging.getLogger(__name__)

client = Together()

# --- MiniMax model ---
async def generate_video_minimax(prompt: str):
    try:
        response = client.videos.create(
            model="minimax/minimax-01-director",
            prompt=prompt
        )
        video_id = response.id
        logger.info(f"[MiniMax] Started video id={video_id}")
        # ждем пока готово
        for _ in range(60):
            await asyncio.sleep(5)
            status = client.videos.retrieve(video_id)
            logger.info(f"[MiniMax] Status: {status.status}")
            if status.status == "succeeded":
                return status.output[0].url
            if status.status == "failed":
                break
        return None
    except Exception as e:
        logger.error(f"[MiniMax] Error: {e}")
        return None


# --- Kling model ---
async def generate_video_kling(prompt: str):
    try:
        response = client.videos.create(
            model="kwaivgI/kling-1.6-standard",
            prompt=prompt
        )
        video_id = response.id
        logger.info(f"[Kling] Started video id={video_id}")
        # ждем пока готово
        for _ in range(60):
            await asyncio.sleep(5)
            status = client.videos.retrieve(video_id)
            logger.info(f"[Kling] Status: {status.status}")
            if status.status == "succeeded":
                return status.output[0].url
            if status.status == "failed":
                break
        return None
    except Exception as e:
        logger.error(f"[Kling] Error: {e}")
        return None
