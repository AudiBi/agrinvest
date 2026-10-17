"""Test de fumée : appelle chaque route avec un compte admin et des données minimales.

Lancer à la main : python tests/smoke_routes.py   (affiche les routes qui répondent 5xx)
Les POST sont appelés avec un corps vide : une réponse 4xx est attendue, jamais 5xx.
"""
import os
import sys
from decimal import Decimal

os.environ['FLASK_ENV'] = 'testing'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash as real_hash  # noqa: E402
import app.models.user as user_module  # noqa: E402

user_module.generate_password_hash = lambda p, method='pbkdf2:sha256': real_hash(p, method='pbkdf2:sha256:1000')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Contribution, Project, User  # noqa: E402
from app.models.enums import ProjectStatus, UserRole  # noqa: E402

app = create_app('testing')
app.config['SESSION_PROTECTION'] = None
app.config['PROPAGATE_EXCEPTIONS'] = False

with app.app_context():
    db.create_all()
    admin = User(email='a@x.com', password='Passw0rd!x', role=UserRole.ADMIN, is_admin=True, name='Admin')
    farmer = User(email='f@x.com', password='Passw0rd!x', role=UserRole.FARMER, name='Farmer')
    investor = User(email='i@x.com', password='Passw0rd!x', role=UserRole.INVESTOR, name='Investor')
    db.session.add_all([admin, farmer, investor])
    db.session.flush()
    project = Project(title='Café', slug='cafe', description='d', amount_needed=Decimal('1000000'),
                      farmer_id=farmer.id, status=ProjectStatus.PUBLISHED, is_published=True,
                      min_investment=Decimal('100'), currency='HTG')
    db.session.add(project)
    db.session.flush()
    contribution = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('500'),
                                currency='HTG', amount_htg=Decimal('500'), payment_method='cash')
    db.session.add(contribution)
    db.session.commit()
    ids = {'admin': admin.id, 'farmer': farmer.id, 'investor': investor.id}

    SKIP = ('/static/', '/logout', '/delete-account')
    failures = []
    total = 0
    for who, user_id in ids.items():
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if any(rule.rule.startswith(s) for s in SKIP):
                continue
            url = rule.rule
            for arg in rule.arguments:
                converter = rule._converters.get(arg)
                value = '1' if converter.__class__.__name__ == 'IntegerConverter' else 'x'
                url = url.replace(f'<int:{arg}>', value).replace(f'<{arg}>', value).replace(f'<string:{arg}>', value)
            for method in sorted(rule.methods & {'GET', 'POST', 'PUT', 'DELETE'}):
                total += 1
                try:
                    kwargs = {'json': {}} if method != 'GET' else {}
                    status = client.open(url, method=method, **kwargs).status_code
                except Exception as e:  # exception non gérée
                    status = f'EXC {type(e).__name__}: {str(e)[:80]}'
                if isinstance(status, str) or status >= 500:
                    failures.append((who, method, url, status))
                db.session.rollback()

    print(f'{total} requêtes, {len(failures)} réponses 5xx/exceptions')
    seen = set()
    for who, method, url, status in failures:
        key = (method, url, str(status))
        if key in seen:
            continue
        seen.add(key)
        print(f'  [{who}] {method} {url} -> {status}')
    db.drop_all()
