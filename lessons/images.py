"""Upload checks for lesson images (SECURITY.md "Input validation").

Pillow decides what a file is; the client's file name and content type are ignored. Every
accepted image is decoded and re-encoded, which drops EXIF (including GPS location) and any
other embedded data.
"""

import io
import warnings

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Pillow format -> stored suffix.
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# Larger than any site photo (a 48 MP phone camera is 48 million pixels); stops
# decompression bombs, i.e. small files that decode to enormous images.
MAX_PIXELS = 64_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def max_upload_bytes():
    return settings.MAX_UPLOAD_MB * 1024 * 1024


def process_image(upload):
    """Return the upload re-encoded as a clean ContentFile, or raise ValidationError."""
    if upload.size > max_upload_bytes():
        raise ValidationError(
            f"Each image must be {settings.MAX_UPLOAD_MB} MB or smaller.", code="too_large"
        )
    try:
        image = _decode(upload)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise ValidationError("Upload a JPEG, PNG or WebP image.", code="invalid_image") from None
    if image.format not in FORMATS:
        raise ValidationError("Upload a JPEG, PNG or WebP image.", code="invalid_image")

    image_format = image.format
    image = ImageOps.exif_transpose(image)  # keep the photo upright once EXIF is gone
    if image_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    out = io.BytesIO()
    # No exif/icc/pnginfo arguments are passed, so none of that metadata is written.
    image.save(out, format=image_format, **({"quality": 90} if image_format != "PNG" else {}))
    return ContentFile(out.getvalue(), name=f"image{FORMATS[image_format]}")


def _decode(upload):
    upload.seek(0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(upload) as probe:
                probe.verify()  # structural check on the raw file
            upload.seek(0)
            image = Image.open(upload)
            image.load()  # full decode: catches truncated data and decompression bombs
        except Image.DecompressionBombWarning:
            raise Image.DecompressionBombError("too many pixels") from None
    return image


def check_image_count(count):
    if count > settings.MAX_IMAGES_PER_LESSON:
        raise ValidationError(
            f"A lesson can have at most {settings.MAX_IMAGES_PER_LESSON} images.",
            code="too_many_images",
        )


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class LessonImagesField(forms.FileField):
    """Accepts several image files and returns them re-encoded, ready to save."""

    widget = MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else [data] if data else []
        if not files:
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return []
        check_image_count(len(files))
        cleaned, errors = [], []
        for upload in files:
            try:
                cleaned.append(process_image(super().clean(upload, initial)))
            except ValidationError as error:
                errors.extend(error.error_list)
        if errors:
            raise ValidationError(errors)
        return cleaned
