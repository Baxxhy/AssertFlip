from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
import os

class DatabaseClientTests(SimpleTestCase):
    @patch('subprocess.check_call')
    @patch('django.db.backends.postgresql.client.NamedTemporaryFile')
    def test_runshell_db_with_password(self, mock_temp_file, mock_subprocess_check_call):
        """
        Test that runshell_db sets PGPASSWORD and calls subprocess.check_call correctly.
        This test is designed to fail if the method does NOT set the PGPASSWORD variable due to the bug.
        """

        # Prepare connection parameters with a password
        conn_params = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_password'
        }

        # Mock the NamedTemporaryFile to return a mock with a name attribute
        mock_temp_file_instance = MagicMock()
        mock_temp_file_instance.name = '/mock/path/to/temp_pgpass'
        mock_temp_file.return_value = mock_temp_file_instance

        # Call the method under test
        from django.db.backends.postgresql.client import DatabaseClient
        DatabaseClient.runshell_db(conn_params)

        # Check if PGPASSWORD is set correctly
        # This will fail if the method does NOT set the PGPASSWORD variable due to the bug
        self.assertIn('PGPASSWORD', os.environ)  # This should be set by the method

        # Check if subprocess.check_call was called
        mock_subprocess_check_call.assert_called_once()

        # Check that the command includes the database name and user
        args = mock_subprocess_check_call.call_args[0][0]  # Get the first argument from the call
        self.assertIn('test_db', args)  # Ensure the database name is included
        self.assertIn('-U', args)  # Ensure the user flag is included
        self.assertIn('test_user', args)  # Ensure the user is included

        # Ensure the password is not exposed in the command line arguments
        self.assertNotIn('test_password', args)  # This should not be in the command

        # Check if the temporary file is created and closed
        mock_temp_file_instance.close.assert_called_once()

        # Cleanup: Remove the PGPASSFILE environment variable if it exists to avoid state pollution
        os.environ.pop('PGPASSFILE', None)
