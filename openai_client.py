import os
from openai import OpenAI
from dotenv import load_dotenv
import replicate
import asyncio
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
        response = client.videos.create(
            model="kwaivgI/kling-2.1-standard",
            prompt=prompt
        )
        # Retrieve the result (will wait until completed)
        video_response = client.videos.retrieve(response.id)
        # Attempt to extract URL from response
        if isinstance(video_response, dict):
            return video_response.get("video_url") or video_response.get("output_url") or next(iter(video_response.values()), None)
        # If response object has 'output' attribute
        return getattr(video_response, "output", video_response)
    return await asyncio.to_thread(run_video)
