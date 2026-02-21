import asyncio
import base64
import io
import json
import platform
import signal
import subprocess
import sys
import time
from typing import Optional
import mss
import pyautogui
from PIL import Image

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05


class PCAgent:
    def __init__(self, server_url: str, connection_code: str, fps: int = 2):
        self._server_url = server_url.rstrip("/")
        self._connection_code = connection_code
        self._fps = fps
        self._running = False
        self._ws = None
        self._platform = platform.system()
        self._screen_width, self._screen_height = pyautogui.size()
        self._capture = mss.mss()

    @property
    def ws_url(self) -> str:
        base = self._server_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/ws/agent?code={self._connection_code}"

    def capture_screen(self) -> str:
        monitor = self._capture.monitors[1]
        raw = self._capture.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img = img.resize((1280, 720), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def execute_command(self, command: dict) -> dict:
        action = command.get("action", "")
        try:
            if action == "move_mouse":
                x = command.get("x", 0)
                y = command.get("y", 0)
                relative = command.get("relative", False)
                sx = x * self._screen_width / 1280
                sy = y * self._screen_height / 720
                if relative:
                    pyautogui.moveRel(sx, sy)
                else:
                    pyautogui.moveTo(sx, sy)
                return {"success": True, "action": action, "description": f"Moved mouse to ({x}, {y})"}

            elif action == "click":
                button_map = {1: "left", 2: "middle", 3: "right"}
                btn_num = command.get("button", 1)
                btn = button_map.get(btn_num, "left")
                x = command.get("x")
                y = command.get("y")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.click(sx, sy, button=btn)
                    return {"success": True, "action": action, "description": f"{btn} click at ({x}, {y})"}
                else:
                    pyautogui.click(button=btn)
                    return {"success": True, "action": action, "description": f"{btn} click"}

            elif action == "double_click":
                x = command.get("x")
                y = command.get("y")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.doubleClick(sx, sy)
                    return {"success": True, "action": action, "description": f"Double click at ({x}, {y})"}
                else:
                    pyautogui.doubleClick()
                    return {"success": True, "action": action, "description": "Double click"}

            elif action == "right_click":
                x = command.get("x")
                y = command.get("y")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.rightClick(sx, sy)
                    return {"success": True, "action": action, "description": f"Right click at ({x}, {y})"}
                else:
                    pyautogui.rightClick()
                    return {"success": True, "action": action, "description": "Right click"}

            elif action == "drag":
                start_x = command.get("start_x", 0) * self._screen_width / 1280
                start_y = command.get("start_y", 0) * self._screen_height / 720
                end_x = command.get("end_x", 0) * self._screen_width / 1280
                end_y = command.get("end_y", 0) * self._screen_height / 720
                pyautogui.moveTo(start_x, start_y)
                pyautogui.mouseDown()
                pyautogui.moveTo(end_x, end_y, duration=0.3)
                pyautogui.mouseUp()
                return {"success": True, "action": action, "description": f"Dragged from ({command.get('start_x')}, {command.get('start_y')}) to ({command.get('end_x')}, {command.get('end_y')})"}

            elif action == "type_text":
                text = command.get("text", "")
                pyautogui.typewrite(text, interval=0.03) if text.isascii() else pyautogui.write(text)
                return {"success": True, "action": action, "description": f"Typed: {text}"}

            elif action == "key_press":
                keys = command.get("keys", "")
                key_map = {
                    "Return": "enter", "Escape": "escape", "Tab": "tab",
                    "BackSpace": "backspace", "Delete": "delete",
                    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
                    "space": "space", "Home": "home", "End": "end",
                }
                mapped = key_map.get(keys, keys.lower())
                pyautogui.press(mapped)
                return {"success": True, "action": action, "description": f"Pressed: {keys}"}

            elif action == "shortcut":
                keys = command.get("keys", "")
                is_mac = self._platform == "Darwin"
                parts = keys.replace("ctrl+", "command+").split("+") if is_mac else keys.split("+")
                key_map = {"ctrl": "command" if is_mac else "ctrl", "alt": "option" if is_mac else "alt", "shift": "shift"}
                mapped_parts = []
                for p in parts:
                    p_lower = p.strip().lower()
                    mapped_parts.append(key_map.get(p_lower, p_lower))
                pyautogui.hotkey(*mapped_parts)
                return {"success": True, "action": action, "description": f"Shortcut: {keys}"}

            elif action == "scroll":
                direction = command.get("direction", "down")
                amount = command.get("amount", 3)
                clicks = amount * 3 if direction == "up" else -amount * 3
                pyautogui.scroll(clicks)
                return {"success": True, "action": action, "description": f"Scrolled {direction} {amount} times"}

            elif action == "open_url":
                url = command.get("url", "")
                if not url:
                    return {"success": False, "action": action, "description": "No URL specified"}
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                if self._platform == "Darwin":
                    subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif self._platform == "Windows":
                    subprocess.Popen(["start", url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    browser_paths = [
                        "/opt/.devin/chrome/chrome/linux-137.0.7118.2/chrome-linux64/chrome",
                        "google-chrome",
                        "chromium-browser",
                        "firefox",
                    ]
                    launched = False
                    for bp in browser_paths:
                        try:
                            args = [bp]
                            if "chrome" in bp.lower():
                                args += ["--no-sandbox", "--no-first-run", "--user-data-dir=/tmp/chrome-agent"]
                            args.append(url)
                            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            launched = True
                            break
                        except FileNotFoundError:
                            continue
                    if not launched:
                        subprocess.Popen(f"xdg-open '{url}' &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"success": True, "action": action, "description": f"Opened URL: {url}"}

            elif action == "open_app":
                app_name = command.get("app_name", "").lower()
                if not app_name:
                    return {"success": False, "action": action, "description": "No app name specified"}
                app_commands = {
                    "chrome": {
                        "Darwin": ["open", "-a", "Google Chrome"],
                        "Windows": ["start", "chrome"],
                        "Linux": ["/opt/.devin/chrome/chrome/linux-137.0.7118.2/chrome-linux64/chrome", "--no-sandbox", "--no-first-run", "--user-data-dir=/tmp/chrome-agent"],
                    },
                    "firefox": {
                        "Darwin": ["open", "-a", "Firefox"],
                        "Windows": ["start", "firefox"],
                        "Linux": ["firefox"],
                    },
                    "terminal": {
                        "Darwin": ["open", "-a", "Terminal"],
                        "Windows": ["start", "cmd"],
                        "Linux": ["xterm"],
                    },
                    "notepad": {
                        "Darwin": ["open", "-a", "TextEdit"],
                        "Windows": ["notepad"],
                        "Linux": ["xterm", "-e", "nano"],
                    },
                    "file_manager": {
                        "Darwin": ["open", "."],
                        "Windows": ["explorer"],
                        "Linux": ["nautilus", "."],
                    },
                }
                cmd_list = None
                if app_name in app_commands:
                    cmd_list = app_commands[app_name].get(self._platform)
                if cmd_list:
                    try:
                        subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        subprocess.Popen(f"{app_name} &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(f"{app_name} &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"success": True, "action": action, "description": f"Opened app: {app_name}"}

            elif action == "wait":
                seconds = min(float(command.get("seconds", 2)), 10)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import time as _time
                        _time.sleep(seconds)
                    else:
                        loop.run_until_complete(asyncio.sleep(seconds))
                except RuntimeError:
                    import time as _time
                    _time.sleep(seconds)
                return {"success": True, "action": action, "description": f"Waited {seconds}s"}

            elif action == "run_command":
                cmd = command.get("command", "")
                if not cmd:
                    return {"success": False, "action": action, "description": "No command specified"}
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"success": True, "action": action, "description": f"Executed: {cmd}"}

            elif action == "get_mouse_position":
                pos = pyautogui.position()
                nx = int(pos[0] * 1280 / self._screen_width)
                ny = int(pos[1] * 720 / self._screen_height)
                return {"success": True, "action": action, "description": f"Mouse position: ({nx}, {ny})", "position": f"x:{nx} y:{ny}"}

            elif action == "triple_click":
                x = command.get("x")
                y = command.get("y")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.click(sx, sy, clicks=3, interval=0.08)
                else:
                    pyautogui.click(clicks=3, interval=0.08)
                desc = f"Triple click at ({x}, {y})" if x is not None else "Triple click"
                return {"success": True, "action": action, "description": desc}

            elif action == "mouse_down":
                x = command.get("x")
                y = command.get("y")
                button_map = {1: "left", 3: "right"}
                btn = button_map.get(command.get("button", 1), "left")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.moveTo(sx, sy)
                pyautogui.mouseDown(button=btn)
                return {"success": True, "action": action, "description": f"Mouse down ({btn})"}

            elif action == "mouse_up":
                x = command.get("x")
                y = command.get("y")
                button_map = {1: "left", 3: "right"}
                btn = button_map.get(command.get("button", 1), "left")
                if x is not None and y is not None:
                    sx = x * self._screen_width / 1280
                    sy = y * self._screen_height / 720
                    pyautogui.moveTo(sx, sy)
                pyautogui.mouseUp(button=btn)
                return {"success": True, "action": action, "description": f"Mouse up ({btn})"}

            elif action == "hover":
                x = command.get("x", 0)
                y = command.get("y", 0)
                sx = x * self._screen_width / 1280
                sy = y * self._screen_height / 720
                pyautogui.moveTo(sx, sy)
                return {"success": True, "action": action, "description": f"Hovering at ({x}, {y})"}

            elif action == "select_all":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "a")
                return {"success": True, "action": action, "description": "Selected all"}

            elif action == "copy":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "c")
                return {"success": True, "action": action, "description": "Copied"}

            elif action == "paste":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "v")
                return {"success": True, "action": action, "description": "Pasted"}

            elif action == "cut":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "x")
                return {"success": True, "action": action, "description": "Cut"}

            elif action == "undo":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "z")
                return {"success": True, "action": action, "description": "Undo"}

            elif action == "redo":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "shift", "z")
                return {"success": True, "action": action, "description": "Redo"}

            elif action == "new_tab":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "t")
                return {"success": True, "action": action, "description": "New tab"}

            elif action == "close_tab":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "w")
                return {"success": True, "action": action, "description": "Closed tab"}

            elif action == "switch_tab":
                direction = command.get("direction", "next")
                mod = "command" if self._platform == "Darwin" else "ctrl"
                if direction == "previous":
                    pyautogui.hotkey(mod, "shift", "tab")
                else:
                    pyautogui.hotkey(mod, "tab")
                return {"success": True, "action": action, "description": f"Switched to {direction} tab"}

            elif action == "refresh_page":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "r")
                return {"success": True, "action": action, "description": "Refreshed page"}

            elif action == "go_back":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "[")
                else:
                    pyautogui.hotkey("alt", "left")
                return {"success": True, "action": action, "description": "Back"}

            elif action == "go_forward":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "]")
                else:
                    pyautogui.hotkey("alt", "right")
                return {"success": True, "action": action, "description": "Forward"}

            elif action == "address_bar":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "l")
                import time as _time
                _time.sleep(0.3)
                url = command.get("url")
                if url:
                    pyautogui.typewrite(url, interval=0.02) if url.isascii() else pyautogui.write(url)
                return {"success": True, "action": action, "description": f"Address bar{': ' + url if url else ''}"}

            elif action == "find_in_page":
                text = command.get("text", "")
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "f")
                import time as _time
                _time.sleep(0.3)
                if text:
                    pyautogui.typewrite(text, interval=0.03) if text.isascii() else pyautogui.write(text)
                return {"success": True, "action": action, "description": f"Find: {text}"}

            elif action == "zoom_in":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "=")
                return {"success": True, "action": action, "description": "Zoomed in"}

            elif action == "zoom_out":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "-")
                return {"success": True, "action": action, "description": "Zoomed out"}

            elif action == "zoom_reset":
                mod = "command" if self._platform == "Darwin" else "ctrl"
                pyautogui.hotkey(mod, "0")
                return {"success": True, "action": action, "description": "Zoom reset"}

            elif action == "close_window":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "q")
                else:
                    pyautogui.hotkey("alt", "F4")
                return {"success": True, "action": action, "description": "Closed window"}

            elif action == "minimize_window":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "m")
                else:
                    pyautogui.hotkey("super", "h")
                return {"success": True, "action": action, "description": "Minimized window"}

            elif action == "maximize_window":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "ctrl", "f")
                else:
                    pyautogui.hotkey("super", "up")
                return {"success": True, "action": action, "description": "Maximized window"}

            elif action == "switch_window":
                if self._platform == "Darwin":
                    pyautogui.hotkey("command", "tab")
                else:
                    pyautogui.hotkey("alt", "tab")
                return {"success": True, "action": action, "description": "Switched window"}

            elif action == "take_screenshot":
                return {"success": True, "action": action, "description": "Screenshot requested"}

            else:
                return {"success": False, "action": action, "description": f"Unknown action: {action}"}

        except Exception as e:
            return {"success": False, "action": action, "error": str(e), "description": f"Error: {e}"}

    async def run(self):
        try:
            import websockets
        except ImportError:
            print("Error: websockets package required. Install with: pip install websockets")
            return

        self._running = True
        print(f"AI PC Agent v1.1")
        print(f"Platform: {self._platform}")
        print(f"Screen: {self._screen_width}x{self._screen_height}")
        print(f"Server: {self._server_url}")
        print(f"Code: {self._connection_code}")
        print(f"FPS: {self._fps}")
        print(f"Connecting...")

        retry_delay = 1
        while self._running:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10, max_size=10 * 1024 * 1024) as ws:
                    self._ws = ws
                    retry_delay = 1
                    print("Connected to server!")

                    screen_task = asyncio.create_task(self._send_screen_loop(ws))
                    command_task = asyncio.create_task(self._receive_commands(ws))

                    done, pending = await asyncio.wait(
                        [screen_task, command_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

            except (ConnectionRefusedError, OSError) as e:
                print(f"Connection failed: {e}. Retrying in {retry_delay}s...")
            except Exception as e:
                print(f"Error: {e}. Retrying in {retry_delay}s...")

            if self._running:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)

    async def _send_screen_loop(self, ws):
        interval = 1.0 / self._fps
        while self._running:
            try:
                img_data = self.capture_screen()
                await ws.send(json.dumps({
                    "type": "screen",
                    "image": img_data,
                    "width": 1280,
                    "height": 720,
                    "timestamp": time.time(),
                }))
            except Exception as e:
                print(f"Screen send error: {e}")
                break
            await asyncio.sleep(interval)

    async def _receive_commands(self, ws):
        while self._running:
            try:
                raw = await ws.recv()
                data = json.loads(raw)
                msg_type = data.get("type", "")

                if msg_type == "command":
                    command = data.get("command", {})
                    result = self.execute_command(command)
                    await ws.send(json.dumps({
                        "type": "command_result",
                        "result": result,
                        "command_id": data.get("command_id", ""),
                    }))
                    await asyncio.sleep(0.1)
                    img_data = self.capture_screen()
                    await ws.send(json.dumps({
                        "type": "screen",
                        "image": img_data,
                        "width": 1280,
                        "height": 720,
                        "timestamp": time.time(),
                    }))

                elif msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

            except Exception as e:
                print(f"Command receive error: {e}")
                break

    def stop(self):
        self._running = False
        print("\nAgent stopping...")
