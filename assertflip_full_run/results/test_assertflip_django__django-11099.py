from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.validators import ASCIIUsernameValidator, UnicodeUsernameValidator

class UsernameValidatorTests(SimpleTestCase):
    def setUp(self):
        self.ascii_validator = ASCIIUsernameValidator()
        self.unicode_validator = UnicodeUsernameValidator()

    def test_username_validation_with_newline(self):
        # Valid usernames
        valid_usernames = [
            "valid_user",
            "user.name",
            "user+name",
            "user-name",
            "user@name"
        ]

        # Invalid usernames (with trailing newline)
        invalid_usernames = [
            "invalid_user\n",
            "user.name\n",
            "user+name\n",
            "user-name\n",
            "user@name\n"
        ]

        # Test valid usernames
        for username in valid_usernames:
            try:
                self.ascii_validator(username)
                self.unicode_validator(username)
            except ValidationError:
                self.fail(f"ValidationError raised for valid username: {username}")

        # Test invalid usernames
        for username in invalid_usernames:
            # This should fail, exposing the bug where the validator incorrectly allows newlines
            with self.assertRaises(ValidationError):
                self.ascii_validator(username)  # This should raise ValidationError if the bug is fixed
            with self.assertRaises(ValidationError):
                self.unicode_validator(username)  # This should raise ValidationError if the bug is fixed
