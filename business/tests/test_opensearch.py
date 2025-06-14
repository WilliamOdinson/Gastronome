from unittest.mock import patch

from django.test import SimpleTestCase

from business.opensearch_tasks import push_is_open_bulk


class PushIsOpenBulkTests(SimpleTestCase):
    """push_is_open_bulk should short-circuit on an empty id list."""

    def test_empty_list_returns_zero_and_no_client_call(self):
        """
        Test that push_is_open_bulk returns 0 and does not call the client
        when given an empty list.
        """
        with patch(
            "business.opensearch_tasks.get_opensearch_client"
        ) as mock_client:
            count = push_is_open_bulk([])
        self.assertEqual(count, 0)
        mock_client.assert_not_called()
