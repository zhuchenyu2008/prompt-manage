import io
import unittest

from PIL import Image

import cover_images


def image_bytes(image_format="PNG", size=(12, 8), **save_options):
    image = Image.new("RGBA" if image_format != "JPEG" else "RGB", size, (50, 110, 180, 255))
    output = io.BytesIO()
    image.save(output, image_format, **save_options)
    return output.getvalue()


class CoverImageTests(unittest.TestCase):
    def test_supported_static_formats_are_normalized(self):
        for image_format in ("JPEG", "PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                asset = cover_images.normalize_cover(image_bytes(image_format))
                self.assertEqual((asset.width, asset.height), (12, 8))
                self.assertTrue(asset.full_bytes)
                self.assertTrue(asset.thumbnail_bytes)

    def test_exactly_five_megabytes_is_allowed(self):
        raw = image_bytes("PNG")
        raw += b"\0" * (cover_images.MAX_IMAGE_SIZE - len(raw))
        asset = cover_images.normalize_cover(raw)
        self.assertEqual((asset.width, asset.height), (12, 8))

    def test_more_than_five_megabytes_is_rejected(self):
        with self.assertRaisesRegex(cover_images.CoverImageError, "5MB"):
            cover_images.read_limited(io.BytesIO(b"x" * (cover_images.MAX_IMAGE_SIZE + 1)))

    def test_corrupt_image_is_rejected(self):
        with self.assertRaisesRegex(cover_images.CoverImageError, "损坏"):
            cover_images.normalize_cover(b"not-an-image")

    def test_animated_webp_is_rejected(self):
        first = Image.new("RGB", (8, 8), "red")
        second = Image.new("RGB", (8, 8), "blue")
        output = io.BytesIO()
        first.save(output, "WEBP", save_all=True, append_images=[second], duration=100, loop=0)
        with self.assertRaisesRegex(cover_images.CoverImageError, "动画 WebP"):
            cover_images.normalize_cover(output.getvalue())

    def test_pixel_limit_is_enforced(self):
        original_limit = cover_images.MAX_IMAGE_PIXELS
        cover_images.MAX_IMAGE_PIXELS = 4
        try:
            with self.assertRaisesRegex(cover_images.CoverImageError, "4000 万"):
                cover_images.normalize_cover(image_bytes("PNG", size=(3, 2)))
        finally:
            cover_images.MAX_IMAGE_PIXELS = original_limit


if __name__ == "__main__":
    unittest.main()
