from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_SIDE = 1600
JPEG_QUALITY = 88


def normalize_image_for_gemini(image_bytes: bytes) -> tuple[bytes, str, int, int]:
    """Validate and normalize a user-uploaded image for Gemini inline input.

    Returns JPEG bytes, mime type, width and height. Normalizing through Pillow avoids
    browser-specific MIME/file quirks and keeps the payload reasonably small.
    """
    if not image_bytes:
        raise ValueError("Uploaded image is empty")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            width, height = image.size
            if width <= 0 or height <= 0:
                raise ValueError("Uploaded image has invalid dimensions")

            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            output = BytesIO()
            image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return output.getvalue(), "image/jpeg", image.width, image.height
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded file is not a valid image") from exc
    except OSError as exc:
        raise ValueError("The uploaded image could not be decoded") from exc
