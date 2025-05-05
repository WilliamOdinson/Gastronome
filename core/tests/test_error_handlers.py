from django.test import TestCase, RequestFactory
from django.template.response import TemplateResponse


class ErrorHandlerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_page_not_found_view(self):
        from core.views import page_not_found
        request = self.factory.get('/nonexistent-path/')
        response = page_not_found(request, Exception('Not Found'))
        self.assertEqual(response.status_code, 404)
        if isinstance(response, TemplateResponse):
            self.assertTemplateUsed(response, '404.html')

    def test_server_error_view(self):
        from core.views import server_error
        request = self.factory.get('/')
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Server Error (500)', status_code=500)

    def test_permission_denied_view(self):
        from core.views import permission_denied
        request = self.factory.get('/')
        response = permission_denied(request, Exception('Forbidden'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Permission Denied (403)', status_code=403)

    def test_bad_request_view(self):
        from core.views import bad_request
        request = self.factory.get('/')
        response = bad_request(request, Exception('Bad Request'))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Bad Request (400)', status_code=400)
