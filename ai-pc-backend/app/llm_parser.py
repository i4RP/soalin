import asyncio
import json
import os
from typing import Optional

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic


TOOL_DEFS = [
    {
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
    {
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
    {
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
    {
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
    {
        "name": "triple_click",
        "description": "Triple click at a position to select entire line or paragraph.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
            },
        },
    },
    {
        "name": "drag",
        "description": "Drag from one position to another (drag & drop).",
        "parameters": {
            "type": "object",
            "properties": {
                "start_x": {"type": "integer", "description": "Start X coordinate"},
                "start_y": {"type": "integer", "description": "Start Y coordinate"},
                "end_x": {"type": "integer", "description": "End X coordinate"},
                "end_y": {"type": "integer", "description": "End Y coordinate"},
                "duration": {"type": "number", "description": "Duration in seconds", "default": 0.3},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
    },
    {
        "name": "mouse_down",
        "description": "Press and hold mouse button at current or given position. Use with mouse_up for complex drag operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "integer", "description": "1=left, 3=right", "default": 1},
            },
        },
    },
    {
        "name": "mouse_up",
        "description": "Release mouse button at current or given position.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "integer", "description": "1=left, 3=right", "default": 1},
            },
        },
    },
    {
        "name": "hover",
        "description": "Move mouse to a position and hover (for tooltips, menus). Same as move_mouse but semantic.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text using the keyboard. Works for any language including Japanese.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "key_press",
        "description": "Press a single key (Enter, Escape, Tab, BackSpace, Delete, Up, Down, Left, Right, space, Home, End, F1-F12, PageUp, PageDown).",
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Key name, e.g. Return, Escape, Tab, BackSpace"},
            },
            "required": ["keys"],
        },
    },
    {
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
    {
        "name": "scroll",
        "description": "Scroll up or down, optionally at a specific position.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction"},
                "amount": {"type": "integer", "description": "Number of scroll steps", "default": 3},
                "x": {"type": "integer", "description": "X coordinate to scroll at"},
                "y": {"type": "integer", "description": "Y coordinate to scroll at"},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "open_url",
        "description": "Open a URL in the web browser. Use for websites like YouTube, Google, Twitter, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to open, e.g. https://youtube.com"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "open_app",
        "description": "Open an application by name.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name, e.g. chrome, firefox, safari, terminal, notepad, calculator, file_manager, vscode, slack, spotify, discord"},
            },
            "required": ["app_name"],
        },
    },
    {
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
    {
        "name": "wait",
        "description": "Wait for a specified number of seconds. Useful between actions to let pages load.",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "description": "Seconds to wait (0.5 to 10)", "default": 2},
            },
        },
    },
    {
        "name": "get_mouse_position",
        "description": "Get the current mouse cursor position.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "select_all",
        "description": "Select all content in the focused element (Ctrl+A / Cmd+A).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "copy",
        "description": "Copy selected content to clipboard (Ctrl+C / Cmd+C).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "paste",
        "description": "Paste clipboard content (Ctrl+V / Cmd+V).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "cut",
        "description": "Cut selected content to clipboard (Ctrl+X / Cmd+X).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "undo",
        "description": "Undo last action (Ctrl+Z / Cmd+Z).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "redo",
        "description": "Redo last undone action (Ctrl+Shift+Z or Ctrl+Y).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "new_tab",
        "description": "Open a new browser tab (Ctrl+T / Cmd+T).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "close_tab",
        "description": "Close the current browser tab (Ctrl+W / Cmd+W).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "switch_tab",
        "description": "Switch to next or previous browser tab.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["next", "previous"], "description": "Tab direction", "default": "next"},
            },
        },
    },
    {
        "name": "refresh_page",
        "description": "Refresh the current browser page (F5 / Cmd+R).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "go_back",
        "description": "Navigate back in browser history (Alt+Left / Cmd+[).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "go_forward",
        "description": "Navigate forward in browser history (Alt+Right / Cmd+]).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "address_bar",
        "description": "Focus the browser address bar and optionally type a URL (Ctrl+L / Cmd+L).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to type in address bar after focusing"},
            },
        },
    },
    {
        "name": "find_in_page",
        "description": "Open find in page (Ctrl+F / Cmd+F) and search for text.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to search for"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "zoom_in",
        "description": "Zoom in on the page or application (Ctrl++ / Cmd++).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "zoom_out",
        "description": "Zoom out on the page or application (Ctrl+- / Cmd+-).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "zoom_reset",
        "description": "Reset zoom to 100% (Ctrl+0 / Cmd+0).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "close_window",
        "description": "Close the current window (Alt+F4 on Windows/Linux, Cmd+W on Mac).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "minimize_window",
        "description": "Minimize the current window.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "maximize_window",
        "description": "Maximize or fullscreen the current window.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "switch_window",
        "description": "Switch to next window (Alt+Tab on Windows/Linux, Cmd+Tab on Mac).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "take_screenshot",
        "description": "Capture current screen state for analysis. Returns the screenshot.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _openai_tools() -> list[dict]:
    return [{"type": "function", "function": t} for t in TOOL_DEFS]


def _anthropic_tools() -> list[dict]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in TOOL_DEFS
    ]


