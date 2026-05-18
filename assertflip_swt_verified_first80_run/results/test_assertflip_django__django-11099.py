from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.validators import ASCIIUsernameValidator, UnicodeUsernameValidator

class UsernameValidatorTests(SimpleTestCase):
    def setUp(self):
        self.ascii_validator = ASCIIUsernameValidator()
        self.unicode_validator = UnicodeUsernameValidator()

    def test_username_validation_with_trailing_newline(self):
        # Invalid username with a single trailing newline
        invalid_username = "invalid_user\n"
        
        # This should raise ValidationError if the bug is present
        with self.assertRaises(ValidationError):
            self.ascii_validator(invalid_username)  # Should raise

        with self.assertRaises(ValidationError):
            self.unicode_validator(invalid_username)  # Should raise
