"""Google Workspace OAuth and Gmail sending for Hearth."""
from __future__ import annotations

import base64
import ctypes
import json
import os
import secrets
import time
from ctypes import wintypes
from email.message import EmailMessage
from receipt_pdf import create_receipt_pdf
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCOPES = 'openid email https://www.googleapis.com/auth/gmail.send'


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != 'nt':
        return data
    source = ctypes.create_string_buffer(data)
    source_blob = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    result_blob = _Blob()
    crypt32 = ctypes.windll.crypt32
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(source_blob), 'Hearth Google Workspace', None, None, None, 1, ctypes.byref(result_blob))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source_blob), None, None, None, None, 1, ctypes.byref(result_blob))
    if not ok:
        raise OSError('Windows could not protect the Google Workspace connection.')
    try:
        return ctypes.string_at(result_blob.pbData, result_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result_blob.pbData)


class GoogleWorkspaceEmail:
    def __init__(self, folder):
        self.folder = Path(folder) / 'private'
        self.path = self.folder / 'google-workspace.bin'
        self.pending = {}

    def _load(self):
        if not self.path.is_file():
            return {}
        try:
            return json.loads(_dpapi(self.path.read_bytes(), False))
        except Exception:
            return {}

    def _save(self, value):
        self.folder.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(',', ':')).encode()
        self.path.write_bytes(_dpapi(raw, True))
        if os.name != 'nt':
            self.path.chmod(0o600)

    def status(self):
        saved = self._load()
        return {
            'provider': 'Google Workspace',
            'configured': bool(saved.get('client')),
            'connected': bool(saved.get('token', {}).get('refresh_token')),
            'email': saved.get('token', {}).get('email') or saved.get('expected_email', '')
        }

    def configure(self, encoded, expected_email):
        expected_email = str(expected_email or '').strip().lower()
        if '@' not in expected_email or len(expected_email) > 254:
            raise ValueError('Enter the Google Workspace email address that will send messages.')
        try:
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 100_000:
                raise ValueError()
            document = json.loads(raw)
            client = document.get('installed') or document.get('web')
            required = ('client_id', 'client_secret', 'auth_uri', 'token_uri')
            if not isinstance(client, dict) or any(not client.get(key) for key in required):
                raise ValueError()
        except Exception:
            raise ValueError('Choose the OAuth client JSON downloaded from Google Cloud.')
        self._save({'client': {key: client[key] for key in required}, 'expected_email': expected_email})
        return self.status()

    def disconnect(self):
        self.path.unlink(missing_ok=True)
        self.pending.clear()
        return self.status()

    def start(self, redirect_uri):
        saved = self._load()
        client = saved.get('client')
        if not client:
            raise ValueError('Add the Google OAuth client file first.')
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(__import__('hashlib').sha256(verifier.encode()).digest()).decode().rstrip('=')
        self.pending[state] = {'verifier': verifier, 'redirect_uri': redirect_uri, 'created': time.time()}
        params = {
            'client_id': client['client_id'], 'redirect_uri': redirect_uri, 'response_type': 'code',
            'scope': SCOPES, 'access_type': 'offline', 'prompt': 'consent', 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256',
            'login_hint': saved.get('expected_email', '')
        }
        return {'url': client['auth_uri'] + '?' + urlencode(params)}

    def finish(self, code, state):
        pending = self.pending.pop(state, None)
        if not pending or time.time() - pending['created'] > 600:
            raise ValueError('The Google sign-in request expired. Start the connection again.')
        saved = self._load(); client = saved.get('client') or {}
        token = self._post_form(client['token_uri'], {
            'code': code, 'client_id': client['client_id'], 'client_secret': client['client_secret'],
            'redirect_uri': pending['redirect_uri'], 'grant_type': 'authorization_code',
            'code_verifier': pending['verifier']
        })
        access = token.get('access_token')
        if not access or not token.get('refresh_token'):
            raise ValueError('Google did not return a reusable connection. Remove Hearth from your Google account and connect again.')
        info = self._get_json('https://openidconnect.googleapis.com/v1/userinfo', access)
        email = str(info.get('email', '')).lower()
        if email != saved.get('expected_email'):
            raise ValueError(f'Sign in as {saved.get("expected_email")}, not {email or "another account"}.')
        saved['token'] = {
            'refresh_token': token['refresh_token'], 'access_token': access,
            'expires_at': time.time() + int(token.get('expires_in', 3600)) - 60, 'email': email
        }
        self._save(saved)
        return self.status()

    def _post_form(self, url, values):
        request = Request(url, urlencode(values).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    def _get_json(self, url, access_token):
        request = Request(url, headers={'Authorization': 'Bearer ' + access_token})
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    def _access_token(self):
        saved = self._load(); token = saved.get('token') or {}
        if not token.get('refresh_token'):
            raise ValueError('Connect Google Workspace in Settings first.')
        if token.get('access_token') and token.get('expires_at', 0) > time.time():
            return token['access_token'], token['email']
        client = saved['client']
        refreshed = self._post_form(client['token_uri'], {
            'client_id': client['client_id'], 'client_secret': client['client_secret'],
            'refresh_token': token['refresh_token'], 'grant_type': 'refresh_token'
        })
        token['access_token'] = refreshed['access_token']
        token['expires_at'] = time.time() + int(refreshed.get('expires_in', 3600)) - 60
        saved['token'] = token; self._save(saved)
        return token['access_token'], token['email']

    def send_receipt(self, store, payment_id):
        with store.lock, store.connect() as con:
            payment = store.get(con, payment_id)
            if not payment or payment.get('kind') != 'payments' or payment.get('archived'):
                raise ValueError('Payment not found.')
            if payment.get('void'):
                raise ValueError('A voided payment receipt cannot be sent.')
            receipt = con.execute('SELECT * FROM receipts WHERE payment_id=?', (payment_id,)).fetchone()
            if not receipt:
                raise ValueError('Create the locked receipt before sending it.')
            tenant = store.get(con, payment['tenant_id'])
            recipient = str(tenant.get('email', '')).strip()
            if '@' not in recipient:
                raise ValueError('Add an email address to this tenant before sending the receipt.')
            snapshot = json.loads(receipt['snapshot']); number = int(receipt['number'])
        access_token, sender = self._access_token()
        ref = f'R-{number:05}'
        subject = f'Payment receipt {ref} — {snapshot["property_name"]}'
        lines = [
            f'Hello {snapshot["tenant_name"]},', '', f'Your payment receipt {ref} is attached.', '',
            f'Property: {snapshot["property_name"]}', f'Payment date: {snapshot["date"]}',
            f'Amount received: ${float(snapshot["amount"]):,.2f}', f'Payment method: {snapshot.get("method") or "—"}', '',
            'This email was sent from Hearth on behalf of your property manager.'
        ]
        message = self._receipt_message(sender, recipient, subject, lines, snapshot, ref)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip('=')
        request = Request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', json.dumps({'raw': raw}).encode(), headers={'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=20) as response:
            sent = json.load(response)
        with store.lock, store.connect() as con:
            con.execute('INSERT INTO audit(at,action,kind,record_id,after_json) VALUES(?,?,?,?,?)', (__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(timespec='seconds'), 'Receipt emailed', 'payments', payment_id, json.dumps({'to': recipient, 'message_id': sent.get('id', '')})))
        return {'ok': True, 'to': recipient, 'message_id': sent.get('id', '')}

    @staticmethod
    def _receipt_message(sender, recipient, subject, lines, snapshot, ref):
        message = EmailMessage(); message['From'] = sender; message['To'] = recipient; message['Subject'] = subject
        message.set_content('\n'.join(lines))
        message.add_attachment(create_receipt_pdf(snapshot, ref), maintype='application', subtype='pdf', filename=f'{ref}-payment-receipt.pdf')
        return message
