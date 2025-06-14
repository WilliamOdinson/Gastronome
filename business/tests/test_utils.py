from django.test import SimpleTestCase

from business.tasks import _batched


class BatchedHelperTests(SimpleTestCase):
    """
    _batched must return full, ordered partitions of the source iterable.
    """

    def test_batches_yield_complete_partitions(self):
        """
        Test that _batched yields complete partitions of the source iterable.
        """
        data = list(range(10))
        batches = list(_batched(data, 3))
        self.assertEqual(
            batches,
            [
                [0, 1, 2],
                [3, 4, 5],
                [6, 7, 8],
                [9],
            ],
        )
