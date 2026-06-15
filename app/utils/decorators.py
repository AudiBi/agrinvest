"""
Décorateurs pour les routes
"""

from functools import wraps
from flask import jsonify, request, current_app
from flask_login import current_user
from redis import Redis
import time


def login_required(f):
    """Vérifie que l'utilisateur est connecté"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Vérifie que l'utilisateur est administrateur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        if not current_user.is_admin:
            return jsonify({'error': 'Accès administrateur requis'}), 403
        return f(*args, **kwargs)
    return decorated_function


def farmer_required(f):
    """Vérifie que l'utilisateur est un agriculteur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        if not current_user.is_farmer and not current_user.is_admin:
            return jsonify({'error': 'Compte agriculteur requis'}), 403
        return f(*args, **kwargs)
    return decorated_function


def investor_required(f):
    """Vérifie que l'utilisateur est un investisseur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        if not current_user.is_investor and not current_user.is_admin:
            return jsonify({'error': 'Compte investisseur requis'}), 403
        return f(*args, **kwargs)
    return decorated_function


def ambassador_required(f):
    """Vérifie que l'utilisateur est un ambassadeur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        if not current_user.is_ambassador and not current_user.is_admin:
            return jsonify({'error': 'Compte ambassadeur requis'}), 403
        return f(*args, **kwargs)
    return decorated_function


def agent_required(f):
    """Vérifie que l'utilisateur est un agent de collecte"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentification requise'}), 401
        if not current_user.is_agent and not current_user.is_admin:
            return jsonify({'error': 'Compte agent requis'}), 403
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(limit=100, per=60):
    """
    Limite le nombre de requêtes par IP
    limit: nombre de requêtes max
    per: période en secondes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            redis_client = Redis.from_url(current_app.config['REDIS_URL'])
            ip = request.remote_addr
            key = f'rate_limit:{ip}:{f.__name__}'
            
            current = redis_client.get(key)
            
            if current and int(current) >= limit:
                return jsonify({'error': 'Trop de requêtes. Veuillez réessayer plus tard.'}), 429
            
            pipe = redis_client.pipeline()
            pipe.incr(key, 1)
            pipe.expire(key, per)
            pipe.execute()
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def cache_response(timeout=300):
    """Met en cache la réponse HTTP"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import make_response
            
            # Vérifier si la réponse est en cache
            # À implémenter avec Redis
            
            response = f(*args, **kwargs)
            
            if isinstance(response, tuple):
                response = make_response(response[0], response[1])
            
            response.cache_control.max_age = timeout
            response.cache_control.public = True
            
            return response
        return decorated_function
    return decorator