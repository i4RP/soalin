import json
import os
from typing import Optional

from openai import AsyncOpenAI


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to absolute coordinates on screen (1280x720 resolution). Center is (640, 360).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate (0-1280)"},
                    "y": {"type": "integer", "description": "Y coordinate (0-720)"},
                    "relative": {"type": "boolean", "description": "If true, move relative to current position"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at a position. If x,y not provided, clicks at current position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                    "button": {"type": "integer", "description": "1=left, 2=middle, 3=right", "default": 1},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double click at a position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "right_click",
            "description": "Right click at a position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "Drag from one position to another (drag & drop). Moves mouse to start, holds button, moves to end, releases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {"type": "integer", "description": "Start X coordinate"},
                    "start_y": {"type": "integer", "description": "Start Y coordinate"},
                    "end_x": {"type": "integer", "description": "End X coordinate"},
                    "end_y": {"type": "integer", "description": "End Y coordinate"},
                },
                "required": ["start_x", "start_y", "end_x", "end_y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key_press",
            "description": "Press a single key (Enter, Escape, Tab, BackSpace, Delete, Up, Down, Left, Right, space, Home, End, F1-F12).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key name, e.g. Return, Escape, Tab, BackSpace"},
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shortcut",
            "description": "Press a keyboard shortcut combination like ctrl+c, ctrl+v, ctrl+s, alt+F4, ctrl+shift+s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key combination, e.g. ctrl+c, ctrl+shift+s, alt+F4"},
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction"},
                    "amount": {"type": "integer", "description": "Number of scroll steps", "default": 3},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the web browser. Use this for opening websites like YouTube, Google, Twitter, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open, e.g. https://youtube.com, https://google.com"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application by name. The system will find and launch the correct executable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name, e.g. chrome, firefox, terminal, notepad, file_manager"},
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command. Use for advanced operations not covered by other tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for a specified number of seconds. Useful between actions to let pages load.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "Seconds to wait (0.5 to 10)", "default": 2},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mouse_position",
            "description": "Get the current mouse cursor position.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

SYSTEM_PROMPT = """You are Soalin, an AI that controls a PC. You receive natural language instructions in Japanese or English and call the appropriate tools to execute them.

Screen resolution: 1280x720. Center is (640, 360).

Key guidelines:
- For opening websites (YouTube, Google, Twitter, etc.), use open_url with the full URL.
- For opening applications (Chrome, Firefox, terminal), use open_app with the app name.
- For drag & drop, use the drag tool with start and end coordinates.
- For complex tasks, call multiple tools in sequence. Add wait() between steps if needed (e.g. after opening a page).
- When the user says something like "YouTubeでLoFi音楽を検索", break it into: open_url -> wait -> click search bar -> type_text -> key_press Enter.
- Always prefer open_url over run_command for opening websites.
- Always prefer open_app over run_command for launching applications.

Examples:
- "YouTube開いて" -> open_url(url="https://www.youtube.com")
- "Chromeを開いて" -> open_app(app_name="chrome")
- "ターミナルを開いて" -> open_app(app_name="terminal")
- "Google検索してネコ" -> open_url(url="https://www.google.com/search?q=ネコ")
- "ファイルをゴミ箱にドラッグして" -> drag(start_x=..., start_y=..., end_x=..., end_y=...)
- "画面の中央をクリック" -> click(x=640, y=360)
- "Hello Worldと入力して" -> type_text(text="Hello World")
- "Ctrl+Sを押して" -> shortcut(keys="ctrl+s")
"""

VISION_SYSTEM_PROMPT = """You are Soalin, an AI that controls a PC by looking at screenshots. Analyze the screenshot and determine what actions to take to fulfill the user's request.

Screen resolution: 1280x720. Use the screenshot to identify UI elements and their approximate coordinates.

When analyzing the screen:
- Identify clickable elements (buttons, links, text fields) and estimate their x,y coordinates.
- For text fields, click on them first, then type.
- For navigation, identify the address bar or search bar position.
- Report what you see on screen to help plan the next action.
"""


class LLMParser:
    def __init__(self):
        self._api_key: Optional[str] = os.environ.get("OPENAI_API_KEY")
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._client: Optional[AsyncOpenAI] = None
        if self._api_key:
            self._client = AsyncOpenAI(api_key=self._api_key)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def configure(self, api_key: str, model: str = "gpt-4o") -> None:
        self._api_key = api_key
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key)

    def disable(self) -> None:
        self._api_key = None
        self._client = None

    async def parse(self, message: str, context: list[dict] | None = None) -> list[dict]:
        if not self._client:
            return []

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            for ctx in context[-5:]:
                messages.append({"role": ctx.get("role", "user"), "content": ctx.get("content", "")})
        messages.append({"role": "user", "content": message})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=2048,
            )

            msg = response.choices[0].message
            commands = []

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}
                    cmd = {"action": fn_name, **fn_args}
                    commands.append(cmd)

            if not commands and msg.content:
                content = msg.content.strip()
                if content.startswith("["):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            commands = parsed
                        elif isinstance(parsed, dict):
                            commands = [parsed]
                    except json.JSONDecodeError:
                        pass

            return commands
        except Exception as e:
            print(f"LLM parse error: {e}")
            return []

    async def parse_with_vision(self, message: str, screenshot_b64: str, context: list[dict] | None = None) -> list[dict]:
        if not self._client:
            return []

        messages = [{"role": "system", "content": VISION_SYSTEM_PROMPT}]
        if context:
            for ctx in context[-3:]:
                messages.append({"role": ctx.get("role", "user"), "content": ctx.get("content", "")})

        user_content = [
            {"type": "text", "text": message},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{screenshot_b64}",
                    "detail": "low",
                },
            },
        ]
        messages.append({"role": "user", "content": user_content})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=2048,
            )

            msg = response.choices[0].message
            commands = []

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}
                    cmd = {"action": fn_name, **fn_args}
                    commands.append(cmd)

            return commands
        except Exception as e:
            print(f"LLM vision parse error: {e}")
            return []

    async def generate_reply(self, user_message: str, results: list[dict]) -> str:
        if not self._client:
            return ""

        descriptions = [r.get("description", "") for r in results if r.get("description")]
        all_success = all(r.get("success", False) for r in results)

        prompt = f"""User asked: "{user_message}"
Actions performed: {', '.join(descriptions)}
All successful: {all_success}

Generate a brief, friendly reply in Japanese (1-2 sentences) confirming what was done.
If actions failed, explain what went wrong briefly."""

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""
