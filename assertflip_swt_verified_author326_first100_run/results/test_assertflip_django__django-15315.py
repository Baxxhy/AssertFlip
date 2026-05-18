from django.db import models
from django.test import SimpleTestCase, override_settings

@override_settings(DEBUG=True)
class FieldHashTests(SimpleTestCase):
    def test_field_hash_changes_on_assignment(self):
        f = models.CharField(max_length=200)
        d = {f: 1}
        self.assertIn(f, d)

        class Book(models.Model):
            class Meta:
                app_label = 'test_app'
            title = f

        self.assertIn(f, d, "Field should still be in the dictionary after assignment to model class.")
