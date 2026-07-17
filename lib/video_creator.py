"""
Image + video generation pipeline.

1. Load background, resize/crop to 1080x1920
2. Apply semi-transparent dark overlay for text legibility
3. Draw hook/fact/cta lines with Tajawal ExtraBold using Pillow's native RTL support
4. Export PNG, then convert to a 6-second silent-audio-track MP4 via ffmpeg
5. Delete the intermediate PNG and the raw background image
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import config


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class VideoCreator:
    def __init__(self, font_path: str = config.FONT_PATH):
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font not found at {font_path}")
        self.font_path = font_path

    def _load_background(self, image_path: str) -> Image.Image:
        img = Image.open(image_path).convert("RGB")
        target_ratio = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        return img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.LANCZOS)

    def _apply_overlay(self, img: Image.Image) -> Image.Image:
        overlay = Image.new("RGBA", img.size, config.OVERLAY_COLOR + (int(255 * config.OVERLAY_OPACITY),))
        base = img.convert("RGBA")
        return Image.alpha_composite(base, overlay).convert("RGB")

    def _draw_centered_text(self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
                             color: str, y: int, canvas_width: int) -> int:
        """Draws text centered horizontally at y, wrapping if needed. Returns new y."""
        # استخدام دعم اللغة العربية والاتجاه المدمج في Pillow مباشرة
        bbox = draw.textbbox((0, 0), text, font=font, direction="rtl", language="ar")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (canvas_width - text_w) // 2
        
        # رسم النص مع تحديد الاتجاه واللغة
        draw.text((x, y), text, font=font, fill=_hex_to_rgb(color), direction="rtl", language="ar")
        return y + text_h + 40  # spacing between lines

    def create_image(self, background_path: str, hook: str, fact: str, cta: str, output_path: str) -> str:
        img = self._load_background(background_path)
        img = self._apply_overlay(img)
        draw = ImageDraw.Draw(img)

        font_hook = ImageFont.truetype(self.font_path, config.FONT_SIZE_HOOK)
        font_fact = ImageFont.truetype(self.font_path, config.FONT_SIZE_FACT)
        font_cta = ImageFont.truetype(self.font_path, config.FONT_SIZE_CTA)

        # Vertically center the 3-line block roughly in the middle third
        y = int(config.VIDEO_HEIGHT * 0.38)
        y = self._draw_centered_text(draw, hook, font_hook, config.COLOR_HOOK, y, config.VIDEO_WIDTH)
        y = self._draw_centered_text(draw, fact, font_fact, config.COLOR_FACT, y, config.VIDEO_WIDTH)
        self._draw_centered_text(draw, cta, font_cta, config.COLOR_CTA, y, config.VIDEO_WIDTH)

        img.save(output_path, "PNG")
        return output_path

    def image_to_video(self, image_path: str, output_path: str) -> str:
        """Converts a static PNG into a silent-but-valid-audio-track MP4,
        6 seconds long, vertical, ready for Instagram Reels."""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264",
            "-t", str(config.VIDEO_DURATION_SECONDS),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        return output_path

    def build_post_video(self, background_path: str, hook: str, fact: str, cta: str,
                          workdir: str, output_filename: str) -> str:
        """Full pipeline: background -> image -> video. Cleans up intermediates."""
        image_path = os.path.join(workdir, "temp_frame.png")
        video_path = os.path.join(workdir, output_filename)

        self.create_image(background_path, hook, fact, cta, image_path)
        self.image_to_video(image_path, video_path)

        # cleanup: raw background + intermediate PNG no longer needed
        for path in (image_path, background_path):
            if os.path.exists(path):
                os.remove(path)

        return video_path
