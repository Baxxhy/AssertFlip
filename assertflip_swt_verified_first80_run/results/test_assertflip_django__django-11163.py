from django.test import SimpleTestCase
from django.db import models
from itertools import chain

# Mock model class to simulate a Django model instance
class MockModel(models.Model):
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    editable_field = models.CharField(max_length=100, editable=True)
    non_editable_field = models.CharField(max_length=100, editable=False)

    class Meta:
        app_label = 'test_app'  # Explicitly declare an app_label for the mock model

def model_to_dict(instance, fields=None, exclude=None):
    opts = instance._meta
    data = {}
    for f in chain(opts.concrete_fields, opts.private_fields, opts.many_to_many):
        if not getattr(f, 'editable', False):
            continue
        if fields and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue
        data[f.name] = f.value_from_object(instance)
    return data

class ModelToDictTests(SimpleTestCase):
    def test_model_to_dict_with_empty_fields(self):
        """
        Test model_to_dict with an empty list of fields.
        """

        # Create an instance of the mock model
        instance = MockModel(name="Test", age=30, editable_field="Editable", non_editable_field="NonEditable")

        # Call model_to_dict with fields set to an empty list
        result = model_to_dict(instance, fields=[])

        # Assert that the result is an empty dictionary
        self.assertEqual(result, {}, 
                         "Expected an empty dictionary when fields are empty.")
