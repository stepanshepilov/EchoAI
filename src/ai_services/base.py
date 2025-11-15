from ..settings import settings
from typing import List, Dict
from .client import get_openai_client
from .prompts.bot_prompts import BURNOUT_DIAGNOSTIC_SYSTEM_PROMPT
from .prompts.test_analyzer_prompt import SYSTEM_PROMPT_TEST, USER_PROMPT_TEST

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


class TestAnalzyer(BaseLM):
    def __init__(self):
        super().__init__()
        self.system_prompt = SYSTEM_PROMPT_TEST
        self.user_prompt = USER_PROMPT_TEST
    
    async def analyze(self, test_results: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(test_result=test_results)}
        ]

        return await super().chat_completion(messages=messages, temperature=0)
