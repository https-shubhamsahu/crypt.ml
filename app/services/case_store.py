from __future__ import annotations

from threading import Lock
from typing import Dict, Optional


class CaseStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cases: Dict[str, dict] = {}

    def put(self, case_id: str, data: dict) -> None:
        with self._lock:
            self._cases[case_id] = data

    def get(self, case_id: str) -> Optional[dict]:
        with self._lock:
            return self._cases.get(case_id)

    def update(self, case_id: str, fields: dict) -> Optional[dict]:
        with self._lock:
            existing = self._cases.get(case_id)
            if existing is None:
                return None
            existing.update(fields)
            return existing

    def list_recent(self, limit: int = 200) -> list[dict]:
        with self._lock:
            items = list(self._cases.items())[-limit:]

        records: list[dict] = []
        for case_id, payload in reversed(items):
            row = {"case_id": case_id}
            row.update(payload)
            records.append(row)
        return records
