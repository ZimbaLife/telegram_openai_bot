import os
import asyncio
import logging
from typing import Optional, Any
from together import Together
from openai import OpenAI

logger = logging.getLogger("openai_client")

# --- Keys ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Clients ---
together = Together(api_key=TOGETHER_API_KEY) if TOGETHER_API_KEY else Together()
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else OpenAI()

# ========= TEXT =========
async def generate_text(prompt: str) -> str:
    """Simple text generation using OpenAI gpt-4o-mini."""
    def _sync_call() -> str:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    return await asyncio.to_thread(_sync_call)

# ========= IMAGES =========
async def generate_image(prompt: str) -> str:
    """Generate image via OpenAI Images API. Return URL."""
    def _sync_call() -> str:
        resp = openai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        return resp.data[0].url
    return await asyncio.to_thread(_sync_call)

# ========= VIDEO Utility =========
async def _poll_together_video(video_id: str, timeout_sec: int = 600, poll_every: int = 5) -> Optional[str]:
    """Wait for video completion on Together and return URL."""
    waited = 0
    last_status = None
    while waited < timeout_sec:
        await asyncio.sleep(poll_every)
        try:
            status_obj = together.videos.retrieve(video_id)
        except Exception as e:
            logger.error(f"[Together] retrieve error: {e}")
            return None
        status = getattr(status_obj, "status", None) or getattr(status_obj, "state", None)
        if status != last_status:
            logger.info(f"[Together] Status: {status}")
            last_status = status
        if status in ("completed", "succeeded", "success", "done", "finished"):
            url = _extract_video_url(status_obj)
            if not url:
                logger.warning("[Together] completed, but URL not found in response")
            return url
        if status in ("failed", "error", "cancelled", "canceled"):
            logger.error(f"[Together] job finished with status: {status}")
            return None
        waited += poll_every
    logger.error("[Together] Timeout waiting video")
    return None

def _extract_video_url(resp: Any) -> Optional[str]:
    """Extract video URL from various response formats."""
    try:
        output = getattr(resp, "output", None)
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    if "url" in item and isinstance(item["url"], str):
                        return item["url"]
                    if "video" in item and isinstance(item["video"], dict) and "url" in item["video"]:
                        return item["video"]["url"]
                else:
                    maybe_url = getattr(item, "url", None)
                    if isinstance(maybe_url, str):
                        return maybe_url
        if isinstance(output, dict):
            if "url" in output and isinstance(output["url"], str):
                return output["url"]
            if "video" in output and isinstance(output["video"], dict) and "url" in output["video"]:
                return output["video"]["url"]
        assets = getattr(resp, "assets", None)
        if isinstance(assets, dict):
            if "video" in assets and isinstance(assets["video"], str) and assets["video"].startswith("http"):
                return assets["video"]
        result = getattr(resp, "result", None)
        if isinstance(result, dict) and "url" in result and isinstance(result["url"], str):
            return result["url"]
    except Exception as e:
        logger.error(f"[Together] URL parse error: {e}")
    return None

# ========= VIDEO: MiniMax =========
async def generate_video_minimax(prompt: str) -> Optional[str]:
    """Together MiniMax 01 Director — low-cost model."""
    try:
        create = together.videos.create(
            model="minimax/minimax-01-director",
            prompt=prompt,
        )
        video_id = create.id
        logger.info(f"[MiniMax] Started video id={video_id}")
        return await _poll_together_video(video_id, timeout_sec=600, poll_every=5)
    except Exception as e:
        logger.error(f"[MiniMax] create error: {e}")
        return None

# ========= VIDEO: Kling =========
async def generate_video_kling(prompt: str) -> Optional[str]:
    """Together Kling 1.6 Standard."""
    try:
        create = together.videos.create(
            model="kwaivgI/kling-1.6-standard",
            prompt=prompt,
        )
        video_id = create.id
        logger.info(f"[Kling] Started video id={video_id}")
        return await _poll_together_video(video_id, timeout_sec=900, poll_every=5)
    except Exception as e:
        logger.error(f"[Kling] create error: {e}")
        return None
