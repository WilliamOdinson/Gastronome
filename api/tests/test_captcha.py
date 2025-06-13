import re
import time
from unittest import mock

from django.test import TestCase
from PIL import ImageFont

from api.captcha import generate_captcha_text


class CaptchaImageTests(TestCase):
    def test_captcha_response_is_png(self):
        """
        GET /api/captcha/ returns PNG bytes and writes a 4-char code into session.
        """
        with mock.patch.object(ImageFont, "truetype", return_value=ImageFont.load_default()):
            resp = self.client.get("/api/captcha/")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertTrue(resp.content.startswith(b"\x89PNG"))

        code, ts = self.client.session["captcha_code"]
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9]{4}", code))
        self.assertIsInstance(ts, float)

    def test_generate_captcha_text_random_and_length(self):
        """
        All generated codes are 4 chars and unique.
        """
        codes = {generate_captcha_text() for _ in range(30)}
        self.assertEqual(len(codes), 30)
        self.assertTrue(all(len(c) == 4 for c in codes))

    def test_second_call_overwrites_session_with_new_code(self):
        """
        A subsequent /api/captcha/ call should replace the stored code and
        update the timestamp.
        """
        with mock.patch.object(ImageFont, "truetype", return_value=ImageFont.load_default()):
            self.client.get("/api/captcha/")

        first_code, first_ts = self.client.session["captcha_code"]

        time.sleep(0.5)

        with mock.patch.object(ImageFont, "truetype", return_value=ImageFont.load_default()):
            self.client.get("/api/captcha/")

        second_code, second_ts = self.client.session["captcha_code"]

        self.assertNotEqual(first_code, second_code)
        self.assertGreater(second_ts, first_ts)
