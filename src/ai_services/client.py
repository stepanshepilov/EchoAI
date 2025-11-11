import openai
import asyncio
from ..settings import settings

def get_openai_client():
    client = openai.AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.DEEPSEEK_API_BASE
    )

    return client

async def main():
    client = get_openai_client()

    response = await client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {
                "role": "user",
                "content": "Привет, как дела?",
            },
        ],
        temperature=1
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())