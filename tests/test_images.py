"""Safe image upload processing (REQ-MEDIA-001)."""

import io
import stat

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import ExifTags, Image

from lessons.images import LessonImagesField, process_image
from lessons.models import LessonImage


def make_image(fmt="JPEG", size=(64, 48), mode="RGB", exif=None, name=None):
    buffer = io.BytesIO()
    extra = {"exif": exif} if exif is not None else {}
    Image.new(mode, size, "red").save(buffer, format=fmt, **extra)
    suffix = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "BMP": "bmp"}[fmt]
    return SimpleUploadedFile(name or f"photo.{suffix}", buffer.getvalue())


def gps_exif():
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "SiteCam"
    exif[ExifTags.Base.Orientation] = 6  # rotated 90 degrees
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (43.0, 39.0, 12.0)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (79.0, 23.0, 1.0)
    return exif


# AC-01: valid images are re-encoded, named by UUID, and stripped of EXIF/GPS.


@pytest.mark.parametrize(("fmt", "suffix"), [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")])
def test_valid_images_accepted_and_reencoded(fmt, suffix):
    upload = make_image(fmt)
    cleaned = process_image(upload)
    assert cleaned.name == f"image{suffix}"
    assert cleaned.read() != upload.read()  # new bytes, not the original
    cleaned.seek(0)
    assert Image.open(cleaned).format == fmt


def test_exif_and_gps_removed():
    upload = make_image(exif=gps_exif())
    with Image.open(io.BytesIO(upload.read())) as original:
        assert original.getexif().get_ifd(ExifTags.IFD.GPSInfo)  # the fixture really has GPS
    cleaned = process_image(upload)
    data = cleaned.read()
    with Image.open(io.BytesIO(data)) as image:
        assert not image.getexif()
        assert image.size == (48, 64)  # orientation applied before EXIF was dropped
    assert b"Exif" not in data
    assert b"SiteCam" not in data


@pytest.mark.django_db
def test_saved_file_has_uuid_name_and_no_execute_bit(make_lesson, media_root):
    image = LessonImage.objects.create(
        lesson=make_lesson(), kind=LessonImage.Kind.FAILED, file=process_image(make_image())
    )
    assert image.file.name.endswith(".jpg") and "photo" not in image.file.name
    mode = (media_root / image.file.name).stat().st_mode
    assert not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert stat.S_IMODE(mode) == 0o640


# AC-02: non-images are rejected, whatever their name says.


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("photo.jpg", b"<?php system($_GET['c']); ?>"),
        SimpleUploadedFile("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40),  # broken PNG
        SimpleUploadedFile("photo.jpg", b""),
    ],
)
def test_non_images_rejected(upload):
    with pytest.raises(ValidationError, match="JPEG, PNG or WebP"):
        process_image(upload)


@pytest.mark.parametrize("fmt", ["GIF", "BMP"])
def test_other_image_formats_rejected(fmt):
    with pytest.raises(ValidationError, match="JPEG, PNG or WebP"):
        process_image(make_image(fmt, name="photo.jpg"))


def test_truncated_jpeg_rejected():
    data = make_image(size=(400, 300)).read()
    with pytest.raises(ValidationError):
        process_image(SimpleUploadedFile("photo.jpg", data[: len(data) // 2]))


# AC-03: files over MAX_UPLOAD_MB are rejected; Django's limits come from the env.


@override_settings(MAX_UPLOAD_MB=1)
def test_file_over_size_limit_rejected():
    upload = SimpleUploadedFile("big.jpg", b"\xff\xd8" + b"0" * (1024 * 1024))
    with pytest.raises(ValidationError, match="1 MB or smaller"):
        process_image(upload)


def test_django_upload_settings_follow_env(settings):
    assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE == settings.MAX_UPLOAD_MB * 1024 * 1024
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES == settings.MAX_IMAGES_PER_LESSON


# AC-04: more than MAX_IMAGES_PER_LESSON images are rejected.


class ImagesForm(forms.Form):
    images = LessonImagesField()


@override_settings(MAX_IMAGES_PER_LESSON=2)
def test_too_many_images_rejected():
    form = ImagesForm(files={"images": [make_image() for _ in range(3)]})
    assert not form.is_valid()
    assert "at most 2 images" in str(form.errors)


@override_settings(MAX_IMAGES_PER_LESSON=2)
def test_images_field_returns_cleaned_files():
    from django.utils.datastructures import MultiValueDict

    form = ImagesForm(files=MultiValueDict({"images": [make_image(), make_image("PNG")]}))
    assert form.is_valid(), form.errors
    assert [f.name for f in form.cleaned_data["images"]] == ["image.jpg", "image.png"]


def test_images_field_collects_errors_per_file():
    from django.utils.datastructures import MultiValueDict

    bad = SimpleUploadedFile("x.jpg", b"nope")
    form = ImagesForm(files=MultiValueDict({"images": [make_image(), bad]}))
    assert not form.is_valid()
    assert "JPEG, PNG or WebP" in str(form.errors)


def test_images_field_required_and_optional():
    assert not ImagesForm(files={}).is_valid()

    class Optional(forms.Form):
        images = LessonImagesField(required=False)

    form = Optional(files={})
    assert form.is_valid() and form.cleaned_data["images"] == []


# AC-05: decompression bombs are rejected.


def test_decompression_bomb_rejected():
    bomb = make_image("PNG", size=(9000, 9000), mode="1")  # tiny file, 81 million pixels
    assert bomb.size < 100_000
    with pytest.raises(ValidationError):
        process_image(bomb)


def test_cmyk_jpeg_converted_to_rgb():
    cleaned = process_image(make_image("JPEG", mode="CMYK"))
    assert Image.open(cleaned).mode == "RGB"
