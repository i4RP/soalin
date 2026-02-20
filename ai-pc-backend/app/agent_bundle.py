AGENT_INIT = '"""AI PC Agent - Run on your Mac/Windows/Linux to allow remote control via AI PC Controller."""\n__version__ = "1.1.0"\n'

AGENT_MAIN = r'''import argparse
import asyncio
import signal
import sys

from ai_pc_agent.agent import PCAgent


def main():
    parser = argparse.ArgumentParser(
        description="AI PC Agent - Connect your PC to AI PC Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ai_pc_agent --server https://app-dltbojca.fly.dev --code ABC123
  python -m ai_pc_agent -s https://app-dltbojca.fly.dev -c ABC123 --fps 3

Supported Platforms: macOS, Windows, Linux

Requirements:
  1. Python 3.10+
  2. pip install mss pyautogui Pillow websockets
  3. macOS: Grant Accessibility + Screen Recording permissions
  4. Linux: Install python3-tk python3-dev (apt) or python3-tkinter (dnf)
        """,
    )
    parser.add_argument("-s", "--server", required=True, help="Server URL (e.g. https://app-dltbojca.fly.dev)")
    parser.add_argument("-c", "--code", required=True, help="6-digit connection code from the app")
    parser.add_argument("--fps", type=int, default=2, help="Screen capture FPS (default: 2)")

    args = parser.parse_args()

    agent = PCAgent(
        server_url=args.server,
        connection_code=args.code,
        fps=args.fps,
    )

    def handle_signal(sig, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("=" * 50)
    print("  AI PC Agent")
    print("=" * 50)
    print()

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
'''

AGENT_PY = r'''import asyncio
import base64
import io
import json
import platform
import signal
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

            elif action == "get_mouse_position":
                pos = pyautogui.position()
                nx = int(pos[0] * 1280 / self._screen_width)
                ny = int(pos[1] * 720 / self._screen_height)
                return {"success": True, "action": action, "description": f"Mouse position: ({nx}, {ny})", "position": f"x:{nx} y:{ny}"}

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
'''

REQUIREMENTS_TXT = "mss>=9.0.0\npyautogui>=0.9.54\nPillow>=10.0.0\nwebsockets>=12.0\n"

SETUP_PY = r'''from setuptools import setup, find_packages

setup(
    name="ai-pc-agent",
    version="1.1.0",
    description="AI PC Agent - Connect your Mac/Windows/Linux to AI PC Controller",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "mss>=9.0.0",
        "pyautogui>=0.9.54",
        "Pillow>=10.0.0",
        "websockets>=12.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-pc-agent=ai_pc_agent.__main__:main",
        ],
    },
)
'''

README_MD = r'''# AI PC Agent

PC上で実行するエージェント。AI PC Controllerからリモートでマウス・キーボード操作が可能になります。
macOS / Windows / Linux に対応しています。

---

## macOS セットアップ

### 方法1: ワンクリック
1. zipを解凍
2. `install_mac.command` をダブルクリック（依存パッケージの自動インストール）
3. macOS権限を許可:
   - システム設定 > プライバシーとセキュリティ > **アクセシビリティ** → ターミナルを許可
   - システム設定 > プライバシーとセキュリティ > **画面収録** → ターミナルを許可
4. `run_mac.command` をダブルクリック → 接続コードを入力

### 方法2: コマンド
```bash
pip3 install -r requirements.txt
python3 -m ai_pc_agent -s https://app-dltbojca.fly.dev -c YOUR_CODE
```

---

## Windows セットアップ

### 方法1: ワンクリック
1. zipを解凍
2. `install_windows.bat` をダブルクリック（依存パッケージの自動インストール）
3. `run_windows.bat` をダブルクリック → 接続コードを入力

### 方法2: コマンド
```cmd
pip install -r requirements.txt
python -m ai_pc_agent -s https://app-dltbojca.fly.dev -c YOUR_CODE
```

---

## Linux セットアップ

### 方法1: スクリプト
1. zipを解凍
2. ターミナルで:
```bash
chmod +x install_linux.sh run_linux.sh
./install_linux.sh
./run_linux.sh
```

### 方法2: コマンド
```bash
sudo apt install python3-tk python3-dev  # Ubuntu/Debian
pip3 install -r requirements.txt
python3 -m ai_pc_agent -s https://app-dltbojca.fly.dev -c YOUR_CODE
```

---

## オプション
- `--fps 3` - 画面キャプチャのFPS（デフォルト: 2）
- `-s` / `--server` - サーバーURL
- `-c` / `--code` - 接続コード
'''

INSTALL_MAC = r'''#!/bin/bash
cd "$(dirname "$0")"
echo "=================================="
echo "  AI PC Agent - macOS Installer"
echo "=================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Python3 が見つかりません。"
    echo "Homebrew でインストールしてください: brew install python@3.12"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python3 found: $(python3 --version)"
echo ""
echo "依存パッケージをインストール中..."
python3 -m pip install --user -r requirements.txt
echo ""
echo "=================================="
echo "  インストール完了！"
echo "=================================="
echo ""
echo "次のステップ:"
echo "  1. macOS の システム設定 > プライバシーとセキュリティ で"
echo "     アクセシビリティ と 画面収録 の権限をターミナルに許可してください"
echo ""
echo "  2. アプリの Settings 画面で接続コードを確認してください"
echo ""
echo "  3. run_mac.command をダブルクリックしてエージェントを起動してください"
echo ""
read -p "Press Enter to exit..."
'''

