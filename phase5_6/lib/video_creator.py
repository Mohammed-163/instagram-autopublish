"""
Image + video generation pipeline.

1. Load background, resize/crop to 1080x1920
2. Apply semi-transparent dark overlay for text legibility
3. Draw hook/fact/cta lines with Tajawal ExtraBold using Pillow's native RTL support (with auto word-wrap)
4. Export PNG, then convert to a 6-second silent-audio-track MP4 via ffmpeg
5. Delete the intermediate PNG and the raw background image
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import config
from . import music_client


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
        """Draws text centered horizontally at y, wrapping into multiple lines if needed. Returns new y."""
        
        # حساب العرض الأقصى المسموح به للنص (نترك هامش 100 بكسل من كل جانب لضمان عدم اقترابه من حواف الشاشة)
        max_width = canvas_width - 200
        
        words = text.split()
        lines = []
        current_line = []

        # خوارزمية تقسيم النص إلى أسطر بناءً على العرض الفعلي للكلمات
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font, direction="rtl", language="ar")
            text_w = bbox[2] - bbox[0]
            
            if text_w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        if current_line:
            lines.append(' '.join(current_line))

        # رسم الأسطر بشكل متتالي
        line_spacing = 20  # المسافة بين الأسطر التابعة لنفس الجملة
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, direction="rtl", language="ar")
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (canvas_width - text_w) // 2
            
            draw.text((x, y), line, font=font, fill=_hex_to_rgb(color), direction="rtl", language="ar")
            y += text_h + line_spacing

        return y + 40  # المسافة الكبيرة بين الفقرات المختلفة (مثل المسافة بين الحقيقة العلمية ودعوة الحفظ)

    def create_image(self, background_path: str, hook: str, fact: str, cta: str, output_path: str) -> str:
        img = self._load_background(background_path)
        img = self._apply_overlay(img)
        draw = ImageDraw.Draw(img)

        font_hook = ImageFont.truetype(self.font_path, config.FONT_SIZE_HOOK)
        font_fact = ImageFont.truetype(self.font_path, config.FONT_SIZE_FACT)
        font_cta = ImageFont.truetype(self.font_path, config.FONT_SIZE_CTA)

        # تم رفع النص قليلاً للأعلى (0.32 بدلاً من 0.38) لكي يتسع براحة في حال كانت الأسطر كثيرة
        y = int(config.VIDEO_HEIGHT * 0.32)
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

    def _get_video_resolution(self, video_path: str) -> tuple:
        """يرجع (width, height) للفيديو عبر ffprobe. يرمي استثناء عند الفشل."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        w_str, h_str = result.stdout.strip().split("x")
        return int(w_str), int(h_str)

    def create_transparent_text_layer(self, lines: list, font_sizes: list, colors: list,
                                      output_path: str, start_y: int = None) -> str:
        """
        يرسم مجموعة أسطر نصية على خلفية شفافة بالكامل.
        start_y: نقطة البداية العمودية بالبكسل. إن كانت None، يُستخدم الافتراضي 0.32 من الارتفاع
        (نفس سلوك create_image الأصلي، للحفاظ على التوافق مع الاستخدامات القديمة).
        يُرجع الدالة الآن (output_path, ending_y) بدل output_path فقط، حيث ending_y هو
        الموضع العمودي بعد آخر سطر مرسوم، لتمرير هذه القيمة كـ start_y لطبقة تالية.
        """
        img = Image.new("RGBA", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        y = start_y if start_y is not None else int(config.VIDEO_HEIGHT * 0.32)
        for text, size, color in zip(lines, font_sizes, colors):
            if not text:
                continue
            font = ImageFont.truetype(self.font_path, size)
            y = self._draw_centered_text(draw, text, font, color, y, config.VIDEO_WIDTH)

        img.save(output_path, "PNG")
        return output_path, y

    def build_post_video_from_video_bg(self, video_bg_path: str, hook: str, fact: str, cta: str,
                                        workdir: str, output_filename: str) -> str:
        """
        مسار بديل كامل: خلفية فيديو خام حقيقية بدل صورة ثابتة، مع طبقتي نص متلاشيتين
        (الهوك أولاً، ثم fact+cta معاً) وموسيقى حقيقية بدل anullsrc.
        يرمي استثناء عند أي مشكلة تقنية (دقة غير كافية، فشل ffmpeg) ليتراجع المستدعي
        تلقائياً لمسار الصور القديم (fail-open على مستوى daily_generate.py).
        """
        width, height = self._get_video_resolution(video_bg_path)
        if height < config.MIN_VIDEO_HEIGHT_FOR_PUBLISH:
            raise RuntimeError(
                f"Video background resolution too low: {width}x{height}, "
                f"minimum height required is {config.MIN_VIDEO_HEIGHT_FOR_PUBLISH}"
            )

        hook_overlay_path = os.path.join(workdir, "hook_overlay.png")
        rest_overlay_path = os.path.join(workdir, "rest_overlay.png")
        output_path = os.path.join(workdir, output_filename)

        _, hook_end_y = self.create_transparent_text_layer(
            lines=[hook],
            font_sizes=[config.FONT_SIZE_HOOK],
            colors=[config.COLOR_HOOK],
            output_path=hook_overlay_path,
        )
        self.create_transparent_text_layer(
            lines=[fact, cta],
            font_sizes=[config.FONT_SIZE_FACT, config.FONT_SIZE_CTA],
            colors=[config.COLOR_FACT, config.COLOR_CTA],
            output_path=rest_overlay_path,
            start_y=hook_end_y,
        )

        music_path = music_client.get_random_instrumental_track(workdir)

        filter_complex = (
            f"[0:v]scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}[bg];"
            f"[1:v]fade=in:st=0:d=0.8:alpha=1[hook_faded];"
            f"[2:v]fade=in:st=1.5:d=0.8:alpha=1[rest_faded];"
            f"[bg][hook_faded]overlay=0:0[v1];"
            f"[v1][rest_faded]overlay=0:0[vout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_bg_path,
            "-loop", "1", "-i", hook_overlay_path,
            "-loop", "1", "-i", rest_overlay_path,
        ]

        if music_path:
            cmd += ["-i", music_path]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "3:a",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-t", str(config.VIDEO_DURATION_SECONDS),
            "-shortest",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        for path in (hook_overlay_path, rest_overlay_path, music_path, video_bg_path):
            if path and os.path.exists(path):
                os.remove(path)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (video bg pipeline): {result.stderr}")

        return output_path
