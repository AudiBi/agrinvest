"""Chaque page rendue doit répondre sans erreur serveur (gabarits présents, endpoints valides)."""
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Contribution, WeatherAlert, WeatherSubscription
from app.models.contribution import utc_now
from tests.conftest import login_as


def test_weather_page_lists_alert_and_subscription_form(client, farmer_user):
    from datetime import timedelta
    db.session.add(WeatherAlert(zone='Artibonite', alert_type='rain', severity='warning',
                                message_ht='Gwo lapli', message_fr='Fortes pluies',
                                starts_at=utc_now().replace(tzinfo=None),
                                ends_at=utc_now().replace(tzinfo=None) + timedelta(days=1)))
    db.session.commit()
    assert b'Fortes pluies' in client.get('/weather').data
    login_as(client, farmer_user)
    assert b'name="zone"' in client.get('/weather').data


def test_weather_subscription_and_alert_notifications(client, app, farmer_user):
    from datetime import timedelta
    from app.models import Notification
    from app.utils.notifications import send_weather_alert_notifications
    login_as(client, farmer_user)
    client.post('/weather/subscribe', data={'zone': 'Artibonite'})
    now = utc_now().replace(tzinfo=None)
    alerts = [WeatherAlert(zone='Artibonite', alert_type='rain', severity=sev, message_ht=f'msg {sev}',
                           starts_at=now, ends_at=now + timedelta(days=1)) for sev in ('info', 'critical')]
    other_zone = WeatherAlert(zone='Nord', alert_type='rain', severity='critical', message_ht='autre zone',
                              starts_at=now, ends_at=now + timedelta(days=1))
    db.session.add_all(alerts + [other_zone])
    db.session.commit()
    # gravité minimale par défaut = « warning » : l'alerte « info » et l'autre zone sont ignorées
    assert [send_weather_alert_notifications(a) for a in alerts] == [0, 1]
    assert send_weather_alert_notifications(other_zone) == 0
    assert Notification.query.filter_by(user_id=farmer_user.id).count() == 1
    assert WeatherSubscription.query.one().last_notified_at is not None


def test_search_page(client, project):
    assert client.get('/search?q=Caf').status_code == 200
    assert b'Caf' in client.get('/search?q=Caf').data
    assert client.get('/search').status_code == 302  # requête vide -> accueil


def test_group_pages(client, investor, project):
    assert client.get('/groups').status_code == 302  # connexion requise
    login_as(client, investor)
    assert client.get('/groups').status_code == 200
    assert client.get('/groups/create').status_code == 200


def test_change_password_page_and_flow(client, investor):
    assert client.get('/auth/change-password').status_code == 302
    login_as(client, investor)
    assert client.get('/auth/change-password').status_code == 200
    wrong = client.post('/auth/change-password', data={
        'current_password': 'bad', 'new_password': 'NewPassw0rd!x', 'confirm_password': 'NewPassw0rd!x'})
    assert wrong.status_code == 200
    ok = client.post('/auth/change-password', data={
        'current_password': 'Passw0rd!x', 'new_password': 'NewPassw0rd!x', 'confirm_password': 'NewPassw0rd!x'})
    assert ok.status_code == 302
    db.session.refresh(investor)
    assert investor.check_password('NewPassw0rd!x')


def test_project_update_page_requires_owner(client, project, farmer_user, investor):
    from app.models import User
    url = f'/project/{project.id}/update/create'
    owner = db.session.get(User, project.farmer_id)
    login_as(client, owner)
    assert client.get(url).status_code == 200
    for stranger in (farmer_user, investor):
        login_as(client, stranger)
        assert client.get(url).status_code in (302, 403, 404)


@pytest.mark.parametrize('payload', [{}, {'event_type': ''}, {'event_type': 'x' * 51}, {'event_type': 5}])
def test_analytics_track_validates_input(client, payload):
    assert client.post('/api/v1/analytics/track', json=payload).status_code == 400
    assert client.post('/api/v1/analytics/track', json={'event_type': 'page_view'}).status_code == 200


@pytest.mark.parametrize('payload', [
    {}, {'amount': 'abc', 'currency': 'USD', 'payment_method': 'stripe'},
    {'amount': -5, 'currency': 'USD', 'payment_method': 'stripe'},
    {'amount': 10, 'payment_method': 'stripe'}])
def test_estimate_fees_validates_input(client, payload):
    assert client.post('/api/v1/contributions/estimate-fees', json=payload).status_code == 400