RUN_MAC = r'''#!/bin/bash
cd "$(dirname "$0")"
echo "=================================="
echo "  AI PC Agent (macOS)"
echo "=================================="
echo ""

SERVER="https://app-dltbojca.fly.dev"

read -p "接続コードを入力してください: " CODE

if [ -z "$CODE" ]; then
    echo "接続コードが入力されていません"
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "サーバー: $SERVER"
echo "接続コード: $CODE"
echo ""
echo "接続中... (Ctrl+C で終了)"
echo ""

python3 -m ai_pc_agent -s "$SERVER" -c "$CODE"

echo ""
read -p "Press Enter to exit..."
'''

INSTALL_WINDOWS = r'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================
echo   AI PC Agent - Windows Installer
echo ==================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python が見つかりません。
    echo https://www.python.org/downloads/ からインストールしてください。
    echo インストール時に「Add Python to PATH」にチェックを入れてください。
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo %%i
echo.
echo 依存パッケージをインストール中...
python -m pip install -r requirements.txt
echo.
echo ==================================
echo   インストール完了！
echo ==================================
echo.
echo 次のステップ:
echo   1. アプリの Settings 画面で接続コードを確認してください
echo   2. run_windows.bat をダブルクリックしてエージェントを起動してください
echo.
pause
'''

RUN_WINDOWS = r'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================
echo   AI PC Agent (Windows)
echo ==================================
echo.

set SERVER=https://app-dltbojca.fly.dev

set /p CODE="接続コードを入力してください: "

if "%CODE%"=="" (
    echo 接続コードが入力されていません
    pause
    exit /b 1
)

echo.
echo サーバー: %SERVER%
echo 接続コード: %CODE%
echo.
echo 接続中... (Ctrl+C で終了)
echo.

python -m ai_pc_agent -s "%SERVER%" -c "%CODE%"

echo.
pause
'''

INSTALL_LINUX = r'''#!/bin/bash
cd "$(dirname "$0")"
echo "=================================="
echo "  AI PC Agent - Linux Installer"
echo "=================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Python3 が見つかりません。"
    echo "インストールしてください:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-tk python3-dev"
    echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip python3-tkinter"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python3 found: $(python3 --version)"
echo ""

if command -v apt &> /dev/null; then
    echo "システムパッケージをインストール中 (sudo が必要な場合があります)..."
    sudo apt install -y python3-tk python3-dev 2>/dev/null || echo "python3-tk のインストールをスキップ (手動でインストールしてください)"
    echo ""
elif command -v dnf &> /dev/null; then
    echo "システムパッケージをインストール中 (sudo が必要な場合があります)..."
    sudo dnf install -y python3-tkinter 2>/dev/null || echo "python3-tkinter のインストールをスキップ (手動でインストールしてください)"
    echo ""
fi

echo "Python パッケージをインストール中..."
python3 -m pip install --user -r requirements.txt
echo ""
echo "=================================="
echo "  インストール完了！"
echo "=================================="
echo ""
echo "次のステップ:"
echo "  1. アプリの Settings 画面で接続コードを確認してください"
echo "  2. ./run_linux.sh を実行してエージェントを起動してください"
echo ""
read -p "Press Enter to exit..."
'''

RUN_LINUX = r'''#!/bin/bash
cd "$(dirname "$0")"
echo "=================================="
echo "  AI PC Agent (Linux)"
echo "=================================="
echo ""

SERVER="https://app-dltbojca.fly.dev"

read -p "接続コードを入力してください: " CODE

if [ -z "$CODE" ]; then
    echo "接続コードが入力されていません"
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "サーバー: $SERVER"
echo "接続コード: $CODE"
echo ""
echo "接続中... (Ctrl+C で終了)"
echo ""

python3 -m ai_pc_agent -s "$SERVER" -c "$CODE"

echo ""
read -p "Press Enter to exit..."
'''


def get_agent_files() -> dict[str, str]:
    return {
        "ai-pc-agent/ai_pc_agent/__init__.py": AGENT_INIT,
        "ai-pc-agent/ai_pc_agent/agent.py": AGENT_PY,
        "ai-pc-agent/ai_pc_agent/__main__.py": AGENT_MAIN,
        "ai-pc-agent/requirements.txt": REQUIREMENTS_TXT,
        "ai-pc-agent/setup.py": SETUP_PY,
        "ai-pc-agent/README.md": README_MD,
        "ai-pc-agent/install_mac.command": INSTALL_MAC,
        "ai-pc-agent/run_mac.command": RUN_MAC,
        "ai-pc-agent/install_windows.bat": INSTALL_WINDOWS,
        "ai-pc-agent/run_windows.bat": RUN_WINDOWS,
        "ai-pc-agent/install_linux.sh": INSTALL_LINUX,
        "ai-pc-agent/run_linux.sh": RUN_LINUX,
    }
