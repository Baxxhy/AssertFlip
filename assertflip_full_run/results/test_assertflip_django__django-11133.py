from django.test import SimpleTestCase
from django.http import HttpResponse

class HttpResponseMemoryviewTest(SimpleTestCase):
    def test_memoryview_content(self):
        # Create a memoryview object from a bytes object
        mem_view = memoryview(b"My Content")

        # Instantiate HttpResponse with the memoryview
        response = HttpResponse(mem_view)

        # Assert that the content is equal to the expected byte string
        self.assertEqual(response.content, b"My Content")  # This should pass when the bug is fixed
