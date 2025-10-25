import os
from openai import OpenAI
from dotenv import load_dotenv
import replicate
import asyncio
import time
from together import Together

# Load environment variables from .env file
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_text(prompt: str) -> str:
    """
    Generates a text response based on the given prompt using the GPT‑4o‑mini model.
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

async def generate_image(prompt: str) -> str:
    """
    Generates an image (URL) from a description using a Replicate model.
    """
    def run_model():
        output = replicate.run(
            "ideogram-ai/ideogram-v3-turbo",
            input={"prompt": prompt}
        )
        return output[0] if isinstance(output, list) else output
    return await asyncio.to_thread(run_model)

async def generate_video(prompt: str) -> str:
    """
    Generates a video URL from a description using Together AI Kling 2.1 Standard model.
    """
    def run_video():
        client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
        # Create a new video job
        job = client.videos.create(
            model="kwaivgI/kling-2.1-standard",
            prompt=prompt
        )
        # Poll the job until it's completed
        while True:
            result = client.videos.retrieve(job.id)
            # Determine status
            status = None
            if isinstance(result, dict):
                status = result.get("status")
            else:
                status = getattr(result, "status", None)
            if status in ("succeeded", "completed", "completed_successfully"):
                # Extract video URL
                if isinstance(result, dict):
                    video_url = result.get("video_url") or result.get("output_url")
                    if not video_url:
                        output = result.get("output")
                        if isinstance(output, list):
                            video_url = output[0]
                        else:
                            video_url = output
                    return video_url
                else:
                    return getattr(result, "video_url", None) or getattr(result, "output_url", None) or getattr(result, "output", None)
            if status in ("failed", "error"):
                return None
            # Sleep before next poll
            time.sleep(1)
    return await asyncio.to_thread(run_video)
