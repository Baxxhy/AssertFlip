from django.test import SimpleTestCase
from django.contrib.admindocs.utils import trim_docstring, parse_docstring

class TrimDocstringTests(SimpleTestCase):
    def test_trim_docstring_with_non_empty_first_line(self):
        """
        Test trim_docstring with various docstrings that start with a non-empty line.
        This should fail when the bug is present and pass only when the bug is fixed.
        """

        # Prepare a list of docstrings that start with a non-empty line
        docstrings = [
            """This is a test docstring with leading content.
            
            This is the second line.""",
            """    This is a test docstring with leading spaces.
            
            This is the second line.""",
            """This is a test docstring with multiple lines.

            This is the second line."""
        ]

        for docstring in docstrings:
            # Call trim_docstring and capture the output
            trimmed_docstring = trim_docstring(docstring)
            
            # Pass the trimmed docstring to parse_docstring
            title, body, metadata = parse_docstring(trimmed_docstring)

            # Assert that the body is empty, indicating the bug is present if it is not
            self.assertEqual(body.strip(), "", "The body should be empty, indicating the bug is present.")
            
            # Assert that the title is correctly parsed
            self.assertEqual(title.strip(), docstring.splitlines()[0].strip(), "The title is incorrectly parsed due to the bug.")
