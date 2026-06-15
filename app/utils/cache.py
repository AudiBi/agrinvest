# app/utils/cache.py
"""
Système de cache pour AgriInvest Haïti
"""

from functools import wraps
from flask import current_app, request
import hashlib
import json


def get_cache_key(prefix, *args, **kwargs):
    """
    Génère une clé de cache unique
    
    Args:
        prefix: Préfixe de la clé
        *args: Arguments positionnels
        **kwargs: Arguments nommés
    
    Returns:
        Clé de cache
    """
    key_parts = [prefix]
    key_parts.extend([str(arg) for arg in args])
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    
    key_string = ':'.join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cache_result(timeout=300, key_prefix=None):
    """
    Décorateur pour mettre en cache le résultat d'une fonction
    
    Args:
        timeout: Durée de validité en secondes
        key_prefix: Préfixe personnalisé pour la clé
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Vérifier si le cache est activé
            if not current_app.config.get('CACHE_ENABLED', True):
                return f(*args, **kwargs)
            
            # Générer la clé de cache
            cache_key = key_prefix or f"{f.__module__}.{f.__name__}"
            cache_key = get_cache_key(cache_key, *args, **kwargs)
            
            # Essayer de récupérer depuis le cache
            from app.extensions import cache
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Exécuter la fonction
            result = f(*args, **kwargs)
            
            # Stocker dans le cache
            cache.set(cache_key, result, timeout=timeout)
            
            return result
        return decorated_function
    return decorator


def clear_cache(pattern=None):
    """
    Vide le cache
    
    Args:
        pattern: Pattern de clés à supprimer (optionnel)
    """
    from app.extensions import cache
    if pattern:
        # Supprimer les clés correspondant au pattern
        cache.delete_pattern(pattern)
    else:
        # Vider tout le cache
        cache.clear()


def invalidate_cache(key_prefix):
    """
    Invalide les clés de cache avec un préfixe donné
    """
    clear_cache(f"{key_prefix}*")