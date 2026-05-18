from django.test import SimpleTestCase
from unittest.mock import patch
import os
from django.db.backends.postgresql.client import DatabaseClient

class DatabaseClientSSLCertTests(SimpleTestCase):
    @patch('subprocess.run')
    def test_runshell_includes_ssl_params(self, mock_run):
        # Set up environment variables for the test
        os.environ['POSTGRES_DB_NAME'] = 'test_db'
        os.environ['POSTGRES_DB_USER'] = 'test_user'
        os.environ['POSTGRES_DB_SCHEMA'] = 'public'
        os.environ['POSTGRES_CLI_SSL_CA'] = 'path/to/ca.crt'
        os.environ['POSTGRES_CLI_SSL_CRT'] = 'path/to/client_cert_chain.crt'
        os.environ['POSTGRES_CLI_SSL_KEY'] = 'path/to/client_key.key'

        # Create a mock connection parameters dictionary including SSL options
        conn_params = {
            'database': os.environ['POSTGRES_DB_NAME'],
            'user': os.environ['POSTGRES_DB_USER'],
            'host': 'localhost',
            'port': '5432',
            'sslmode': 'verify-ca',
            'sslrootcert': os.environ['POSTGRES_CLI_SSL_CA'],
            'sslcert': os.environ['POSTGRES_CLI_SSL_CRT'],
            'sslkey': os.environ['POSTGRES_CLI_SSL_KEY'],
        }

        # Create a mock connection object
        class MockConnection:
            def get_connection_params(self):
                return conn_params

        # Create an instance of the DatabaseClient with a mock connection
        client = DatabaseClient(MockConnection())

        # Call the runshell method
        client.runshell()  # Call the method that should include SSL parameters

        # Check the command that was executed
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]  # Get the first argument of the call

        # Assert that the command includes the SSL parameters
        self.assertIn('--sslcert', args)  # This should pass if the bug is fixed
        self.assertIn('--sslkey', args)    # This should pass if the bug is fixed
