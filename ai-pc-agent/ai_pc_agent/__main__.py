import argparse
import asyncio
import signal
import sys
import types

sys.modules['mouseinfo'] = types.ModuleType('mouseinfo')

from ai_pc_agent.agent import PCAgent


def main():
    parser = argparse.ArgumentParser(
        description="AI PC Agent - Connect your Mac to AI PC Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ai_pc_agent --server https://app-dltbojca.fly.dev --code ABC123
  python -m ai_pc_agent -s https://app-dltbojca.fly.dev -c ABC123 --fps 3

Requirements (macOS):
  1. Python 3.10+
  2. pip install mss pyautogui Pillow websockets
  3. Grant Accessibility permission: System Settings > Privacy & Security > Accessibility
  4. Grant Screen Recording permission: System Settings > Privacy & Security > Screen Recording
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
