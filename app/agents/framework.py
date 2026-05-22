from __future__ import annotations
import uuid
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, List, Any, Callable, Awaitable

@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receiver: str = "broadcast"
    msg_type: str = "request"  # request, response, alert, escalation
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class AgentResult:
    agent_name: str
    score: float  # 0-100
    confidence: float  # 0-1
    decision: str  # BLOCK, ESCALATE, REVIEW, ALLOW
    reasoning: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class ToolRegistry:
    """Registry to manage and execute agent tools."""
    def __init__(self) -> None:
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, func: Callable[..., Any], description: str) -> None:
        self.tools[name] = {
            "func": func,
            "description": description
        }

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        func = self.tools[name]["func"]
        return func(*args, **kwargs)

    async def invoke_async(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        func = self.tools[name]["func"]
        import inspect
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    def list_tools(self) -> List[Dict[str, str]]:
        return [{"name": k, "description": v["description"]} for k, v in self.tools.items()]

class AgentMemory:
    """Simple in-memory and persistent representation of agent decisions and observations."""
    def __init__(self) -> None:
        self.history: List[Dict[str, Any]] = []

    def store(self, item: Dict[str, Any]) -> None:
        item["timestamp"] = item.get("timestamp", datetime.now(UTC).isoformat())
        self.history.append(item)

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.history[-limit:]

    def clear(self) -> None:
        self.history.clear()

class EventBus:
    """Publisher-Subscriber messaging bus for agents."""
    def __init__(self) -> None:
        self.subscribers: Dict[str, List[Callable[[AgentMessage], Awaitable[None]]]] = {}
        self.all_messages: List[AgentMessage] = []

    def subscribe(self, agent_name: str, handler: Callable[[AgentMessage], Awaitable[None]]) -> None:
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        self.subscribers[agent_name].append(handler)

    async def publish(self, message: AgentMessage) -> None:
        self.all_messages.append(message)
        receiver = message.receiver
        
        # Determine target handlers
        handlers = []
        if receiver == "broadcast" or receiver == "*":
            for sub_handlers in self.subscribers.values():
                handlers.extend(sub_handlers)
        elif receiver in self.subscribers:
            handlers.extend(self.subscribers[receiver])
            
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                import logging
                logging.error(f"Error handling message {message.id} on event bus: {e}")

    def get_messages(self) -> List[AgentMessage]:
        return self.all_messages

class BaseAgent(ABC):
    """Abstract Base Class for all autonomous agents."""
    def __init__(self, name: str, event_bus: EventBus | None = None) -> None:
        self.name: str = name
        self.tools: ToolRegistry = ToolRegistry()
        self.memory: AgentMemory = AgentMemory()
        self.event_bus: EventBus | None = event_bus
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.tools.register("get_memory_history", self.memory.get_recent, "Get recent observations from memory.")

    async def send_message(self, receiver: str, msg_type: str, payload: Dict[str, Any], correlation_id: str | None = None) -> None:
        if self.event_bus:
            msg = AgentMessage(
                sender=self.name,
                receiver=receiver,
                msg_type=msg_type,
                payload=payload,
                correlation_id=correlation_id or str(uuid.uuid4())
            )
            await self.event_bus.publish(msg)

    @abstractmethod
    async def analyze(self, context: Dict[str, Any], correlation_id: str | None = None) -> AgentResult:
        """Analyze a transaction or event context and return an AgentResult."""
        pass
