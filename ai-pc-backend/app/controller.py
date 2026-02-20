import os
import shutil
import subprocess
import time


class PCController:
    def __init__(self):
        self.display = os.environ.get("DISPLAY", ":99")
        self.screen_width = int(os.environ.get("SCREEN_WIDTH", "1280"))
        self.screen_height = int(os.environ.get("SCREEN_HEIGHT", "720"))
        self.has_xdotool = shutil.which("xdotool") is not None
        self.demo_mode = not self.has_xdotool
        self.mouse_x = self.screen_width // 2
        self.mouse_y = self.screen_height // 2

    def _xdotool(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if not self.has_xdotool:
            return subprocess.CompletedProcess(args=["xdotool"] + args, returncode=0, stdout="", stderr="")
        return subprocess.run(
            ["xdotool"] + args,
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "DISPLAY": self.display},
        )

    def execute(self, command: dict) -> dict:
        action = command.get("action", "")
        try:
            handler = getattr(self, f"_action_{action}", None)
            if handler is None:
                return {"success": False, "action": action, "description": f"Unknown action: {action}"}
            return handler(command)
        except Exception as e:
            return {"success": False, "action": action, "error": str(e), "description": f"Error: {e}"}

    def _action_move_mouse(self, cmd: dict) -> dict:
        x = cmd.get("x", 0)
        y = cmd.get("y", 0)
        relative = cmd.get("relative", False)
        if relative:
            self._xdotool(["mousemove_relative", "--", str(x), str(y)])
            desc = f"Moved mouse by ({x}, {y})"
        else:
            self._xdotool(["mousemove", str(x), str(y)])
            desc = f"Moved mouse to ({x}, {y})"
        return {"success": True, "action": "move_mouse", "description": desc}

    def _action_click(self, cmd: dict) -> dict:
        button = cmd.get("button", 1)
        x = cmd.get("x")
        y = cmd.get("y")
        if x is not None and y is not None:
            self._xdotool(["mousemove", str(x), str(y)])
        self._xdotool(["click", str(button)])
        btn_name = {1: "left", 2: "middle", 3: "right"}.get(button, str(button))
        if x is not None and y is not None:
            desc = f"{btn_name} click at ({x}, {y})"
        else:
            desc = f"{btn_name} click"
        return {"success": True, "action": "click", "description": desc}

    def _action_double_click(self, cmd: dict) -> dict:
        x = cmd.get("x")
        y = cmd.get("y")
        if x is not None and y is not None:
            self._xdotool(["mousemove", str(x), str(y)])
        self._xdotool(["click", "--repeat", "2", "--delay", "100", "1"])
        if x is not None and y is not None:
            desc = f"Double click at ({x}, {y})"
        else:
            desc = "Double click"
        return {"success": True, "action": "double_click", "description": desc}

    def _action_right_click(self, cmd: dict) -> dict:
        x = cmd.get("x")
        y = cmd.get("y")
        if x is not None and y is not None:
            self._xdotool(["mousemove", str(x), str(y)])
        self._xdotool(["click", "3"])
        if x is not None and y is not None:
            desc = f"Right click at ({x}, {y})"
        else:
            desc = "Right click"
        return {"success": True, "action": "right_click", "description": desc}

    def _action_drag(self, cmd: dict) -> dict:
        start_x = cmd.get("start_x", 0)
        start_y = cmd.get("start_y", 0)
        end_x = cmd.get("end_x", 0)
        end_y = cmd.get("end_y", 0)
        self._xdotool(["mousemove", str(start_x), str(start_y)])
        self._xdotool(["mousedown", "1"])
        steps = 10
        for i in range(1, steps + 1):
            ix = start_x + (end_x - start_x) * i // steps
            iy = start_y + (end_y - start_y) * i // steps
            self._xdotool(["mousemove", str(ix), str(iy)])
            time.sleep(0.02)
        self._xdotool(["mouseup", "1"])
        desc = f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        return {"success": True, "action": "drag", "description": desc}

    def _action_type_text(self, cmd: dict) -> dict:
        text = cmd.get("text", "")
        self._xdotool(["type", "--clearmodifiers", "--delay", "50", text])
        desc = f"Typed: {text}"
        return {"success": True, "action": "type_text", "description": desc}

    def _action_key_press(self, cmd: dict) -> dict:
        keys = cmd.get("keys", "")
        self._xdotool(["key", "--clearmodifiers", keys])
        desc = f"Pressed: {keys}"
        return {"success": True, "action": "key_press", "description": desc}

    def _action_shortcut(self, cmd: dict) -> dict:
        keys = cmd.get("keys", "")
        self._xdotool(["key", keys])
        desc = f"Shortcut: {keys}"
        return {"success": True, "action": "shortcut", "description": desc}

    def _action_scroll(self, cmd: dict) -> dict:
        direction = cmd.get("direction", "down")
        amount = cmd.get("amount", 3)
        if direction == "up":
            self._xdotool(["click", "--repeat", str(amount), "4"])
        else:
            self._xdotool(["click", "--repeat", str(amount), "5"])
        desc = f"Scrolled {direction} {amount} times"
        return {"success": True, "action": "scroll", "description": desc}

    def _action_get_mouse_position(self, cmd: dict) -> dict:
        result = self._xdotool(["getmouselocation"])
        output = result.stdout.strip()
        desc = f"Mouse position: {output}"
        return {"success": True, "action": "get_mouse_position", "description": desc, "position": output}

    def _action_open_url(self, cmd: dict) -> dict:
        url = cmd.get("url", "")
        if not url:
            return {"success": False, "action": "open_url", "description": "No URL specified"}
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
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
                subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env={**os.environ, "DISPLAY": self.display},
                )
                launched = True
                break
            except FileNotFoundError:
                continue
        if not launched:
            subprocess.Popen(
                f"xdg-open '{url}' &", shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={**os.environ, "DISPLAY": self.display},
            )
        return {"success": True, "action": "open_url", "description": f"Opened URL: {url}"}

    def _action_open_app(self, cmd: dict) -> dict:
        app_name = cmd.get("app_name", "").lower()
        if not app_name:
            return {"success": False, "action": "open_app", "description": "No app name specified"}
        app_commands = {
            "chrome": ["/opt/.devin/chrome/chrome/linux-137.0.7118.2/chrome-linux64/chrome", "--no-sandbox", "--no-first-run", "--user-data-dir=/tmp/chrome-agent"],
            "firefox": ["firefox"],
            "terminal": ["xterm"],
            "notepad": ["xterm", "-e", "nano"],
            "file_manager": ["nautilus", "."],
        }
        cmd_list = app_commands.get(app_name)
        if cmd_list:
            try:
                subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env={**os.environ, "DISPLAY": self.display},
                )
            except FileNotFoundError:
                subprocess.Popen(
                    f"{app_name} &", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env={**os.environ, "DISPLAY": self.display},
                )
        else:
            subprocess.Popen(
                f"{app_name} &", shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={**os.environ, "DISPLAY": self.display},
            )
        return {"success": True, "action": "open_app", "description": f"Opened app: {app_name}"}

    def _action_wait(self, cmd: dict) -> dict:
        seconds = min(float(cmd.get("seconds", 2)), 10)
        time.sleep(seconds)
        return {"success": True, "action": "wait", "description": f"Waited {seconds}s"}

    def _action_run_command(self, cmd: dict) -> dict:
        command = cmd.get("command", "")
        if not command:
            return {"success": False, "action": "run_command", "description": "No command specified"}
        subprocess.Popen(
            command, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "DISPLAY": self.display},
        )
        return {"success": True, "action": "run_command", "description": f"Executed: {command}"}
