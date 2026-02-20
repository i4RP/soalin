import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket


@dataclass
class AgentConnection:
    websocket: WebSocket
    connection_code: str
    session_id: str
    connected_at: float
    last_screen: str = ""
    last_screen_time: float = 0
    screen_width: int = 1280
    screen_height: int = 720
    pending_commands: dict = field(default_factory=dict)


class AgentRelay:
    def __init__(self):
        self._agents: dict[str, AgentConnection] = {}
        self._code_to_session: dict[str, str] = {}

    def register_agent(self, session_id: str, code: str, ws: WebSocket) -> AgentConnection:
        conn = AgentConnection(
            websocket=ws,
            connection_code=code,
            session_id=session_id,
            connected_at=time.time(),
        )
        self._agents[session_id] = conn
        self._code_to_session[code.upper()] = session_id
        return conn

    def unregister_agent(self, session_id: str) -> None:
        conn = self._agents.pop(session_id, None)
        if conn:
            self._code_to_session.pop(conn.connection_code.upper(), None)

    def get_agent(self, session_id: str) -> Optional[AgentConnection]:
        return self._agents.get(session_id)

    def get_agent_by_code(self, code: str) -> Optional[AgentConnection]:
        session_id = self._code_to_session.get(code.upper())
        if session_id:
            return self._agents.get(session_id)
        return None

    def has_agent(self, session_id: str) -> bool:
        return session_id in self._agents

    def update_screen(self, session_id: str, image: str, width: int = 1280, height: int = 720) -> None:
        conn = self._agents.get(session_id)
        if conn:
            conn.last_screen = image
            conn.last_screen_time = time.time()
            conn.screen_width = width
            conn.screen_height = height

    async def send_command(self, session_id: str, command: dict, command_id: str = "") -> Optional[dict]:
        conn = self._agents.get(session_id)
        if not conn:
            return None

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        cmd_id = command_id or f"cmd_{time.time()}"
        conn.pending_commands[cmd_id] = future

        try:
            await conn.websocket.send_json({
                "type": "command",
                "command": command,
                "command_id": cmd_id,
            })
            result = await asyncio.wait_for(future, timeout=15.0)
            return result
        except asyncio.TimeoutError:
            conn.pending_commands.pop(cmd_id, None)
            return {"success": False, "action": command.get("action", ""), "description": "Timeout waiting for agent"}
        except Exception as e:
            conn.pending_commands.pop(cmd_id, None)
            return {"success": False, "action": command.get("action", ""), "description": f"Error: {e}"}

    def resolve_command(self, session_id: str, command_id: str, result: dict) -> None:
        conn = self._agents.get(session_id)
        if conn:
            future = conn.pending_commands.pop(command_id, None)
            if future and not future.done():
                future.set_result(result)

    @property
    def active_agents(self) -> int:
        return len(self._agents)
