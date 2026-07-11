"""Image processing engine: resize/crop/align/optimize/validate/preview."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


@dataclass
class ImageIssue:
    code: str
    message: str


class ImageEngine:
    def resize(self, path: Path, output_path: Path, max_width: int, max_height: int) -> Path:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_width, max_height), Image.LANCZOS)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
        return output_path

    def crop_to_aspect(self, path: Path, output_path: Path, target_ratio: float) -> Path:
        with Image.open(path) as image:
            width, height = image.size
            current_ratio = width / height
            if current_ratio > target_ratio:
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                box = (left, 0, left + new_width, height)
            else:
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                box = (0, top, width, top + new_height)
            cropped = image.crop(box)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(output_path)
        return output_path

    def align_center(self, path: Path, output_path: Path, canvas_size: tuple[int, int]) -> Path:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(canvas_size, Image.LANCZOS)
            canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
            offset = ((canvas_size[0] - image.width) // 2, (canvas_size[1] - image.height) // 2)
            canvas.paste(image, offset)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.convert("RGB").save(output_path)
        return output_path

    def optimize(self, path: Path, output_path: Path, quality: int = 85) -> Path:
        with Image.open(path) as image:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, optimize=True, quality=quality)
        return output_path

    def generate_preview(self, path: Path, output_path: Path, size: tuple[int, int] = (320, 320)) -> Path:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(size, Image.LANCZOS)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(output_path, format="JPEG", quality=80)
        return output_path

    def validate(
        self, path: Path, min_width: int = 200, min_height: int = 200, min_dpi: int = 72
    ) -> list[ImageIssue]:
        issues: list[ImageIssue] = []
        try:
            with Image.open(path) as image:
                width, height = image.size
                if width < min_width or height < min_height:
                    issues.append(
                        ImageIssue(
                            "too_small",
                            f"Image {width}x{height} is below minimum {min_width}x{min_height}",
                        )
                    )
                dpi = image.info.get("dpi", (72, 72))
                if dpi and dpi[0] < min_dpi:
                    issues.append(ImageIssue("low_dpi", f"Image DPI {dpi[0]} below minimum {min_dpi}"))
        except Exception as exc:
            issues.append(ImageIssue("unreadable", f"Could not open image: {exc}"))
        return issues
