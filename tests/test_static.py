"""Garde-fous statiques : ces erreurs ne se voient qu'à l'exécution de la route concernée."""
import glob
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, 'app')
TEMPLATES = os.path.join(APP_DIR, 'templates')


def read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def test_no_undefined_names():
    pyflakes_api = pytest.importorskip('pyflakes.api')
    from pyflakes.messages import UndefinedName

    problems = []

    class Reporter:
        def unexpectedError(self, filename, msg):
            problems.append(f'{filename}: {msg}')

        def syntaxError(self, filename, msg, lineno, offset, text):
            problems.append(f'{filename}:{lineno}: erreur de syntaxe {msg}')

        def flake(self, message):
            if isinstance(message, UndefinedName):
                problems.append(f'{os.path.relpath(message.filename, ROOT)}:{message.lineno}: '
                                f'nom non défini {message.message_args[0]!r}')

    for path in glob.glob(os.path.join(APP_DIR, '**', '*.py'), recursive=True):
        pyflakes_api.check(read(path), path, Reporter())
    assert not problems, '\n'.join(problems)


def test_every_rendered_template_exists():
    missing = []
    for path in glob.glob(os.path.join(APP_DIR, '**', '*.py'), recursive=True):
        for name in re.findall(r"render_template\(\s*f?['\"]([^'\"{]+)['\"]", read(path)):
            if not os.path.exists(os.path.join(TEMPLATES, name)):
                missing.append(f'{os.path.relpath(path, ROOT)} -> {name}')
    for path in glob.glob(os.path.join(TEMPLATES, '**', '*.html'), recursive=True):
        for name in re.findall(r"\{%\s*(?:extends|include)\s+['\"]([^'\"]+)['\"]", read(path)):
            if not os.path.exists(os.path.join(TEMPLATES, name)):
                missing.append(f'{os.path.relpath(path, ROOT)} -> {name}')
    assert not missing, '\n'.join(missing)


# Gabarits ou modules non utilisés qui référencent encore des endpoints supprimés
KNOWN_DEAD = {'app/templates/home.html', 'app/utils/seo.py'}


def test_url_for_endpoints_exist(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    unknown = []
    files = (glob.glob(os.path.join(TEMPLATES, '**', '*.html'), recursive=True)
             + glob.glob(os.path.join(APP_DIR, '**', '*.py'), recursive=True))
    for path in files:
        relative = os.path.relpath(path, ROOT).replace(os.sep, '/')
        if relative in KNOWN_DEAD:
            continue
        for endpoint in re.findall(r"url_for\(\s*['\"]([\w.]+)['\"]", read(path)):
            if endpoint != 'static' and endpoint not in endpoints:
                unknown.append(f'{relative} -> {endpoint}')
    assert not unknown, '\n'.join(unknown)
