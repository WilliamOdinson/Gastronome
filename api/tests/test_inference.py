import os
import unittest
import json
from django.test import TestCase
from django.urls import reverse


@unittest.skipIf(os.getenv('DJANGO_TEST_DB') == 'sqlite', "Skip PredictReviewApiTests on Github Actions CI")
class PredictReviewApiTests(TestCase):
    def test_predict_valid_input(self):
        """
        Test that correct JSON input can yield prediction results.
        """
        url = reverse('api:predict_review_api')
        response = self.client.post(
            url,
            data=json.dumps({'review': 'The food was amazing!'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('prediction', response.json())
        self.assertIsInstance(response.json()['prediction'], int)

    def test_predict_invalid_json(self):
        """
        Test that invalid JSON input returns a 400 error.
        """
        url = reverse('api:predict_review_api')
        response = self.client.post(
            url,
            data='not a json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_predict_empty_review(self):
        """
        Test that empty review content returns a 400 error.
        """
        url = reverse('api:predict_review_api')
        response = self.client.post(
            url,
            data=json.dumps({'review': ''}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
