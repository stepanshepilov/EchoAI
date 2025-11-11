import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseRepository(ABC):
    @abstractmethod
    def start_new_session(self, user_id: int) -> str:
        pass

    @abstractmethod
    def add_message(self, session_id: str, role: str, content: str):
        pass

    @abstractmethod
    def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        pass

    @abstractmethod
    def save_analysis(self, session_id: str, analysis_data: Dict[str, Any]):
        pass
    
    @abstractmethod
    def get_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        pass

class InMemoryRepository(BaseRepository):
    def __init__(self):
        # 'conversations': { "session_id_1": [{"role": "user", "content": "..."}, ...], ... }
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        # 'analyses': { "session_id_1": {"sentiment": 0.5, "topics": [...]}, ... }
        self._analyses: Dict[str, Dict[str, Any]] = {}
        # 'sessions': { "session_id_1": {"user_id": 101}, ... }
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def start_new_session(self, user_id: int) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {"user_id": user_id}
        self._conversations[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        if session_id in self._conversations:
            self._conversations[session_id].append({"role": role, "content": content})
        else:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Попытка добавить сообщение в несуществующую сессию {session_id}")

    def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        return self._conversations.get(session_id)

    def save_analysis(self, session_id: str, analysis_data: Dict[str, Any]):
        self._analyses[session_id] = analysis_data

    def get_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._analyses.get(session_id)

db_repository: BaseRepository = InMemoryRepository()
