import asyncio
import io
import json
import os
import subprocess
import time
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.controller import PCController
from app.ai_parser import AICommandParser
from app.llm_parser import LLMParser
from app.screen import ScreenCapture
from app.session_manager import SessionManager
from app.agent_relay import AgentRelay
from app.agent_bundle import get_agent_files


display_process = None
screen_capture: ScreenCapture | None = None
pc_controller: PCController | None = None
ai_parser: AICommandParser | None = None
llm_parser: LLMParser | None = None
session_manager: SessionManager | None = None
agent_relay: AgentRelay | None = None


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global display_process, screen_capture, pc_controller, ai_parser, llm_parser, session_manager, agent_relay

    display_num = os.environ.get("VIRTUAL_DISPLAY", ":99")
    width = int(os.environ.get("SCREEN_WIDTH", "1280"))
    height = int(os.environ.get("SCREEN_HEIGHT", "720"))

    existing_display = os.environ.get("DISPLAY", "")
    use_virtual = os.environ.get("USE_VIRTUAL_DISPLAY", "true").lower() == "true"

    if use_virtual:
        try:
            display_process = subprocess.Popen(
                [
                    "Xvfb", display_num,
                    "-screen", "0", f"{width}x{height}x24",
                    "+extension", "RANDR"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.environ["DISPLAY"] = display_num
            await asyncio.sleep(1)

            subprocess.Popen(
                ["xterm"],
                env={**os.environ, "DISPLAY": display_num},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(0.5)
        except FileNotFoundError:
            if existing_display:
                os.environ["DISPLAY"] = existing_display
    elif existing_display:
        os.environ["DISPLAY"] = existing_display

    screen_capture = ScreenCapture(width=width, height=height)
    pc_controller = PCController()
    ai_parser = AICommandParser()
    llm_parser = LLMParser()
    session_manager = SessionManager()
    agent_relay = AgentRelay()

    yield

    if display_process:
        display_process.terminate()
        display_process.wait()


app = FastAPI(lifespan=lifespan)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


class ChatMessage(BaseModel):
    message: str
    session_id: str = ""


class ActionRequest(BaseModel):
    action: str
    params: dict = {}


class SettingsUpdate(BaseModel):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    vision_enabled: bool = True


class SessionCreate(BaseModel):
    username: str = ""


class ConnectionCode(BaseModel):
    code: str


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/screenshot")
async def get_screenshot(session_id: str = ""):
    agent_conn = None
    if session_id and agent_relay:
        agent_conn = agent_relay.get_agent(session_id)
        if not agent_conn and session_manager:
            session = session_manager.get_session(session_id)
            if session:
                agent_conn = agent_relay.get_agent_by_code(session.connection_code)
    if agent_conn and agent_conn.last_screen:
        return {
            "image": agent_conn.last_screen,
            "width": agent_conn.screen_width,
            "height": agent_conn.screen_height,
            "timestamp": agent_conn.last_screen_time,
            "source": "remote_mac",
        }
    if screen_capture is None:
        return JSONResponse(status_code=503, content={"error": "Screen capture not initialized"})
    img_base64 = screen_capture.capture_base64()
    return {
        "image": img_base64,
        "width": screen_capture.width,
        "height": screen_capture.height,
        "timestamp": time.time(),
        "source": "virtual_desktop",
    }


@app.post("/api/session/create")
async def create_session(req: SessionCreate):
    if session_manager is None:
        return JSONResponse(status_code=503, content={"error": "Session manager not initialized"})
    session = session_manager.create_session(username=req.username)
    return {
        "session_id": session.session_id,
        "connection_code": session.connection_code,
        "created_at": session.created_at,
    }


@app.post("/api/session/connect")
async def connect_with_code(req: ConnectionCode):
    if session_manager is None:
        return JSONResponse(status_code=503, content={"error": "Session manager not initialized"})
    session = session_manager.get_by_code(req.code)
    if not session:
        session = session_manager.create_session()
        old_code = session.connection_code
        session_manager._codes.pop(old_code, None)
        session.connection_code = req.code.upper()
        session_manager._codes[req.code.upper()] = session.session_id
    return {
        "session_id": session.session_id,
        "connection_code": session.connection_code,
        "username": session.username,
    }


@app.get("/api/session/{session_id}")
async def get_session_info(session_id: str):
    if session_manager is None:
        return JSONResponse(status_code=503, content={"error": "Session manager not initialized"})
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    has_agent = agent_relay.has_agent(session_id) if agent_relay else False
    return {
        "session_id": session.session_id,
        "connection_code": session.connection_code,
        "username": session.username,
        "created_at": session.created_at,
        "chat_history": session.chat_history[-50:],
        "has_agent": has_agent,
        "settings": {
            "has_openai_key": bool(session.settings.get("openai_api_key")),
            "openai_model": session.settings.get("openai_model", "gpt-4o-mini"),
        },
    }


@app.get("/api/session/{session_id}/history")
async def get_chat_history(session_id: str):
    if session_manager is None:
        return JSONResponse(status_code=503, content={"error": "Session manager not initialized"})
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return {"history": session.chat_history}


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if llm_parser is None:
        return JSONResponse(status_code=503, content={"error": "LLM parser not initialized"})

    if settings.openai_api_key or settings.anthropic_api_key:
        llm_parser.configure(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            anthropic_api_key=settings.anthropic_api_key,
            claude_model=settings.claude_model,
        )
        return {
            "status": "ok",
            "llm_enabled": True,
            "mode": llm_parser.mode,
            "model": llm_parser.model,
        }
    else:
        llm_parser.disable()
        return {"status": "ok", "llm_enabled": False}


@app.get("/api/settings")
async def get_settings():
    return {
        "llm_enabled": llm_parser is not None and llm_parser.is_available,
        "mode": llm_parser.mode if llm_parser else "none",
        "model": llm_parser.model if llm_parser else "none",
    }


async def _execute_commands(commands: list[dict], session_id: str, use_agent: bool) -> tuple[list[dict], str]:
    results = []
    img_base64 = ""
    if use_agent and agent_relay:
        for cmd in commands:
            result = await agent_relay.send_command(session_id, cmd)
            if result:
                results.append(result)
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.5)
        agent_conn = agent_relay.get_agent(session_id)
        img_base64 = agent_conn.last_screen if agent_conn else ""
    else:
        if pc_controller is None or screen_capture is None:
            return results, img_base64
        for cmd in commands:
            result = pc_controller.execute(cmd)
            results.append(result)
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.5)
        img_base64 = screen_capture.capture_base64()
    return results, img_base64


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    if ai_parser is None:
        return JSONResponse(status_code=503, content={"error": "System not initialized"})

    session = None
    use_agent = False
    agent_session_id = msg.session_id
    if msg.session_id and session_manager:
        session = session_manager.get_session(msg.session_id)
        if session:
            session.add_message("user", msg.message)
        if agent_relay:
            if agent_relay.has_agent(msg.session_id):
                use_agent = True
            elif session:
                agent_conn = agent_relay.get_agent_by_code(session.connection_code)
                if agent_conn:
                    use_agent = True
                    agent_session_id = agent_conn.session_id

    context = session.chat_history[-10:] if session else None
    commands: list[dict] = []
    used_llm = False
    provider_used = ""

    if llm_parser and llm_parser.is_available:
        commands = await llm_parser.parse(msg.message, context)
        if commands:
            used_llm = True
            provider_used = "claude" if llm_parser.mode in ("dual", "claude") else "openai"

    if not commands:
        commands = ai_parser.parse(msg.message)

    results, img_base64 = await _execute_commands(commands, agent_session_id, use_agent)

    any_failed = any(not r.get("success", False) for r in results)
    consulted_gpt4o = False

    if used_llm and any_failed and llm_parser and llm_parser.mode == "dual":
        retry_commands = await llm_parser.consult_gpt4o(msg.message, commands, results)
        if retry_commands:
            consulted_gpt4o = True
            provider_used = "claude+gpt4o"
            results, img_base64 = await _execute_commands(retry_commands, agent_session_id, use_agent)

    reply = ""
    if used_llm and llm_parser:
        reply = await llm_parser.generate_reply(msg.message, results, provider_used)
    if not reply:
        reply = ai_parser.generate_reply(msg.message, results)

    if session:
        session.add_message("assistant", reply)

    return {
        "reply": reply,
        "actions": results,
        "screenshot": img_base64,
        "timestamp": time.time(),
        "used_llm": used_llm,
        "provider": provider_used,
        "consulted_gpt4o": consulted_gpt4o,
        "source": "remote_mac" if use_agent else "virtual_desktop",
    }


@app.post("/api/action")
async def execute_action(req: ActionRequest):
    if pc_controller is None:
        return JSONResponse(status_code=503, content={"error": "Controller not initialized"})

    cmd = {"action": req.action, **req.params}
    result = pc_controller.execute(cmd)

    await asyncio.sleep(0.2)
    img_base64 = screen_capture.capture_base64() if screen_capture else ""

    return {
        "result": result,
        "screenshot": img_base64,
        "timestamp": time.time(),
    }


@app.websocket("/ws/screen")
async def websocket_screen(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if screen_capture:
                img_base64 = screen_capture.capture_base64()
                await websocket.send_json({
                    "type": "screen_update",
                    "image": img_base64,
                    "timestamp": time.time(),
                })
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            user_message = msg_data.get("message", "")
            session_id = msg_data.get("session_id", "")

            if not user_message or ai_parser is None or pc_controller is None:
                await websocket.send_json({
                    "type": "error",
                    "message": "Empty message or system not ready",
                })
                continue

            session = None
            if session_id and session_manager:
                session = session_manager.get_session(session_id)
                if session:
                    session.add_message("user", user_message)

            context = session.chat_history[-10:] if session else None
            commands: list[dict] = []
            used_llm = False

            if llm_parser and llm_parser.is_available:
                commands = await llm_parser.parse(user_message, context)
                if commands:
                    used_llm = True

            if not commands:
                commands = ai_parser.parse(user_message)

            await websocket.send_json({
                "type": "status",
                "message": f"{len(commands)} action(s) executing...",
            })

            results = []
            for cmd in commands:
                result = pc_controller.execute(cmd)
                results.append(result)

                img_base64 = screen_capture.capture_base64() if screen_capture else ""
                await websocket.send_json({
                    "type": "action_update",
                    "action": result,
                    "screenshot": img_base64,
                    "timestamp": time.time(),
                })
                await asyncio.sleep(0.3)

            reply = ""
            if used_llm and llm_parser:
                reply = await llm_parser.generate_reply(user_message, results)
            if not reply:
                reply = ai_parser.generate_reply(user_message, results)

            if session:
                session.add_message("assistant", reply)

            img_base64 = screen_capture.capture_base64() if screen_capture else ""

            await websocket.send_json({
                "type": "chat_response",
                "reply": reply,
                "actions": results,
                "screenshot": img_base64,
                "timestamp": time.time(),
                "used_llm": used_llm,
            })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/api/agent/download")
async def download_agent():
    buf = io.BytesIO()
    agent_files = get_agent_files()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in agent_files.items():
            zf.writestr(path, content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=ai-pc-agent.zip"},
    )


@app.get("/api/agent/status")
async def agent_status(session_id: str = ""):
    if not agent_relay:
        return {"connected": False, "active_agents": 0}
    if session_id:
        has = agent_relay.has_agent(session_id)
        if not has and session_manager:
            session = session_manager.get_session(session_id)
            if session:
                agent_conn = agent_relay.get_agent_by_code(session.connection_code)
                has = agent_conn is not None
        return {"connected": has, "active_agents": agent_relay.active_agents, "session_id": session_id}
    return {"connected": False, "active_agents": agent_relay.active_agents}


@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket, code: str = Query("")):
    if not code or not session_manager or not agent_relay:
        await websocket.close(code=4001, reason="Missing connection code")
        return

    session = session_manager.get_by_code(code)
    if not session:
        session = session_manager.create_session()
        old_code = session.connection_code
        session_manager._codes.pop(old_code, None)
        session.connection_code = code.upper()
        session_manager._codes[code.upper()] = session.session_id
        print(f"Auto-created session for agent code={code}")

    await websocket.accept()
    session_id = session.session_id
    agent_relay.register_agent(session_id, code, websocket)
    print(f"Agent connected: session={session_id[:8]}... code={code}")

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "screen":
                agent_relay.update_screen(
                    session_id,
                    data.get("image", ""),
                    data.get("width", 1280),
                    data.get("height", 720),
                )

            elif msg_type == "command_result":
                cmd_id = data.get("command_id", "")
                result = data.get("result", {})
                agent_relay.resolve_command(session_id, cmd_id, result)

            elif msg_type == "pong":
                pass

    except WebSocketDisconnect:
        print(f"Agent disconnected: session={session_id[:8]}...")
    except Exception as e:
        print(f"Agent error: {e}")
    finally:
        agent_relay.unregister_agent(session_id)
