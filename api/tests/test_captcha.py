from django.test import TestCase


class CaptchaImageTests(TestCase):
    def test_captcha_response_is_png(self):
        """
        /api/captcha/ should return a 200 status code, the content type is image/png,
        and captcha_code is written into the session.
        """
        response = self.client.get("/api/captcha/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content[:8].startswith(b"\x89PNG"))

        session = self.client.session
        self.assertIn("captcha_code", session)
        value = session["captcha_code"]

        self.assertIsInstance(value, list)
        self.assertEqual(len(value), 2)
        self.assertIsInstance(value[0], str)
        self.assertEqual(len(value[0]), 4)
