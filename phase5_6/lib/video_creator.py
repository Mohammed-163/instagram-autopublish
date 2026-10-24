"""Render a six-second vertical Reel with a verified Quran verse and local music."""
from __future__ import annotations

import os
import random
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import config


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


class VideoCreator:
    def __init__(self, font_path: str | None = None, music_dir: str | None = None):
        self.quran_font_path = self._find_font(font_path or config.FONT_PATH)
        self.arabic_font_path = self._find_arabic_font()
        self.hook_font_path = self._find_hook_font()
        self.music_dir = music_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "mp3")
        )

    @staticmethod
    def _find_font(preferred: str) -> str:
        if os.path.isfile(preferred):
            return preferred
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "Amiri Quran"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            if result.returncode == 0 and os.path.isfile(result.stdout.strip()):
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        if os.path.isfile(config.FONT_FALLBACK_PATH):
            return config.FONT_FALLBACK_PATH
        raise FileNotFoundError(
            "Amiri Quran font not found. Install fonts-hosny-amiri or set QURAN_FONT_PATH."
        )

    @staticmethod
    def _find_arabic_font() -> str:
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "Noto Sans Arabic"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            matched = result.stdout.strip()
            if result.returncode == 0 and os.path.isfile(matched):
                return matched
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        if os.path.isfile(config.FONT_FALLBACK_PATH):
            return config.FONT_FALLBACK_PATH
        return VideoCreator._find_font(config.FONT_PATH)

    @staticmethod
    def _find_hook_font() -> str:
        """Use an elegant Arabic display face, falling back to the bundled bold font."""
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "Amiri"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            matched = result.stdout.strip()
            if result.returncode == 0 and os.path.isfile(matched):
                return matched
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return config.FONT_FALLBACK_PATH

    def _load_background(self, image_path: str) -> Image.Image:
        img = Image.open(image_path).convert("RGB")
        target_ratio = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
        width, height = img.size
        if width / height > target_ratio:
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img = img.crop((left, 0, left + new_width, height))
        else:
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img = img.crop((0, top, width, top + new_height))
        return img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.Resampling.LANCZOS)

    @staticmethod
    def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
              max_width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font, direction="rtl", language="ar")[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_fit(self, draw: ImageDraw.ImageDraw, text: str, y: int,
                  max_height: int, base_size: int, color: tuple[int, int, int],
                  max_width: int = 920, quranic: bool = False,
                  font_path: str | None = None) -> int:
        font_path = font_path or (self.quran_font_path if quranic else self.arabic_font_path)
        size = base_size
        while size >= 28:
            font = ImageFont.truetype(font_path, size)
            lines = self._wrap(draw, text, font, max_width)
            boxes = [draw.textbbox((0, 0), line, font=font, direction="rtl", language="ar") for line in lines]
            # Keep 1.5-line rhythm, expanding Quranic lines when tall marks need it.
            line_height = max(int(size * 1.5), max((b[3] - b[1] for b in boxes), default=size) + int(size * 0.30))
            if len(lines) * line_height <= max_height:
                break
            size -= 2
        font = ImageFont.truetype(font_path, size)
        lines = self._wrap(draw, text, font, max_width)
        boxes = [draw.textbbox((0, 0), line, font=font, direction="rtl", language="ar") for line in lines]
        line_height = max(int(size * 1.5), max((b[3] - b[1] for b in boxes), default=size) + int(size * 0.30))
        for index, line in enumerate(lines):
            box = boxes[index]
            x = (config.VIDEO_WIDTH - (box[2] - box[0])) // 2
            draw.text((x, y + index * line_height - box[1]), line, font=font, fill=color,
                      direction="rtl", language="ar",
                      stroke_width=0 if quranic else 1, stroke_fill=(255, 248, 235))
        return y + (len(lines) - 1) * line_height + max((b[3] - b[1] for b in boxes), default=size)

    def create_image(self, background_path: str, ayah_text: str, reference: str,
                     explanation: str, output_path: str,
                     hook_line: str = "") -> str:
        img = self._load_background(background_path).convert("RGBA")
        wash = Image.new("RGBA", img.size, (250, 242, 222, int(255 * config.OVERLAY_OPACITY)))
        img = Image.alpha_composite(img, wash).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Soft, translucent panel keeps the photograph visible and the text legible.
        panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((48, 305, config.VIDEO_WIDTH - 48, 1555), radius=42,
                                     fill=(255, 249, 235, 205), outline=(144, 105, 58, 210), width=3)
        img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
        draw = ImageDraw.Draw(img)

        card_bottom = 1555
        y = 355
        if hook_line.strip():
            hook_bottom = self._draw_fit(
                draw, hook_line.strip(), y, 180, 64, _hex_to_rgb("#8C5A27"),
                max_width=900, font_path=self.hook_font_path,
            )
            # Leave breathing room between the hook and the Quranic text.
            y = hook_bottom + 48

        ayah = f"﴿{ayah_text}﴾"
        ayah_max_height = max(300, min(700, card_bottom - y - 500))
        y = self._draw_fit(
            draw, ayah, y, ayah_max_height, 76, _hex_to_rgb("#4E3523"),
            max_width=890, quranic=True,
        )
        ref_font = ImageFont.truetype(self.arabic_font_path, 34)
        ref_text = f"سورة {reference}"
        ref_box = draw.textbbox((0, 0), ref_text, font=ref_font, direction="rtl", language="ar")
        ref_top = y + 38
        draw.text(((config.VIDEO_WIDTH - (ref_box[2] - ref_box[0])) // 2, ref_top - ref_box[1]), ref_text,
                  font=ref_font, fill=_hex_to_rgb("#8C6A3F"), direction="rtl", language="ar")
        ref_bottom = ref_top + (ref_box[3] - ref_box[1])
        divider_y = ref_bottom + 30
        draw.line((190, divider_y, config.VIDEO_WIDTH - 190, divider_y), fill=(176, 137, 83), width=2)
        explanation_y = divider_y + int(42 * 1.5)
        explanation_height = max(150, card_bottom - explanation_y - 35)
        self._draw_fit(
            draw, explanation, explanation_y, explanation_height, 52,
            _hex_to_rgb("#3F342A"), max_width=850,
        )
        img.save(output_path, "PNG")
        return output_path

    def choose_music(self) -> str:
        if not os.path.isdir(self.music_dir):
            raise FileNotFoundError(f"Music folder does not exist: {self.music_dir}")
        choices = sorted(
            os.path.join(self.music_dir, name)
            for name in os.listdir(self.music_dir)
            if name.lower().endswith(".mp3") and os.path.isfile(os.path.join(self.music_dir, name))
        )
        if not choices:
            raise FileNotFoundError(f"Add at least one royalty-cleared .mp3 file to {self.music_dir}")
        return random.choice(choices)

    def image_to_video(self, image_path: str, output_path: str, music_path: str) -> str:
        command = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-stream_loop", "-1", "-i", music_path,
            "-t", str(config.VIDEO_DURATION_SECONDS),
            "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},format=yuv420p",
            "-af", "volume=0.18,afade=t=out:st=5:d=1",
            "-c:v", "libx264", "-preset", "medium", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-shortest", output_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        return output_path

    def build_post_video(self, background_path: str, ayah_text: str, reference: str,
                         explanation: str, workdir: str, output_filename: str,
                         hook_line: str = "") -> tuple[str, str]:
        music_path = self.choose_music()
        image_path = os.path.join(workdir, "temp_frame.png")
        video_path = os.path.join(workdir, output_filename)
        self.create_image(
            background_path, ayah_text, reference, explanation, image_path,
            hook_line=hook_line,
        )
        self.image_to_video(image_path, video_path, music_path)
        for path in (image_path, background_path):
            if os.path.exists(path):
                os.remove(path)
        return video_path, os.path.basename(music_path)
