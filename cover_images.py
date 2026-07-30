"""Secure cover-image normalization and filesystem storage helpers."""

from __future__ import annotations

import base64
import binascii
import os
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
THUMBNAIL_MAX_EDGE = 640
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}


class CoverImageError(ValueError):
    """A reader-facing cover validation error."""


@dataclass(frozen=True)
class CoverAsset:
    full_bytes: bytes
    thumbnail_bytes: bytes
    extension: str
    mime_type: str
    width: int
    height: int


def _save_image(image: Image.Image, image_format: str) -> tuple[bytes, str, str]:
    output = BytesIO()
    if image_format == "JPEG":
        if image.mode not in ("RGB", "L"):
            if "A" in image.getbands():
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
        image.save(output, "JPEG", quality=90, optimize=True)
        return output.getvalue(), "jpg", "image/jpeg"
    if image_format == "PNG":
        if image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        image.save(output, "PNG", optimize=True)
        return output.getvalue(), "png", "image/png"

    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    image.save(output, "WEBP", quality=90, method=6)
    return output.getvalue(), "webp", "image/webp"


def normalize_cover(raw: bytes) -> CoverAsset:
    """Validate and normalize one JPEG, PNG, or static WebP cover."""
    if not raw:
        raise CoverImageError("图片上传失败：图片不能为空")
    if len(raw) > MAX_IMAGE_SIZE:
        raise CoverImageError("图片上传失败：文件大小不能超过 5MB")

    try:
        with Image.open(BytesIO(raw)) as opened:
            image_format = (opened.format or "").upper()
            if image_format not in SUPPORTED_FORMATS:
                raise CoverImageError("图片上传失败：仅支持 jpg/jpeg/png/webp 格式")
            if getattr(opened, "n_frames", 1) > 1 or getattr(opened, "is_animated", False):
                raise CoverImageError("图片上传失败：暂不支持动画 WebP")
            width, height = opened.size
            if width <= 0 or height <= 0:
                raise CoverImageError("图片上传失败：图片尺寸无效")
            if width * height > MAX_IMAGE_PIXELS:
                raise CoverImageError("图片上传失败：图片像素不能超过 4000 万")

            opened.load()
            normalized = ImageOps.exif_transpose(opened)
            normalized.load()
            width, height = normalized.size

            full_bytes, extension, mime_type = _save_image(normalized, image_format)
            thumbnail = normalized.copy()
            thumbnail.thumbnail(
                (THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE),
                Image.Resampling.LANCZOS,
            )
            thumb_output = BytesIO()
            thumb_mode = "RGBA" if "A" in thumbnail.getbands() else "RGB"
            thumbnail.convert(thumb_mode).save(
                thumb_output,
                "WEBP",
                quality=86,
                method=6,
            )
    except CoverImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise CoverImageError("图片上传失败：图片文件已损坏或格式无效") from exc

    return CoverAsset(
        full_bytes=full_bytes,
        thumbnail_bytes=thumb_output.getvalue(),
        extension=extension,
        mime_type=mime_type,
        width=width,
        height=height,
    )


def read_limited(stream) -> bytes:
    """Read at most 5MB + 1 byte so oversized uploads never enter validation."""
    raw = stream.read(MAX_IMAGE_SIZE + 1)
    if len(raw) > MAX_IMAGE_SIZE:
        raise CoverImageError("图片上传失败：文件大小不能超过 5MB")
    return raw


def decode_data_url(data_url: str) -> bytes:
    if not data_url or not isinstance(data_url, str):
        raise CoverImageError("导入失败：封面图片数据无效")
    prefix, separator, payload = data_url.partition(",")
    if not separator or ";base64" not in prefix.lower():
        raise CoverImageError("导入失败：封面图片数据无效")
    try:
        return base64.b64decode("".join(payload.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CoverImageError("导入失败：封面图片 Base64 无效") from exc


def encode_data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def ensure_cover_dir(cover_dir: str) -> None:
    os.makedirs(cover_dir, exist_ok=True)


def _atomic_write(directory: str, filename: str, payload: bytes) -> None:
    ensure_cover_dir(directory)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=".cover-",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, os.path.join(directory, filename))
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def store_cover(asset: CoverAsset, cover_dir: str) -> dict:
    token = uuid.uuid4().hex
    filename = f"{token}.{asset.extension}"
    thumbnail_filename = f"{token}.thumb.webp"
    written: list[str] = []
    try:
        _atomic_write(cover_dir, filename, asset.full_bytes)
        written.append(filename)
        _atomic_write(cover_dir, thumbnail_filename, asset.thumbnail_bytes)
        written.append(thumbnail_filename)
    except Exception:
        delete_cover_files(cover_dir, written)
        raise
    return {
        "cover_file": filename,
        "cover_thumb": thumbnail_filename,
        "cover_mime": asset.mime_type,
        "cover_width": asset.width,
        "cover_height": asset.height,
    }


def resolve_cover_path(cover_dir: str, filename: str | None) -> str | None:
    if not filename or os.path.basename(filename) != filename:
        return None
    root = Path(cover_dir).resolve()
    candidate = (root / filename).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return str(candidate)


def delete_cover_files(cover_dir: str, filenames) -> None:
    for filename in filenames:
        path = resolve_cover_path(cover_dir, filename)
        if not path:
            continue
        try:
            os.unlink(path)
        except OSError:
            pass


def remove_unreferenced_files(cover_dir: str, referenced: set[str]) -> None:
    if not os.path.isdir(cover_dir):
        return
    for entry in os.scandir(cover_dir):
        if entry.is_file() and not entry.name.startswith(".") and entry.name not in referenced:
            delete_cover_files(cover_dir, [entry.name])
