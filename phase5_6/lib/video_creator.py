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
        self.font_path = self._find_font(font_path or config.FONT_PATH)
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
            box = draw.textbbox((0, 0), candidate, font=font, direction="rtl", language="ar")
            if box[2] - box[0] <= max_width:
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
                  max_width: int = 920, min_size: int = 26,
                  quranic: bool = False) -> int:
        size = base_size
        line_layout = []
        while True:
            font = ImageFont.truetype(self.font_path, size)
            lines = self._wrap(draw, text, font, max_width)
            line_layout = []
            for line in lines:
                box = draw.textbbox((0, 0), line, font=font, direction="rtl", language="ar")
                ink_height = max(1, box[3] - box[1])
                line_step = max(int(size * (1.8 if quranic else 1.6)), ink_height + int(size * 0.42))
                line_layout.append((line, box, line_step))
            total_height = sum(step for _, _, step in line_layout)
            if total_height <= max_height or size <= min_size:
                break
            size = max(min_size, size - 2)
        font = ImageFont.truetype(self.font_path, size)

        cursor_y = y
        for line, box, line_step in line_layout:
            text_width = box[2] - box[0]
            x = (config.VIDEO_WIDTH - text_width) // 2 - box[0]
            # Extra leading protects Quranic marks from colliding with the line above.
            draw_y = cursor_y - box[1]
            draw.text((x, draw_y), line, font=font, fill=color,
                      direction="rtl", language="ar",
                      stroke_width=0 if quranic else 1,
                      stroke_fill=(255, 248, 235))
            cursor_y += line_step
        return cursor_y

    @staticmethod
    def _arabic_digits(value: str) -> str:
        return str(value).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))

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
        panel_draw.rounded_rectangle((48, 215, config.VIDEO_WIDTH - 48, 1705), radius=42,
                                     fill=(255, 249, 235, 205), outline=(144, 105, 58, 210), width=3)
        img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
        draw = ImageDraw.Draw(img)

        content_top = 292
        card_bottom = 1618
        y = content_top

        if hook_line.strip():
            y = self._draw_fit(
                draw, hook_line.strip(), y, 118, 44,
                _hex_to_rgb("#765333"), max_width=870, min_size=30,
            )
            y += 26

        ayah = f"﴿{ayah_text}﴾"
        y = self._draw_fit(
            draw, ayah, y, 620, 70, _hex_to_rgb("#4E3523"),
            max_width=890, min_size=42, quranic=True,
        )

        # Put the surah and ayah number directly under the verse, then keep
        # the divider clearly below that label (the old line crossed it).
        ref_text = reference.strip()
        ref_font = ImageFont.truetype(self.font_path, 36)
        ref_box = draw.textbbox((0, 0), ref_text, font=ref_font, direction="rtl", language="ar")
        ref_width = ref_box[2] - ref_box[0]
        ref_x = (config.VIDEO_WIDTH - ref_width) // 2 - ref_box[0]
        ref_y = y + 28
        draw.text((ref_x, ref_y - ref_box[1]), ref_text, font=ref_font,
                  fill=_hex_to_rgb("#8C6A3F"), direction="rtl", language="ar")

        divider_y = ref_y + (ref_box[3] - ref_box[1]) + 54
        draw.line((190, divider_y, config.VIDEO_WIDTH - 190, divider_y),
                  fill=(176, 137, 83), width=2)

        explanation_y = divider_y + 58
        explanation_height = max(170, card_bottom - explanation_y)
        self._draw_fit(
            draw, explanation, explanation_y, explanation_height, 42,
            _hex_to_rgb("#3F342A"), max_width=850, min_size=26,
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
        self.create_image(background_path, ayah_text, reference, explanation,
                          image_path, hook_line=hook_line)
        self.image_to_video(image_path, video_path, music_path)
        for path in (image_path, background_path):
            if os.path.exists(path):
                os.remove(path)
        return video_path, os.path.basename(music_path)
