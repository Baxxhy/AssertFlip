from django.test import SimpleTestCase
from unittest.mock import patch

class DatabaseClientSSLCertTests(SimpleTestCase):
    @patch('subprocess.run')
    def test_runshell_with_ssl_parameters_included(self, mock_run):
        conn_params = {
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_password',
            'host': 'localhost',
            'port': '5432',
            'sslrootcert': 'ca.crt',
            'sslcert': 'client_cert_chain.crt',
            'sslkey': 'client_key.key',
        }

        from django.db.backends.postgresql.client import DatabaseClient
        DatabaseClient.runshell_db(conn_params)

        args_passed = mock_run.call_args[0][0]

        self.assertIn('--sslrootcert', args_passed)
        self.assertIn('--sslcert', args_passed)
        self.assertIn('--sslkey', args_passed)

    @patch('subprocess.run')
    def test_runshell_with_partial_ssl_parameters_included(self, mock_run):
        conn_params = {
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_password',
            'host': 'localhost',
            'port': '5432',
            'sslrootcert': 'ca.crt',
        }

        from django.db.backends.postgresql.client import DatabaseClient
        DatabaseClient.runshell_db(conn_params)

        args_passed = mock_run.call_args[0][0]

        self.assertIn('--sslrootcert', args_passed)
        self.assertNotIn('--sslcert', args_passed)
        self.assertNotIn('--sslkey', args_passed)
