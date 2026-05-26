from schemas.memory import PreferenceItem


class MemoryService:
    def _get_memory_repository(self):
        from services.container import memory_repository

        return memory_repository

    def upsert_preference(self, user_id: str, key: str, value: str) -> None:
        self._get_memory_repository().upsert_preference(user_id, key, value)

    def list_preferences(self, user_id: str) -> list[PreferenceItem]:
        prefs = self._get_memory_repository().get_preferences(user_id)
        return [
            PreferenceItem(user_id=user_id, key=key, value=value)
            for key, value in prefs.items()
        ]

    def append_session(self, session_id: str, message: str) -> None:
        self._get_memory_repository().append_session_message(session_id, message)

    def get_session(self, session_id: str) -> list[str]:
        return self._get_memory_repository().get_session_messages(session_id)
