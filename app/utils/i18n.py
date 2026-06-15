# app/utils/i18n.py
"""
Internationalisation pour AgriInvest Haïti
"""

from flask import session, request, current_app
import json
import os


# Traductions par défaut
TRANSLATIONS = {
    'fr': {
        'welcome': 'Bienvenue',
        'login': 'Connexion',
        'logout': 'Déconnexion',
        'register': 'Inscription',
        'dashboard': 'Tableau de bord',
        'projects': 'Projets',
        'invest': 'Investir',
        'amount': 'Montant',
        'date': 'Date',
        'status': 'Statut',
        'success': 'Succès',
        'error': 'Erreur',
        'warning': 'Attention',
        'info': 'Information',
        'save': 'Enregistrer',
        'cancel': 'Annuler',
        'delete': 'Supprimer',
        'edit': 'Modifier',
        'view': 'Voir',
        'search': 'Rechercher',
        'filter': 'Filtrer',
        'loading': 'Chargement...',
        'no_results': 'Aucun résultat',
        'confirm': 'Confirmer',
        'yes': 'Oui',
        'no': 'Non'
    },
    'ht': {
        'welcome': 'Byenvini',
        'login': 'Konekte',
        'logout': 'Dekonekte',
        'register': 'Enskri',
        'dashboard': 'Tablo debò',
        'projects': 'Pwojè',
        'invest': 'Envesti',
        'amount': 'Montan',
        'date': 'Dat',
        'status': 'Estati',
        'success': 'Siksè',
        'error': 'Erè',
        'warning': 'Avètisman',
        'info': 'Enfòmasyon',
        'save': 'Sove',
        'cancel': 'Anile',
        'delete': 'Efase',
        'edit': 'Modifye',
        'view': 'Wè',
        'search': 'Chèche',
        'filter': 'Filtre',
        'loading': 'Chajman...',
        'no_results': 'Pa gen rezilta',
        'confirm': 'Konfime',
        'yes': 'Wi',
        'no': 'Non'
    },
    'en': {
        'welcome': 'Welcome',
        'login': 'Login',
        'logout': 'Logout',
        'register': 'Register',
        'dashboard': 'Dashboard',
        'projects': 'Projects',
        'invest': 'Invest',
        'amount': 'Amount',
        'date': 'Date',
        'status': 'Status',
        'success': 'Success',
        'error': 'Error',
        'warning': 'Warning',
        'info': 'Info',
        'save': 'Save',
        'cancel': 'Cancel',
        'delete': 'Delete',
        'edit': 'Edit',
        'view': 'View',
        'search': 'Search',
        'filter': 'Filter',
        'loading': 'Loading...',
        'no_results': 'No results',
        'confirm': 'Confirm',
        'yes': 'Yes',
        'no': 'No'
    }
}


def get_locale():
    """
    Récupère la langue actuelle
    
    Returns:
        Code de langue
    """
    # Priorité: session > paramètre > en-tête > défaut
    lang = session.get('language')
    if lang:
        return lang
    
    lang = request.args.get('lang')
    if lang:
        return lang
    
    # En-tête Accept-Language
    best_match = request.accept_languages.best_match(['ht', 'fr', 'en'])
    if best_match:
        return best_match
    
    return 'fr'


def translate(key, lang=None, **kwargs):
    """
    Traduit une clé
    
    Args:
        key: Clé de traduction
        lang: Langue cible (optionnel)
        **kwargs: Variables de formatage
    
    Returns:
        Texte traduit
    """
    if lang is None:
        lang = get_locale()
    
    translations = TRANSLATIONS.get(lang, TRANSLATIONS['fr'])
    text = translations.get(key, key)
    
    # Formater avec les kwargs
    if kwargs:
        text = text.format(**kwargs)
    
    return text


def get_translations(lang=None):
    """
    Récupère toutes les traductions pour une langue
    
    Args:
        lang: Code de langue
    
    Returns:
        Dict des traductions
    """
    if lang is None:
        lang = get_locale()
    
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr'])