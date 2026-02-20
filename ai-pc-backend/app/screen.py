import base64
import io
import os
import subprocess


class ScreenCapture:
    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

    def capture_base64(self) -> str:
        try:
            display = os.environ.get("DISPLAY", ":99")
            result = subprocess.run(
                [
                    "import",
                    "-window", "root",
                    "-resize", f"{self.width}x{self.height}",
                    "-quality", "60",
                    "png:-",
                ],
                capture_output=True,
                timeout=5,
                env={**os.environ, "DISPLAY": display},
            )
            if result.returncode == 0 and result.stdout:
                return base64.b64encode(result.stdout).decode("utf-8")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            return self._capture_with_xwd()
        except Exception:
            pass

        return self._generate_placeholder()

    def _capture_with_xwd(self) -> str:
        display = os.environ.get("DISPLAY", ":99")
        xwd_result = subprocess.run(
            ["xwd", "-root", "-silent"],
            capture_output=True,
            timeout=5,
            env={**os.environ, "DISPLAY": display},
        )
        if xwd_result.returncode != 0:
            raise RuntimeError("xwd capture failed")

        convert_result = subprocess.run(
            ["convert", "xwd:-", "-resize", f"{self.width}x{self.height}", "-quality", "60", "png:-"],
            input=xwd_result.stdout,
            capture_output=True,
            timeout=5,
        )
        if convert_result.returncode == 0 and convert_result.stdout:
            return base64.b64encode(convert_result.stdout).decode("utf-8")
        raise RuntimeError("convert failed")

    def _generate_placeholder(self) -> str:
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (self.width, self.height), color=(30, 30, 46))
            draw = ImageDraw.Draw(img)
            text = "AI PC Controller - Virtual Desktop"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except (OSError, IOError):
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (self.width - text_width) // 2
            y = (self.height - text_height) // 2
            draw.text((x, y), text, fill=(205, 214, 244), font=font)
            draw.text((x, y + 40), "Waiting for display...", fill=(147, 153, 178), font=font)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except ImportError:
            return ""
