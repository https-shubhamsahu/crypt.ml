from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import List

_PERSISTENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "chat_history"


@dataclass
class ChatMessage:
    role: str
    text: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            role=str(data.get("role", "assistant")),
            text=str(data.get("text", "")),
            created_at=str(data.get("created_at", "")),
        )


class ChatHistoryStore:
    """Thread-safe JSON-file-backed chat persistence per session."""

    def __init__(self, session_id: str = "default") -> None:
        self._lock = Lock()
        _PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _PERSISTENCE_DIR / f"{session_id}.json"
        self._messages: List[ChatMessage] = self._load()

    def _load(self) -> List[ChatMessage]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                return []
            return [ChatMessage.from_dict(item) for item in payload if isinstance(item, dict)]
        except (json.JSONDecodeError, OSError):
            return []

    def _persist(self) -> None:
        self._path.write_text(
            json.dumps([message.to_dict() for message in self._messages], indent=2),
            encoding="utf-8",
        )

    def add(self, role: str, text: str) -> None:
        clean_text = text.strip()
        if not clean_text:
            return
        with self._lock:
            self._messages.append(
                ChatMessage(
                    role=role,
                    text=clean_text,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            self._persist()

    def list(self, limit: int = 80) -> List[ChatMessage]:
        with self._lock:
            return list(self._messages[-limit:])

    def clear(self) -> int:
        with self._lock:
            removed = len(self._messages)
            self._messages.clear()
            self._persist()
            return removed
