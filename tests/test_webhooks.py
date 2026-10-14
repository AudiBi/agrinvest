import hashlib
import hmac
import json

URL = '/api/v1/webhooks/moncash'


def sign(body: bytes, secret='moncash-test-secret'):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post(client, payload, signature=None):
    body = json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json'}
    if signature is not None:
        headers['X-MonCash-Signature'] = signature
    return client.post(URL, data=body, headers=headers), body


def test_moncash_rejects_missing_signature(client):
    resp, _ = post(client, {'payment_id': 'p1', 'status': 'completed'})
    assert resp.status_code == 401


def test_moncash_rejects_bad_signature(client):
    resp, _ = post(client, {'payment_id': 'p1', 'status': 'completed'}, signature='deadbeef')
    assert resp.status_code == 401


def test_moncash_rejects_when_secret_not_configured(client, app):
    app.config['MONCASH_WEBHOOK_SECRET'] = ''
    body = json.dumps({'payment_id': 'p1'}).encode()
    resp = client.post(URL, data=body, headers={
        'Content-Type': 'application/json',
        'X-MonCash-Signature': sign(body, ''),
    })
    assert resp.status_code == 401


def test_moncash_accepts_valid_signature_unknown_payment(client):
    body = json.dumps({'payment_id': 'unknown', 'status': 'completed'}).encode()
    resp = client.post(URL, data=body, headers={
        'Content-Type': 'application/json',
        'X-MonCash-Signature': sign(body),
    })
    assert resp.status_code == 200


def test_wise_rejects_missing_signature(client):
    resp = client.post('/api/v1/webhooks/wise', json={'event_type': 'x'})
    assert resp.status_code == 401
