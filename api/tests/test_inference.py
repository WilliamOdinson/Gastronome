import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse


class PredictReviewApiTests(TestCase):
    """
    Tests for /api/predict/ endpoint
    """

    def setUp(self):
        self.url = reverse("api:predict_review_api")

    def _post(self, payload, ctype="application/json"):
        return self.client.post(self.url, data=payload, content_type=ctype)

    def test_predict_valid_input(self):
        """
        Test that correct JSON input can yield prediction results.
        """
        with mock.patch("api.views.predict_score", return_value=4):
            resp = self._post(json.dumps({"review": "Excellent!"}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["prediction"], int)

    def test_predict_invalid_json(self):
        """
        Test that invalid JSON input returns a 400 error.
        """
        resp = self._post("not-json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_predict_empty_review(self):
        """
        Test that empty review content returns a 400 error.
        """
        resp = self._post(json.dumps({"review": ""}))
        self.assertEqual(resp.status_code, 400)

    def test_missing_review_field(self):
        """
        Test that missing review field in JSON input returns a 400 error.
        """
        resp = self._post(json.dumps({"foo": "bar"}))
        self.assertEqual(resp.status_code, 400)

    def test_whitespace_only_review(self):
        """
        Test that a review with only whitespace characters returns a 400 error.
        """
        resp = self._post(json.dumps({"review": "   \n\t"}))
        self.assertEqual(resp.status_code, 400)

    def test_get_method_not_allowed(self):
        """
        Test that GET requests to the predict endpoint return a 405 Method Not Allowed error.
        """
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_predict_score_called_once(self):
        """
        Test that the predict_score function is called once with the correct review text.
        """
        with mock.patch("api.views.predict_score", return_value=3) as mocked:
            self._post(json.dumps({"review": "Great"}))
            mocked.assert_called_once_with("Great")

    def test_predict_score_exception_triggers_server_error(self):
        """
        If predict_score raises, Django test-client re-raises the exception.
        We assert that RuntimeError surfaces.
        """
        with mock.patch("api.views.predict_score",
                        side_effect=RuntimeError("grpc down")):
            with self.assertRaises(RuntimeError):
                self._post(json.dumps({"review": "Oops"}))