VALID_ACTIONS = {t["name"] for t in TOOL_DEFS}

SYSTEM_PROMPT = """You are Soalin, an AI that controls a PC. You receive natural language instructions in Japanese or English and call the appropriate tools to execute them.

Screen resolution: 1280x720. Center is (640, 360).

CRITICAL: You MUST call ALL required tools in a SINGLE response. Do NOT return only one tool call when multiple steps are needed. Always plan the COMPLETE sequence of actions and call them ALL at once.

IMPORTANT RULES:
- For opening websites (YouTube, Google, Twitter, etc.), ALWAYS use open_url with the full https:// URL.
- For opening applications (Chrome, Firefox, terminal), use open_app with the app name.
- For drag & drop, use the drag tool with start and end coordinates.
- For complex tasks, call ALL tools in one response. ALWAYS add wait(seconds=2) after open_url or open_app to let the page/app load.
- For browser navigation, prefer address_bar + type the URL + key_press Enter, or use open_url.
- Use clipboard actions (copy, paste, cut, select_all) for text manipulation.
- Use browser tab actions (new_tab, close_tab, switch_tab) for tab management.
- For multi-step workflows, return ALL atomic actions at once with wait() between steps.
- Always prefer specialized actions over run_command when available.
- When searching on a website: click the search field -> type_text -> key_press Return. ALL in one response.

Examples (ALL tools called in ONE response):
- "YouTube開いて" -> open_url(url="https://www.youtube.com"), wait(seconds=2)
- "YouTubeで猫を検索" -> open_url(url="https://www.youtube.com"), wait(seconds=3), click(x=540, y=102), type_text(text="猫"), key_press(keys="Return")
- "検索バーをクリックしてmusicと入力してEnter" -> click(x=540, y=102), wait(seconds=0.5), type_text(text="music"), key_press(keys="Return")
- "Google検索してネコ" -> open_url(url="https://www.google.com/search?q=ネコ"), wait(seconds=2)
- "Chromeを開いて" -> open_app(app_name="chrome"), wait(seconds=2)
- "画面の中央をクリック" -> click(x=640, y=360)
- "Hello Worldと入力して" -> type_text(text="Hello World")
- "全選択してコピー" -> select_all(), copy()
- "ファイルをゴミ箱にドラッグして" -> drag(start_x=..., start_y=..., end_x=..., end_y=...)
- "ページを更新" -> refresh_page()
- "新しいタブ" -> new_tab()
- "タブを閉じて" -> close_tab()
- "前のページに戻って" -> go_back()
- "ズームイン" -> zoom_in()
- "ウィンドウ切り替え" -> switch_window()
- "YouTubeで音楽を再生" -> open_url(url="https://www.youtube.com"), wait(seconds=3), click(x=540, y=102), type_text(text="music"), key_press(keys="Return"), wait(seconds=3), click(x=500, y=300)

Remember: ALWAYS return ALL steps in a SINGLE response. Never return just one step when more are needed."""

VISION_SYSTEM_PROMPT = """You are Soalin, an AI that controls a PC by analyzing screenshots. Look at the screenshot and determine what actions to take.

Screen resolution: 1280x720. Use the screenshot to identify UI elements and their approximate x,y coordinates.

When analyzing the screen:
- Identify clickable elements (buttons, links, text fields) and estimate their x,y coordinates.
- For text fields, click on them first, then type.
- For navigation, identify the address bar or search bar position.
- Look at the current state to determine what has already been done and what's next.
- If a page is still loading, use wait() before interacting.
"""

