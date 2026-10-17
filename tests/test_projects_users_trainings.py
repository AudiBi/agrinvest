"""Projets (API + publication), profils utilisateurs, formations et mises à jour de récolte."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Contribution, HarvestUpdate, Project, Training, TrainingProgress, User
from app.models.enums import ContributionStatus, ProjectStatus, UserRole
from tests.conftest import login_as, make_user

API = '/api/v1'
IMAGE = 'https://example.com/photo.jpg'


def future(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def owner_of(project):
    return db.session.get(User, project.farmer_id)


def draft_project(owner, **extra):
    fields = dict(title='Brouillon', slug='brouillon', description='d', amount_needed=Decimal('1000'),
                  farmer_id=owner.id, status=ProjectStatus.DRAFT, is_published=False,
                  min_investment=Decimal('10'), currency='HTG', image_url=IMAGE)
    fields.update(extra)
    project = Project(**fields)
    db.session.add(project)
    db.session.commit()
    return project


# ================================================================= liste & visibilité
def test_list_never_exposes_unpublished_projects(client, project, farmer_user):
    draft_project(farmer_user)
    # état incohérent (statut « published » mais retiré de la publication, p. ex. par un admin) : jamais listé
    draft_project(farmer_user, slug='retire', title='Retiré', status=ProjectStatus.PUBLISHED, is_published=False)
    for query in ('', '?status=', '?status=published'):
        titles = [p['title'] for p in client.get(f'{API}/projects{query}').get_json()['projects']]
        assert titles == ['Café'], query
    assert client.get(f'{API}/projects?status=draft').status_code == 400


def test_pagination_is_capped(client, project):
    assert client.get(f'{API}/projects?per_page=100000').get_json()['per_page'] == 100
    assert client.get(f'{API}/projects?per_page=0').get_json()['per_page'] == 1


def test_global_stats_work_on_sqlite(client, project):
    assert client.get(f'{API}/projects/stats').status_code == 200


def test_unpublished_project_is_private_everywhere(client, farmer_user, other_investor, admin):
    draft = draft_project(farmer_user)
    urls = [f'{API}/projects/{draft.id}', f'{API}/projects/slug/{draft.slug}',
            f'{API}/projects/{draft.id}/contributions', f'{API}/projects/{draft.id}/updates',
            f'{API}/harvest-updates/projects/{draft.id}']
    for url in urls:
        assert client.get(url).status_code == 404, url
    login_as(client, other_investor)
    assert all(client.get(url).status_code == 404 for url in urls)
    for allowed in (farmer_user, admin):
        login_as(client, allowed)
        assert all(client.get(url).status_code == 200 for url in urls)


# ===================================================================== création
@pytest.mark.parametrize('bad', [
    {'amount_needed': -5}, {'amount_needed': 'abc'}, {'amount_needed': 'Infinity'}, {'amount_needed': 0},
    {'min_investment': 5000}, {'max_investment': 1}, {'min_investment': 0},
    {'deadline': 'bientôt'}, {'deadline': '2000-01-01T00:00:00Z'},
    {'currency': 'XXX'}, {'image_url': 'javascript:alert(1)'}, {'title': 'ab'}, {'title': 5}])
def test_create_project_rejects_invalid_input(client, farmer_user, bad):
    login_as(client, farmer_user)
    payload = {'title': 'Maïs', 'description': 'd', 'amount_needed': 1000, 'deadline': future(), **bad}
    assert client.post(f'{API}/projects', json=payload).status_code == 400, bad
    assert Project.query.count() == 0


def test_create_project_ok_and_roles(client, farmer_user, investor):
    payload = {'title': 'Maïs', 'description': 'd', 'amount_needed': 1000, 'deadline': future(),
               'min_investment': 50, 'currency': 'htg', 'image_url': IMAGE}
    login_as(client, investor)
    assert client.post(f'{API}/projects', json=payload).status_code == 403
    login_as(client, farmer_user)
    assert client.post(f'{API}/projects', json={}).status_code == 400
    resp = client.post(f'{API}/projects', json=payload)
    assert resp.status_code == 201
    project = Project.query.one()
    assert (project.currency, project.status, project.is_published) == ('HTG', 'draft', False)
    assert project.deadline.tzinfo is None  # stocké en UTC naïf, comme le reste du modèle


# ================================================================ mise à jour
def test_update_rules(client, project, other_investor, farmer_user, admin):
    owner = owner_of(project)
    url = f'{API}/projects/{project.id}'
    login_as(client, other_investor)
    assert client.put(url, json={'title': 'Volé'}).status_code == 403
    login_as(client, farmer_user)
    assert client.put(url, json={'title': 'Volé'}).status_code == 403
    login_as(client, owner)
    ok = client.put(url, json={'title': 'Café bio', 'farmer_id': 999, 'status': 'funded', 'amount_raised': 1e6})
    assert ok.status_code == 200
    project = db.session.get(Project, project.id)
    assert (project.title, project.farmer_id, project.status, project.amount_raised) == (
        'Café bio', owner.id, 'published', 0)  # champs sensibles ignorés
    # projet publié : les conditions financières sont figées pour l'agriculteur
    for field, value in (('amount_needed', 1), ('min_investment', 1), ('deadline', future(90)), ('currency', 'USD')):
        assert client.put(url, json={field: value}).status_code == 403, field
    login_as(client, admin)
    assert client.put(url, json={'min_investment': 20}).status_code == 200


def test_admin_cannot_lower_target_below_raised_amount(client, project, admin):
    project.amount_raised = Decimal('600')
    db.session.commit()
    login_as(client, admin)
    resp = client.put(f'{API}/projects/{project.id}', json={'amount_needed': 500})
    assert resp.status_code == 400
    assert db.session.get(Project, project.id).amount_needed == Decimal('1000000')


def test_draft_project_financial_fields_are_editable_until_publication(client, farmer_user):
    draft = draft_project(farmer_user)
    login_as(client, farmer_user)
    assert client.put(f'{API}/projects/{draft.id}', json={'amount_needed': 2000}).status_code == 200
    draft.amount_raised = Decimal('10')
    db.session.commit()
    assert client.put(f'{API}/projects/{draft.id}', json={'amount_needed': 3000}).status_code == 403  # déjà des fonds


# ================================================================= publication
def test_publish_flow_and_guards(client, farmer_user, other_investor):
    draft = draft_project(farmer_user, image_url=None)
    url = f'{API}/projects/{draft.id}/publish'
    login_as(client, other_investor)
    assert client.post(url).status_code == 403
    login_as(client, farmer_user)
    assert client.post(url).status_code == 400  # image requise
    draft.image_url = IMAGE
    db.session.commit()
    assert client.post(url).status_code == 200
    assert db.session.get(Project, draft.id).is_published is True
    assert client.post(url).status_code == 409  # déjà publié


def test_expired_or_closed_projects_cannot_be_published(client, farmer_user):
    expired = draft_project(farmer_user, slug='old', deadline=datetime.utcnow() - timedelta(days=1))
    cancelled = draft_project(farmer_user, slug='c', status=ProjectStatus.CANCELLED)
    login_as(client, farmer_user)
    assert client.post(f'{API}/projects/{expired.id}/publish').status_code == 400
    assert client.post(f'{API}/projects/{cancelled.id}/publish').status_code == 409


def test_moderation_mode_sends_projects_to_the_admin_queue(client, app, farmer_user, admin):
    app.config['REQUIRE_PROJECT_APPROVAL'] = True
    draft = draft_project(farmer_user)
    login_as(client, farmer_user)
    resp = client.post(f'{API}/projects/{draft.id}/publish')
    assert resp.status_code == 202
    draft = db.session.get(Project, draft.id)
    assert (draft.status, draft.is_published) == ('pending', False)
    assert client.get(f'{API}/projects/{draft.id}').status_code == 200  # visible du propriétaire seulement
    login_as(client, admin)
    assert [p['id'] for p in client.get(f'{API}/admin/projects/pending').get_json()['projects']] == [draft.id]
    assert client.post(f'{API}/admin/projects/{draft.id}/approve').status_code == 200
    assert db.session.get(Project, draft.id).is_published is True


def test_web_publish_follows_the_same_rules(client, app, farmer_user):
    draft = draft_project(farmer_user)
    login_as(client, farmer_user)
    app.config['REQUIRE_PROJECT_APPROVAL'] = True
    client.post(f'/project/{draft.id}/publish')
    assert db.session.get(Project, draft.id).status == 'pending'
    app.config['REQUIRE_PROJECT_APPROVAL'] = False
    client.post(f'/project/{draft.id}/publish')
    assert db.session.get(Project, draft.id).status == 'published'
    client.post(f'/project/{draft.id}/publish')  # déjà publié : sans effet
    assert db.session.get(Project, draft.id).status == 'published'


# ====================================================================== profils
@pytest.mark.parametrize('bad', [
    {'preferred_currency': 'XXX'}, {'preferred_language': 'es'}, {'country': 'HAITI'}, {'country': 'H1'},
    {'name': ''}, {'name': 'x' * 101}, {'phone': '1' * 21}, {'sms_alerts_enabled': 'yes'},
    {'avatar_url': 'javascript:alert(1)'}, {'bio': 5}])
def test_profile_update_rejects_invalid_values(client, investor, bad):
    login_as(client, investor)
    assert client.put(f'{API}/users/{investor.id}', json=bad).status_code == 400, bad


def test_profile_update_ok_and_privilege_rules(client, investor, other_investor, admin):
    login_as(client, investor)
    ok = client.put(f'{API}/users/{investor.id}', json={
        'name': 'Ines D.', 'country': 'us', 'preferred_currency': 'eur', 'preferred_language': 'fr',
        'role': 'admin', 'is_admin': True, 'sms_alerts_enabled': True})
    assert ok.status_code == 200
    user = db.session.get(User, investor.id)
    assert (user.country, user.preferred_currency, user.role, user.is_admin) == ('US', 'EUR', UserRole.INVESTOR, False)
    assert client.put(f'{API}/users/{other_investor.id}', json={'name': 'x'}).status_code == 403
    assert client.get(f'{API}/users/{other_investor.id}').status_code == 403
    login_as(client, admin)
    assert client.put(f'{API}/users/{investor.id}', json={'role': 'superuser'}).status_code == 400
    assert client.put(f'{API}/users/{investor.id}', json={'role': 'farmer'}).status_code == 200
    assert db.session.get(User, investor.id).role == UserRole.FARMER


def test_user_listing_is_admin_only_and_capped(client, investor, admin):
    login_as(client, investor)
    assert client.get(f'{API}/users').status_code == 403
    login_as(client, admin)
    assert client.get(f'{API}/users?per_page=100000').get_json()['per_page'] == 100


def test_dashboards_only_count_confirmed_contributions(client, investor, project):
    for status in (ContributionStatus.COMPLETED, ContributionStatus.PENDING, ContributionStatus.FAILED):
        db.session.add(Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('100'),
                                    currency='HTG', amount_htg=Decimal('100'), payment_method='cash', status=status))
    db.session.commit()
    login_as(client, owner_of(project))
    farmer_view = client.get(f'{API}/users/dashboard').get_json()
    assert len(farmer_view['recent_contributions']) == 1
    login_as(client, investor)
    assert client.get(f'{API}/users/dashboard').get_json()['stats']['investments_count'] == 1


# ==================================================================== formations
@pytest.fixture()
def training(app):
    t = Training(title_ht='Teknik', description_ht='d', content_type='video',
                 content_url='https://example.com/v.mp4', category='irrigation', is_published=True)
    db.session.add(t)
    db.session.commit()
    return t


def test_unpublished_training_is_hidden(client, training, farmer_user, admin):
    training.is_published = False
    db.session.commit()
    url = f'{API}/trainings/{training.id}'
    assert client.get(url).status_code == 404
    login_as(client, farmer_user)
    assert client.get(url).status_code == 404
    assert client.post(f'{url}/progress', json={'progress_percentage': 10}).status_code == 404
    login_as(client, admin)
    assert client.get(url).status_code == 200


@pytest.mark.parametrize('bad', [{'progress_percentage': 101}, {'progress_percentage': -1},
                                 {'progress_percentage': 'x'}, {'progress_percentage': True},
                                 {'last_position_seconds': -5}, {'last_position_seconds': 'x'}])
def test_training_progress_is_validated(client, training, farmer_user, bad):
    login_as(client, farmer_user)
    assert client.post(f'{API}/trainings/{training.id}/progress', json=bad).status_code == 400
    assert TrainingProgress.query.count() == 0


def test_training_progress_flow_and_roles(client, training, farmer_user, investor):
    url = f'{API}/trainings/{training.id}/progress'
    login_as(client, investor)
    assert client.post(url, json={'progress_percentage': 50}).status_code == 403
    login_as(client, farmer_user)
    assert client.post(url, json={'progress_percentage': 50}).status_code == 200
    assert client.post(url, json={'completed': True}).get_json()['progress']['progress_percentage'] == 100
    assert client.get(f'{API}/trainings/my-progress').get_json()['stats']['completed'] == 1
    assert client.get(f'{API}/trainings?per_page=100000').get_json()['per_page'] == 100


def test_create_training_validation(client, admin, farmer_user):
    payload = {'title_ht': 'T', 'description_ht': 'd', 'content_type': 'video',
               'content_url': 'https://example.com/v.mp4', 'category': 'sol'}
    login_as(client, farmer_user)
    assert client.post(f'{API}/trainings', json=payload).status_code == 403
    login_as(client, admin)
    assert client.post(f'{API}/trainings', json={}).status_code == 400
    assert client.post(f'{API}/trainings', json={**payload, 'content_url': 'javascript:alert(1)'}).status_code == 400
    assert client.post(f'{API}/trainings', json={**payload, 'thumbnail_url': 'ftp://x'}).status_code == 400
    assert Training.query.count() == 0
    assert client.post(f'{API}/trainings', json=payload).status_code == 201


# ============================================================== mises à jour de récolte
def test_harvest_update_permissions_and_validation(client, project, other_investor, farmer_user):
    owner = owner_of(project)
    body = {'project_id': project.id, 'title': 'Récolte', 'content': 'Bonne récolte'}
    login_as(client, other_investor)
    assert client.post(f'{API}/harvest-updates', json=body).status_code == 403
    login_as(client, owner)
    for bad in ({}, {'project_id': 'x', 'title': 't', 'content': 'c'}, {**body, 'title': ''},
                {**body, 'image_url': 'javascript:alert(1)'}):
        assert client.post(f'{API}/harvest-updates', json=bad).status_code == 400, bad
    created = client.post(f'{API}/harvest-updates', json=body)
    assert created.status_code == 201
    update_id = created.get_json()['update']['id']
    assert client.put(f'{API}/harvest-updates/{update_id}', json={'title': ''}).status_code == 400
    login_as(client, farmer_user)  # autre agriculteur
    assert client.put(f'{API}/harvest-updates/{update_id}', json={'title': 'x'}).status_code == 403
    assert client.delete(f'{API}/harvest-updates/{update_id}').status_code == 403
    login_as(client, owner)
    assert client.delete(f'{API}/harvest-updates/{update_id}').status_code == 200
    assert HarvestUpdate.query.count() == 0


def test_published_update_of_an_unpublished_project_stays_private(client, farmer_user, other_investor):
    draft = draft_project(farmer_user)
    update = HarvestUpdate(project_id=draft.id, title='t', content='c', is_published=True)
    db.session.add(update)
    db.session.commit()
    assert client.get(f'{API}/harvest-updates/{update.id}').status_code == 404
    login_as(client, other_investor)
    assert client.get(f'{API}/harvest-updates/{update.id}').status_code == 404
    login_as(client, farmer_user)
    assert client.get(f'{API}/harvest-updates/{update.id}').status_code == 200
