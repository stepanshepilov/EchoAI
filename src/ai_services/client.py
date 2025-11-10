from openai import OpenAI
from ..settings import settings

# Здесь на месте увидим, где будет LLM, там и напишем актуальный файл

def get_client():
    client = ChatOpenAI(
        api_key=settings.api_key,
        temperature=0,
        base_url=settings.base_url,
        model_name=settings.model_name
    )
    return client

def get_openai_client():
    client = OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url
    )
    return client

if __name__ == "__main__":
    client = get_openai_client()

    response = client.chat.completions.create(
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
