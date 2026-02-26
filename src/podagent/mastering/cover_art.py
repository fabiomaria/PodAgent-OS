"""Cover art processing — resize and compress for podcast platforms."""

from __future__ import annotations

import io
from pathlib import Path

from podagent.utils.progress import log_step, log_warning


def prepare_cover_art(
    path: Path,
    *,
    max_size_px: int = 3000,
    min_size_px: int = 1400,
    max_file_kb: int = 512,
) -> tuple[bytes, str]:
    """Resize and compress cover art to meet podcast platform requirements.

    Apple Podcasts: 1400x1400 minimum, 3000x3000 maximum.
    Returns (image_bytes, mime_type).
    """
    try:
        from PIL import Image
    except ImportError:
        log_warning(
            "Pillow not installed — embedding cover art as-is. "
            "Install with: pip install podagent-os[mastering]"
        )
        data = path.read_bytes()
        mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return data, mime

    img = Image.open(path)
    original_size = f"{img.width}x{img.height}"

    # Ensure square
    if img.width != img.height:
        size = min(img.width, img.height)
        img = img.crop((0, 0, size, size))
        log_step("CoverArt", f"Cropped to square: {size}x{size}")

    # Resize if needed
    if img.width > max_size_px:
        img = img.resize((max_size_px, max_size_px), Image.LANCZOS)
        log_step("CoverArt", f"Resized: {original_size} → {max_size_px}x{max_size_px}")
    elif img.width < min_size_px:
        log_warning(
            f"Cover art is {img.width}x{img.height} — "
            f"below minimum {min_size_px}px. Upscaling."
        )
        img = img.resize((min_size_px, min_size_px), Image.LANCZOS)

    # Compress to JPEG under max file size
    quality = 95
    while quality >= 50:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size_kb = buffer.tell() / 1024
        if size_kb <= max_file_kb:
            log_step("CoverArt", f"Compressed: {size_kb:.0f} KB (quality={quality})")
            return buffer.getvalue(), "image/jpeg"
        quality -= 5

    # Still too large — return at quality 50
    log_warning(f"Cover art is {size_kb:.0f} KB (target: {max_file_kb} KB)")
    return buffer.getvalue(), "image/jpeg"
