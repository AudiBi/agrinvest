# app/utils/weather_cache.py
"""
Système de cache pour les données météo
Réduit les appels API externes
"""

from datetime import datetime, timedelta
from functools import wraps
import json
import redis
from flask import current_app


class WeatherCache:
    """Cache Redis pour les données météo"""
    
    def __init__(self):
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialise la connexion Redis"""
        try:
            self.redis_client = redis.Redis.from_url(
                current_app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
                decode_responses=True
            )
        except Exception as e:
            current_app.logger.warning(f"Redis not available: {e}")
            self.redis_client = None
    
    def get(self, key: str) -> dict:
        """Récupère une valeur du cache"""
        if not self.redis_client:
            return None
        
        try:
            data = self.redis_client.get(f"weather:{key}")
            if data:
                return json.loads(data)
        except Exception as e:
            current_app.logger.error(f"Cache get error: {e}")
        
        return None
    
    def set(self, key: str, value: dict, ttl: int = 1800):
        """Stocke une valeur dans le cache (TTL par défaut 30 min)"""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.setex(
                f"weather:{key}",
                ttl,
                json.dumps(value)
            )
        except Exception as e:
            current_app.logger.error(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Supprime une valeur du cache"""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.delete(f"weather:{key}")
        except Exception:
            pass
    
    def clear_all(self):
        """Vide tout le cache météo"""
        if not self.redis_client:
            return
        
        try:
            keys = self.redis_client.keys("weather:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass


# Instance globale
weather_cache = WeatherCache()


def cached_weather(ttl=1800):
    """Décorateur pour mettre en cache les appels météo"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Générer une clé de cache unique
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Essayer de récupérer depuis le cache
            cached = weather_cache.get(cache_key)
            if cached:
                return cached
            
            # Appeler la fonction
            result = func(*args, **kwargs)
            
            # Stocker dans le cache
            if result:
                weather_cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator