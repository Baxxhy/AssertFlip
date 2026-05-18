from django.http import HttpResponse
from django.test import SimpleTestCase

class HttpResponseMemoryViewTests(SimpleTestCase):
    def test_memoryview_content(self):
        # Create a memoryview object from a bytes string
        mem_view = memoryview(b"My Content")

        # Create an HttpResponse with the memoryview
        response = HttpResponse(mem_view)

        # Check that the content is equal to the expected bytes
        self.assertEqual(response.content, b"My Content")  # This will pass only if the bug is fixed

        # Check that the content is not a memoryview representation
        self.assertNotIsInstance(response.content, bytes)  # This will fail if the bug is fixed
        self.assertNotIn(b'<memory', response.content)  # This indicates the absence of the bug
