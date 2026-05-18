from django import forms
from django.test import SimpleTestCase
import copy

class TestForm(forms.Form):
    name = forms.CharField(error_messages={'required': 'This field is required.'})
    email = forms.EmailField(error_messages={'invalid': 'Enter a valid email address.'})

class DeepCopyErrorMessagesTest(SimpleTestCase):
    def test_deepcopy_error_messages(self):
        # Create an instance of the form
        original_form = TestForm()
        
        # Create a deep copy of the original form
        copied_form = copy.deepcopy(original_form)
        
        # Modify the error message of the 'name' field in the original form
        original_form.fields['name'].error_messages['required'] = 'This field cannot be empty.'
        
        # Assert that the copied form's 'name' field error message does NOT reflect the change in the original form
        # This assertion will fail if the bug is present, as both forms share the same error_messages dictionary
        self.assertNotEqual(copied_form.fields['name'].error_messages['required'], 'This field cannot be empty.')  # Modified message
        
        # Assert that the original form's error message has changed
        self.assertNotEqual(original_form.fields['name'].error_messages['required'], 'This field is required.')  # Should be modified
