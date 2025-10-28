import os
from openai import OpenAI
from dotenv import load_dotenv
import replicate
import asyncio

# Load environment variables from .env file
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_text(prompt: str) -> str:
    """
    Generates a text response based on the given prompt using the GPT-4o-mini model.
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
    Generates a video URL from a description using Replicate Kling v1.6 Standard model.
    """
    def run_video():
        output = replicate.run(
            "kwaivgi/kling-v1.6-standard",
            input={"prompt": prompt}
        )
        return output[0] if isinstance(output, list) else output
    return await asyncio.to_thread(run_video)
