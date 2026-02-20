from setuptools import setup, find_packages

setup(
    name="ai-pc-agent",
    version="1.0.0",
    description="AI PC Agent - Connect your Mac to AI PC Controller",
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