GPT4O_ADVISOR_PROMPT = """You are a senior advisor AI for Soalin, a PC-control assistant. The primary AI (Claude) attempted an action plan but it FAILED. You need to analyze what went wrong and propose a BETTER plan.

User's original request: "{user_message}"

Claude's plan that was executed:
{claude_plan}

Execution results (FAILED):
{results}

Analyze the failure and propose a corrected action plan. Consider:
1. Were the coordinates wrong? Adjust them.
2. Was a wait() step missing? Add it.
3. Was the wrong action used? Fix it.
4. Was there a missing step? Add it.

Output ONLY a valid JSON array of action objects. No explanation."""


class LLMParser:
    def __init__(self):
        self._openai_key: Optional[str] = os.environ.get("OPENAI_API_KEY")
        self._anthropic_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
        if not self._anthropic_key:
            self._anthropic_key = os.environ.get("claude_api_key")
        self._openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._claude_model: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self._openai: Optional[AsyncOpenAI] = None
        self._anthropic: Optional[AsyncAnthropic] = None
        if self._openai_key:
            self._openai = AsyncOpenAI(api_key=self._openai_key)
        if self._anthropic_key:
            self._anthropic = AsyncAnthropic(api_key=self._anthropic_key)

    @property
    def is_available(self) -> bool:
        return self._openai is not None or self._anthropic is not None

    @property
    def mode(self) -> str:
        has_both = self._openai is not None and self._anthropic is not None
        if has_both:
            return "dual"
        if self._anthropic is not None:
            return "claude"
        if self._openai is not None:
            return "openai"
        return "none"

    @property
    def model(self) -> str:
        if self.mode == "dual":
            return f"{self._claude_model}+{self._openai_model}"
        if self._anthropic:
            return self._claude_model
        if self._openai:
            return self._openai_model
        return "none"

    def configure(
        self,
        openai_api_key: str = "",
        openai_model: str = "",
        anthropic_api_key: str = "",
        claude_model: str = "",
    ) -> None:
        if openai_api_key:
            self._openai_key = openai_api_key
            self._openai = AsyncOpenAI(api_key=openai_api_key)
        if openai_model:
            self._openai_model = openai_model
        if anthropic_api_key:
            self._anthropic_key = anthropic_api_key
            self._anthropic = AsyncAnthropic(api_key=anthropic_api_key)
        if claude_model:
            self._claude_model = claude_model

    def disable(self) -> None:
        self._openai_key = None
        self._anthropic_key = None
        self._openai = None
        self._anthropic = None

    async def parse(self, message: str, context: list[dict] | None = None) -> list[dict]:
        if self._anthropic:
            return await self._parse_claude(message, context)
        if self._openai:
            return await self._parse_openai(message, context)
        return []

    async def consult_gpt4o(self, user_message: str, claude_plan: list[dict], results: list[dict]) -> list[dict]:
        if not self._openai:
            return []

        prompt = GPT4O_ADVISOR_PROMPT.format(
            user_message=user_message,
            claude_plan=json.dumps(claude_plan, ensure_ascii=False),
            results=json.dumps(results, ensure_ascii=False),
        )

        try:
            response = await self._openai.chat.completions.create(
                model=self._openai_model,
                messages=[{"role": "user", "content": prompt}],
                tools=_openai_tools(),
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
                    if fn_name in VALID_ACTIONS:
                        commands.append({"action": fn_name, **fn_args})

            if not commands and msg.content:
                text = msg.content.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        for cmd in parsed:
                            if isinstance(cmd, dict) and cmd.get("action") in VALID_ACTIONS:
                                commands.append(cmd)
                except (json.JSONDecodeError, ValueError):
                    pass

            return commands
        except Exception as e:
            print(f"GPT-4o advisor error: {e}")
            return []

    async def _parse_openai(self, message: str, context: list[dict] | None = None) -> list[dict]:
        if not self._openai:
            return []

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            for ctx in context[-5:]:
                messages.append({"role": ctx.get("role", "user"), "content": ctx.get("content", "")})
        messages.append({"role": "user", "content": message})

        try:
            response = await self._openai.chat.completions.create(
                model=self._openai_model,
                messages=messages,
                tools=_openai_tools(),
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
            print(f"OpenAI parse error: {e}")
            return []

    async def _parse_claude(self, message: str, context: list[dict] | None = None) -> list[dict]:
        if not self._anthropic:
            return []

        messages = []
        if context:
            for ctx in context[-5:]:
                role = ctx.get("role", "user")
                if role == "system":
                    continue
                messages.append({"role": role, "content": ctx.get("content", "")})
        messages.append({"role": "user", "content": message})

        if len(messages) >= 2:
            deduped = [messages[0]]
            for m in messages[1:]:
                if m["role"] != deduped[-1]["role"]:
                    deduped.append(m)
                else:
                    deduped[-1]["content"] += "\n" + m["content"]
            messages = deduped
        if messages and messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "..."})

        try:
            all_commands = []
            max_turns = 5

            for turn in range(max_turns):
                response = await self._anthropic.messages.create(
                    model=self._claude_model,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=_anthropic_tools(),
                    max_tokens=2048,
                    temperature=0.1,
                )

                tool_uses = []
                for block in response.content:
                    if block.type == "tool_use":
                        cmd = {"action": block.name, **block.input}
                        all_commands.append(cmd)
                        tool_uses.append(block)

                if response.stop_reason != "tool_use" or not tool_uses:
                    break

                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for tu in tool_uses:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps({"success": True, "description": f"Queued: {tu.name}"}),
                    })
                messages.append({"role": "user", "content": tool_results})

            return all_commands
        except Exception as e:
            print(f"Claude parse error: {e}")
            return []

    async def parse_with_vision(self, message: str, screenshot_b64: str, context: list[dict] | None = None) -> list[dict]:
        if self._anthropic:
            return await self._vision_claude(message, screenshot_b64, context)
        if self._openai:
            return await self._vision_openai(message, screenshot_b64, context)
        return []

    async def _vision_openai(self, message: str, screenshot_b64: str, context: list[dict] | None = None) -> list[dict]:
        if not self._openai:
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
            response = await self._openai.chat.completions.create(
                model=self._openai_model,
                messages=messages,
                tools=_openai_tools(),
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
            print(f"OpenAI vision error: {e}")
            return []

    async def _vision_claude(self, message: str, screenshot_b64: str, context: list[dict] | None = None) -> list[dict]:
        if not self._anthropic:
            return []

        messages = []
        if context:
            for ctx in context[-3:]:
                role = ctx.get("role", "user")
                if role == "system":
                    continue
                messages.append({"role": role, "content": ctx.get("content", "")})

        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": screenshot_b64,
                },
            },
            {"type": "text", "text": message},
        ]
        messages.append({"role": "user", "content": user_content})

        if len(messages) >= 2:
            deduped = [messages[0]]
            for m in messages[1:]:
                if m["role"] != deduped[-1]["role"]:
                    deduped.append(m)
            messages = deduped
        if messages and messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "..."})

        try:
            response = await self._anthropic.messages.create(
                model=self._claude_model,
                system=VISION_SYSTEM_PROMPT,
                messages=messages,
                tools=_anthropic_tools(),
                max_tokens=2048,
                temperature=0.1,
            )

            commands = []
            for block in response.content:
                if block.type == "tool_use":
                    cmd = {"action": block.name, **block.input}
                    commands.append(cmd)
            return commands
        except Exception as e:
            print(f"Claude vision error: {e}")
            return []

    async def generate_reply(self, user_message: str, results: list[dict], provider_used: str = "") -> str:
        descriptions = [r.get("description", "") for r in results if r.get("description")]
        all_success = all(r.get("success", False) for r in results)

        prompt = f"""User asked: "{user_message}"
Actions performed: {', '.join(descriptions)}
All successful: {all_success}
AI used: {provider_used or self.mode}

Generate a brief, friendly reply in Japanese (1-2 sentences) confirming what was done.
If actions failed, explain what went wrong briefly.
If GPT-4o was consulted after Claude's failure, mention that."""

        if self._anthropic:
            reply = await self._reply_claude(prompt)
            if reply:
                return reply
        if self._openai:
            return await self._reply_openai(prompt)
        return ""

    async def _reply_openai(self, prompt: str) -> str:
        if not self._openai:
            return ""
        try:
            response = await self._openai.chat.completions.create(
                model=self._openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""

    async def _reply_claude(self, prompt: str) -> str:
        if not self._anthropic:
            return ""
        try:
            response = await self._anthropic.messages.create(
                model=self._claude_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        except Exception:
            return ""
