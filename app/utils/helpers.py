# app/utils/helpers.py
"""
Fonctions utilitaires pour AgriInvest Haïti
"""

from datetime import datetime, timezone
from decimal import Decimal
import re


def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


def format_currency(amount, currency='HTG'):
    """Formate un montant en devise"""
    if amount is None:
        amount = 0
    try:
        return f"{float(amount):,.0f} {currency}".replace(',', ' ')
    except (ValueError, TypeError):
        return f"0 {currency}"


def format_date(date, format_str='%d/%m/%Y'):
    """Formate une date"""
    if date:
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                return date
        return date.strftime(format_str)
    return ''


def slugify(text):
    """Convertit un texte en slug"""
    if not text:
        return ''
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text


def generate_contract_pdf(contribution):
    """Génère un contrat PDF (placeholder - à implémenter avec ReportLab)"""
    # À implémenter avec ReportLab ou autre bibliothèque PDF
    # Pour l'instant, retourne None
    return None