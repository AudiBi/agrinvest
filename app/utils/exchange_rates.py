# app/utils/exchange_rates.py
"""Taux de change. Aucun taux de repli codé en dur : sans taux fiable, on refuse."""

import time
from decimal import Decimal

import requests
from flask import current_app

_cache = {}  # base -> (timestamp, {devise: taux})


def _fetch_rates(base):
    url = f"{current_app.config['EXCHANGE_RATE_API_URL'].rstrip('/')}/{base}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    rates = response.json().get('rates')
    if not rates:
        raise ValueError('Réponse de taux de change invalide')
    return rates


def get_exchange_rate(from_currency, to_currency='HTG'):
    """Taux `from_currency` -> `to_currency` (Decimal).

    Lève ValueError pour une devise non supportée, RuntimeError si aucun taux
    (frais ni périmé) n'est disponible.
    """
    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    supported = current_app.config['SUPPORTED_CURRENCIES']
    for code in (from_currency, to_currency):
        if code not in supported:
            raise ValueError(f'Devise non supportée : {code}')
    if from_currency == to_currency:
        return Decimal('1')

    ttl = current_app.config.get('EXCHANGE_RATE_CACHE_TTL', 3600)
    cached = _cache.get(from_currency)
    if cached and time.time() - cached[0] < ttl:
        rates = cached[1]
    else:
        try:
            rates = _fetch_rates(from_currency)
            _cache[from_currency] = (time.time(), rates)
        except (requests.RequestException, ValueError) as e:
            current_app.logger.error(f'Exchange rate error: {e}')
            if not cached:
                raise RuntimeError('Taux de change indisponible') from e
            rates = cached[1]  # dernier taux connu plutôt que rien

    if to_currency not in rates:
        raise RuntimeError(f'Taux {from_currency}->{to_currency} indisponible')
    return Decimal(str(rates[to_currency]))
