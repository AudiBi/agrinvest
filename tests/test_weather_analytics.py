"""Météo (alertes, abonnements, services externes), analytics, fuseau horaire PostgreSQL."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import AnalyticsEvent, WeatherAlert, WeatherSubscription
from app.models.contribution import utc_now
from tests.conftest import login_as

W = '/api/v1/weather'
A = '/api/v1/analytics'


def naive_now():
    return utc_now().replace(tzinfo=None)


def alert(zone='Nord', severity='warning', **extra):
    fields = dict(zone=zone, alert_type='rain', severity=severity, message_ht='msg',
                  starts_at=naive_now() - timedelta(hours=1), ends_at=naive_now() + timedelta(hours=5))
    fields.update(extra)
    a = WeatherAlert(**fields)
    db.session.add(a)
    db.session.commit()
    return a


# ====================================================================== alertes
def test_alerts_are_sorted_critical_first_and_only_active(client):
    alert(severity='info')
    alert(severity='critical')
    alert(severity='warning')
    alert(severity='critical', ends_at=naive_now() - timedelta(minutes=1))            # terminée
    alert(severity='critical', starts_at=naive_now() + timedelta(hours=1),
          ends_at=naive_now() + timedelta(hours=2))                                  # pas encore commencée
    alert(severity='critical', is_active=False)
    body = client.get(f'{W}/alerts').get_json()
    assert [a['severity'] for a in body['alerts']] == ['critical', 'warning', 'info'] and body['count'] == 3
    assert client.get(f'{W}/alerts?zone=Sud').get_json()['count'] == 0


def valid_alert(**extra):
    return {'zone': 'Nord', 'alert_type': 'rain', 'severity': 'critical', 'message_ht': 'Gwo lapli',
            'starts_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            'ends_at': (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(), **extra}


def test_create_alert_requires_admin_and_validates(client, admin, farmer_user):
    login_as(client, farmer_user)
    assert client.post(f'{W}/alerts', json=valid_alert()).status_code == 403
    login_as(client, admin)
    assert client.post(f'{W}/alerts', json={}).status_code == 400
    for bad in ({'severity': 'apocalypse'}, {'starts_at': 'hier'}, {'zone': 'x' * 51},
                {'ends_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}, {'message_ht': ''}):
        assert client.post(f'{W}/alerts', json={**valid_alert(), **bad}).status_code == 400, bad
    assert WeatherAlert.query.count() == 0
    ok = client.post(f'{W}/alerts', json=valid_alert())
    assert ok.status_code == 201
    stored = WeatherAlert.query.one()
    assert stored.starts_at.tzinfo is None  # stockée en UTC naïf
    assert client.get(f'{W}/alerts').get_json()['count'] == 1  # visible immédiatement (fuseau correct)


def test_new_alert_notifies_subscribers(client, admin, farmer_user):
    from app.models import Notification
    login_as(client, farmer_user)
    client.post(f'{W}/subscriptions', json={'zone': 'Nord', 'phone_number': '+50937000000'})
    login_as(client, admin)
    client.post(f'{W}/alerts', json=valid_alert())
    assert Notification.query.filter_by(user_id=farmer_user.id).count() == 1


# ================================================================== abonnements
@pytest.mark.parametrize('bad', [
    {}, {'zone': ''}, {'zone': 'z' * 51}, {'zone': 'Nord', 'min_severity': 'extreme'},
    {'zone': 'Nord', 'language': 'es'}, {'zone': 'Nord', 'receive_sms': 'oui'},
    {'zone': 'Nord', 'phone_number': 'abc'}, {'zone': 'Nord', 'phone_number': None}])
def test_subscription_validation(client, farmer_user, bad):
    login_as(client, farmer_user)
    payload = bad if 'phone_number' in bad or not bad.get('zone') else {'phone_number': '+50937000000', **bad}
    assert client.post(f'{W}/subscriptions', json=payload).status_code == 400, bad
    assert WeatherSubscription.query.count() == 0


def test_subscription_lifecycle_and_ownership(client, farmer_user, investor):
    login_as(client, investor)
    assert client.post(f'{W}/subscriptions', json={'zone': 'Nord'}).status_code == 403
    login_as(client, farmer_user)
    created = client.post(f'{W}/subscriptions', json={'zone': 'Nord', 'phone_number': '+509 3700-0000'})
    assert created.status_code == 201
    again = client.post(f'{W}/subscriptions', json={'zone': 'Nord', 'phone_number': '+50937000000',
                                                    'min_severity': 'critical'})
    assert again.status_code == 200 and WeatherSubscription.query.count() == 1
    sub_id = WeatherSubscription.query.one().id
    other = __import__('tests.conftest', fromlist=['make_user']).make_user('f3@example.com', role='farmer')
    login_as(client, other)
    assert client.delete(f'{W}/subscriptions/{sub_id}').status_code == 403
    login_as(client, farmer_user)
    assert client.delete(f'{W}/subscriptions/{sub_id}').status_code == 200
    assert client.get(f'{W}/subscriptions').get_json()['subscriptions'] == []


def test_sms_subscription_needs_a_phone_number(client, farmer_user):
    login_as(client, farmer_user)
    assert client.post(f'{W}/subscriptions', json={'zone': 'Nord'}).status_code == 400
    ok = client.post(f'{W}/subscriptions', json={'zone': 'Nord', 'receive_sms': False})
    assert ok.status_code == 201


# ======================================================= services météo externes
@pytest.fixture()
def fake_weather(monkeypatch):
    calls = []

    def current(**kwargs):
        calls.append(kwargs)
        return {'temperature': 30, 'humidity': 60, 'wind_speed': 10}

    monkeypatch.setattr('app.api.weather_routes.get_current_weather', current)
    monkeypatch.setattr('app.api.weather_routes.get_forecast',
                        lambda **kwargs: calls.append(kwargs) or {'days': kwargs['days']})
    return calls


@pytest.mark.parametrize('query', ['', '?lat=18.5', '?lng=-72.3', '?lat=200&lng=0', '?lat=18&lng=-500',
                                   '?lat=abc&lng=1', '?city=' + 'x' * 101])
def test_weather_rejects_bad_locations_without_calling_the_provider(client, fake_weather, query):
    for endpoint in ('current', 'forecast', 'agricultural-advice'):
        assert client.get(f'{W}/{endpoint}{query}').status_code == 400, (endpoint, query)
    assert fake_weather == []


def test_weather_accepts_coordinates_and_city(client, fake_weather):
    assert client.get(f'{W}/current?lat=18.5&lng=-72.3').status_code == 200
    assert client.get(f'{W}/current?lat=0&lng=0').status_code == 200  # 0 est une coordonnée valide
    assert client.get(f'{W}/current?city=Cap-Haitien').status_code == 200
    assert client.get(f'{W}/agricultural-advice?lat=18.5&lng=-72.3&crop_type=banana').status_code == 200


def test_forecast_days_are_clamped(client, fake_weather):
    assert client.get(f'{W}/forecast?city=Cap&days=100000').get_json() == {'days': 7}
    assert client.get(f'{W}/forecast?city=Cap&days=-3').get_json() == {'days': 1}


def test_provider_outage_is_reported_as_unavailable(client, monkeypatch):
    monkeypatch.setattr('app.api.weather_routes.get_current_weather', lambda **kwargs: None)
    assert client.get(f'{W}/current?city=Cap').status_code == 503


def test_public_weather_endpoints_are_rate_limited(limited_app, monkeypatch):
    monkeypatch.setattr('app.api.weather_routes.get_current_weather', lambda **kwargs: {'temperature': 1})
    client = limited_app.test_client()
    codes = [client.get(f'{W}/current?city=Cap').status_code for _ in range(32)]
    assert codes[:30] == [200] * 30 and 429 in codes[30:]


# ==================================================================== analytics
def test_track_serializes_event_data_and_clips_long_fields(client):
    resp = client.post(f'{A}/track', json={'event_type': 'page_view', 'event_data': {'k': 'é'},
                                          'page_url': 'u' * 900, 'referrer': 'r' * 900, 'project_id': 3},
                       headers={'User-Agent': 'ua' * 400})
    assert resp.status_code == 200
    event = AnalyticsEvent.query.one()
    assert event.event_data == '{"k": "é"}'
    assert (len(event.page_url), len(event.referrer), len(event.user_agent)) == (500, 500, 500)
    assert event.project_id == 3


@pytest.mark.parametrize('extra', [{'project_id': 'x'}, {'contribution_id': True}, {'event_data': 'x' * 5001},
                                   {'event_data': {'k': 'x' * 5001}}])
def test_track_rejects_bad_payloads(client, extra):
    assert client.post(f'{A}/track', json={'event_type': 'page_view', **extra}).status_code == 400
    assert AnalyticsEvent.query.count() == 0


def test_analytics_stats_are_admin_only(client, investor, admin):
    for url in (f'{A}/stats/conversion', f'{A}/stats/traffic'):
        assert client.get(url).status_code == 401
        login_as(client, investor)
        assert client.get(url).status_code == 403
        login_as(client, admin)
        assert client.get(url).status_code == 200
        client.get('/logout')


def test_conversion_stats_respect_the_requested_period(client, admin):
    now = naive_now()
    for event_type, when in (('contribution_start', now), ('contribution_start', now - timedelta(days=10)),
                             ('contribution_complete', now), ('page_view', now), ('page_view', now - timedelta(days=10))):
        db.session.add(AnalyticsEvent(event_type=event_type, created_at=when))
    db.session.commit()
    login_as(client, admin)
    everything = client.get(f'{A}/stats/conversion').get_json()
    assert (everything['page_views'], everything['contribution_starts']) == (2, 2)
    today = now.strftime('%Y-%m-%d')
    recent = client.get(f'{A}/stats/conversion?start_date={today}&end_date={today}').get_json()
    assert (recent['page_views'], recent['contribution_starts'], recent['conversion_rate']) == (1, 1, 100.0)
    assert client.get(f'{A}/stats/conversion?start_date=hier').status_code == 400


def test_traffic_days_are_capped(client, admin):
    login_as(client, admin)
    assert len(client.get(f'{A}/stats/traffic?days=100000').get_json()) == 365
    assert len(client.get(f'{A}/stats/traffic?days=0').get_json()) == 1


def test_project_stats_are_private_to_owner_and_admin(client, project, other_investor, admin):
    url = f'{A}/stats/project/{project.id}'
    login_as(client, other_investor)
    assert client.get(url).status_code == 403
    for allowed in (db.session.get(type(other_investor), project.farmer_id), admin):
        login_as(client, allowed)
        assert client.get(url).status_code == 200


# ============================================================ PostgreSQL : fuseau
@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL', '').startswith('postgresql'),
                    reason='nécessite PostgreSQL (TEST_DATABASE_URL)')
def test_postgres_session_runs_in_utc(app):
    """Colonnes DateTime naïves + utc_now() aware : la session doit être en UTC, sinon décalage horaire."""
    assert db.session.execute(db.text('SHOW timezone')).scalar().upper() == 'UTC'
    created = alert()
    db.session.refresh(created)
    assert abs((created.created_at - naive_now()).total_seconds()) < 60  # valeur par défaut aware, relue naïve
