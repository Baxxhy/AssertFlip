import os
import tempfile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import SimpleTestCase, override_settings

class FileUploadPermissionTests(SimpleTestCase):
    
    @override_settings(FILE_UPLOAD_PERMISSIONS=None)
    def test_file_upload_permissions(self):
        """
        Test that uploaded files do not have permissions set to 0o600 when FILE_UPLOAD_PERMISSIONS is None.
        This confirms the correct behavior where permissions are set as expected.
        """

        # Create a temporary directory for file uploads
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileSystemStorage(location=temp_dir)

            # Create a mock file for upload that is large enough to trigger TemporaryUploadedFile
            file_content = b'Test content' * 1000  # Make the file large enough
            file_name = 'test_file.txt'
            uploaded_file = TemporaryUploadedFile(name=file_name, size=len(file_content), content_type='text/plain', charset=None)

            # Write content to the temporary file
            uploaded_file.file.write(file_content)
            uploaded_file.file.seek(0)

            # Save the uploaded file
            storage.save(uploaded_file.name, uploaded_file)

            # Check permissions of the uploaded file
            uploaded_file_path = os.path.join(temp_dir, uploaded_file.name)

            # Assert that the permissions are not 0o600
            self.assertNotEqual(oct(os.stat(uploaded_file_path).st_mode & 0o777), '0o600')  # This should fail if the bug is present
