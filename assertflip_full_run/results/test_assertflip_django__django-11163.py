from django.test import SimpleTestCase
from django.db import models
from itertools import chain

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

class MockField:
    def __init__(self, name, editable):
        self.name = name
        self.editable = editable

    def value_from_object(self, obj):
        return getattr(obj, self.name)

class MockModel:
    _meta = type('Meta', (), {
        'concrete_fields': [MockField('field1', editable=True), MockField('field2', editable=True)],
        'private_fields': [],
        'many_to_many': []
    })

    def __init__(self, field1, field2):
        self.field1 = field1
        self.field2 = field2

class ModelToDictTests(SimpleTestCase):
    def test_model_to_dict_with_empty_fields(self):
        instance = MockModel(field1='value1', field2='value2')
        
        # Call model_to_dict with an empty list for fields
        result = model_to_dict(instance, fields=[])

        # Assert that the result is an empty dictionary, passing only if the bug is fixed
        self.assertEqual(result, {}, "model_to_dict should return an empty dict for empty fields list.")
