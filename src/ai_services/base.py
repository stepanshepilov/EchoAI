from ..settings import settings
from typing import List, Dict
from .client import get_openai_client
from .prompts.bot_prompts import BURNOUT_DIAGNOSTIC_SYSTEM_PROMPT

class BaseLM:
    def __init__(self):
        self.client = get_openai_client()
    
    def build_messages(self, user_request: str, SYSTEM_PROMPT: str, USER_PROMPT: str) -> List[dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(user_request=user_request),
            },
        ]
    
    def answer(self, user_message: str, SYSTEM_PROMPT: str, USER_PROMPT: str, temp=0.6) -> str:
            messages = self.build_messages(user_message, SYSTEM_PROMPT, USER_PROMPT)

            response = self.client.chat.completions.create(
                model=settings.model_name,
                messages=messages,
                temperature=temp
            )

            return response.choices[0].message.content

    async def chat_completion(self, messages: list[dict], temperature: float = 0.7) -> str:
            response = await self.client.chat.completions.create(
                model=settings.model_name,
                messages=messages,
                temperature=temperature
            )

            return response.choices[0].message.content


class ChatLM(BaseLM):
    def __init__(self, system_prompt: str = BURNOUT_DIAGNOSTIC_SYSTEM_PROMPT, context_length: int = 10):
        super().__init__()
        self.system_prompt = system_prompt
        self.context_length = context_length
    
    async def get_response(self, conversation_history: List[Dict]) -> str:
        trimmed_history = conversation_history[-self.context_length:]
        
        messages_for_api = [
            {"role": "system", "content": self.system_prompt},
            *trimmed_history
        ]
        
        ai_response = await self.chat_completion(
            messages=messages_for_api
        )
        
        return ai_response
