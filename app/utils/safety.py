# app/utils/safety.py
"""Garde-fous pour les opérations destructrices (effacement de la base, comptes de démonstration)."""

import os
from urllib.parse import urlparse

LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')
CONFIRM_VARIABLE = 'AGRINVEST_ALLOW_DROP'


def check_safe_to_wipe(database_uri, environ=None):
    """(autorisé, raison) : peut-on effacer cette base ?

    - SQLite (fichier ou mémoire) : autorisé, c'est la base de développement.
    - Autre base sur la machine locale : seulement avec AGRINVEST_ALLOW_DROP=yes.
    - Base distante : toujours refusé (jamais d'effacement à distance depuis un script).
    """
    environ = os.environ if environ is None else environ
    uri = str(database_uri or '')
    if uri.startswith('sqlite'):
        return True, 'SQLite (base de développement)'
    host = urlparse(uri).hostname
    if host not in LOCAL_HOSTS:
        return False, f"base distante ({host or 'hôte inconnu'}) : l'effacement est interdit"
    if environ.get(CONFIRM_VARIABLE) != 'yes':
        return False, f'base locale non SQLite : définissez {CONFIRM_VARIABLE}=yes pour confirmer'
    return True, 'base locale confirmée'
