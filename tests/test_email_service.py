import base64
import json
import tempfile
import unittest

from email_service import GoogleWorkspaceEmail, SCOPES
from receipt_pdf import create_receipt_pdf


class GoogleWorkspaceEmailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.email = GoogleWorkspaceEmail(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_oauth_client_is_stored_without_exposing_secrets_in_status(self):
        document = {'installed': {
            'client_id': 'client-id', 'client_secret': 'client-secret',
            'auth_uri': 'https://accounts.google.com/o/oauth2/v2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token'
        }}
        encoded = base64.b64encode(json.dumps(document).encode()).decode()
        status = self.email.configure(encoded, 'owner@example.com')
        self.assertTrue(status['configured'])
        self.assertFalse(status['connected'])
        self.assertEqual(status['email'], 'owner@example.com')
        self.assertNotIn('client_secret', status)
        url = self.email.start('http://127.0.0.1:8768/oauth/google/callback')['url']
        self.assertIn('gmail.send', url)
        self.assertIn('login_hint=owner%40example.com', url)
        self.assertIn('openid email', SCOPES)

    def test_invalid_oauth_file_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'OAuth client JSON'):
            self.email.configure(base64.b64encode(b'{}').decode(), 'owner@example.com')

    def test_receipt_pdf_is_valid_and_contains_locked_values(self):
        snapshot = {'tenant_name':'Tenant','property_name':'Home','property_address':'123 Main','category':'Rent','description':'Monthly rent','amount':900,'date':'2026-09-30','method':'Cash','reference':'60694791','owner':{'name':'Owner'}}
        receipt = create_receipt_pdf(snapshot, 'R-00001')
        self.assertTrue(receipt.startswith(b'%PDF-1.4'))
        self.assertTrue(receipt.rstrip().endswith(b'%%EOF'))
        self.assertIn(b'R-00001', receipt)
        self.assertIn(b'$900.00', receipt)
        message = self.email._receipt_message('owner@example.com', 'tenant@example.com', 'Receipt', ['Attached'], snapshot, 'R-00001')
        attachment = next(message.iter_attachments())
        self.assertEqual(attachment.get_content_type(), 'application/pdf')
        self.assertEqual(attachment.get_filename(), 'R-00001-payment-receipt.pdf')
        self.assertTrue(attachment.get_payload(decode=True).startswith(b'%PDF-1.4'))


if __name__ == '__main__':
    unittest.main()
