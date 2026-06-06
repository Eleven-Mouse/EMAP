from schemas.memory import PreferenceHistoryItem, PreferenceItem, SessionSummaryItem


class MemoryService:
    def _get_memory_repository(self):
        from services.container import memory_repository

        return memory_repository

    def upsert_preference(
        self,
        user_id: str,
        key: str,
        value: str,
        changed_by: str = "api",
        change_reason: str = "upsert",
    ) -> None:
        self._get_memory_repository().upsert_preference(
            user_id=user_id,
            key=key,
            value=value,
            changed_by=changed_by,
            change_reason=change_reason,
        )

    def list_preferences(self, user_id: str) -> list[PreferenceItem]:
        prefs = self._get_memory_repository().get_preferences(user_id)
        return [
            PreferenceItem(user_id=user_id, key=key, value=value)
            for key, value in prefs.items()
        ]

    def delete_preference(
        self,
        user_id: str,
        key: str,
        changed_by: str = "api",
        change_reason: str = "delete",
    ) -> bool:
        return self._get_memory_repository().delete_preference(
            user_id=user_id,
            key=key,
            changed_by=changed_by,
            change_reason=change_reason,
        )

    def get_preference_history(self, user_id: str, key: str) -> list[PreferenceHistoryItem]:
        rows = self._get_memory_repository().get_preference_history(user_id=user_id, key=key)
        return [
            PreferenceHistoryItem(
                user_id=row[0],
                key=row[1],
                version=int(row[2]),
                change_type=row[3],
                old_value=row[4],
                new_value=row[5],
                changed_by=row[6],
                change_reason=row[7],
                changed_at=row[8],
            )
            for row in rows
        ]

    def rollback_preference(
        self,
        user_id: str,
        key: str,
        target_version: int | None = None,
        changed_by: str = "api",
        change_reason: str = "rollback",
    ) -> bool:
        return self._get_memory_repository().rollback_preference(
            user_id=user_id,
            key=key,
            target_version=target_version,
            changed_by=changed_by,
            change_reason=change_reason,
        )

    def append_session(self, session_id: str, message: str) -> None:
        self._get_memory_repository().append_session_message(session_id, message)

    def get_session(self, session_id: str) -> list[str]:
        return self._get_memory_repository().get_session_messages(session_id)

    def upsert_session_summary(
        self,
        user_id: str,
        session_id: str,
        summary_text: str,
        last_message_count: int,
    ) -> None:
        self._get_memory_repository().upsert_session_summary(
            user_id=user_id,
            session_id=session_id,
            summary_text=summary_text,
            last_message_count=last_message_count,
        )

    def list_session_summaries(self, user_id: str, limit: int = 3) -> list[SessionSummaryItem]:
        rows = self._get_memory_repository().list_session_summaries(
            user_id=user_id,
            limit=limit,
        )
        return [
            SessionSummaryItem(
                user_id=row[0],
                session_id=row[1],
                summary_text=row[2],
                last_message_count=int(row[3]),
                updated_at=row[4],
            )
            for row in rows
        ]

    def get_session_summary_checkpoint(self, session_id: str) -> int:
        return self._get_memory_repository().get_session_summary_checkpoint(session_id)
