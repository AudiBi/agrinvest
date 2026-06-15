# app/utils/weather.py
"""
Fonctions météo pour Haïti
Intégration avec OpenWeatherMap, NOAA, CNIGS Haïti
"""

import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
from flask import current_app
from typing import Dict, List, Optional, Tuple
import hashlib
import hmac


# ============================================================================
# CONSTANTES
# ============================================================================

HAITI_DEPARTMENTS = {
    'OU': 'Ouest',
    'AR': 'Artibonite', 
    'NO': 'Nord',
    'NE': 'Nord-Est',
    'NW': 'Nord-Ouest',
    'SO': 'Sud',
    'SE': 'Sud-Est',
    'GA': 'Grand\'Anse',
    'NI': 'Nippes',
    'CE': 'Centre'
}

HAITI_CITIES = {
    'Port-au-Prince': {'lat': 18.5392, 'lng': -72.3350, 'department': 'Ouest'},
    'Cap-Haïtien': {'lat': 19.7578, 'lng': -72.2040, 'department': 'Nord'},
    'Gonaïves': {'lat': 19.4456, 'lng': -72.6890, 'department': 'Artibonite'},
    'Les Cayes': {'lat': 18.1953, 'lng': -73.7460, 'department': 'Sud'},
    'Jacmel': {'lat': 18.2342, 'lng': -72.5340, 'department': 'Sud-Est'},
    'Jérémie': {'lat': 18.6528, 'lng': -74.1130, 'department': 'Grand\'Anse'},
    'Hinche': {'lat': 19.1500, 'lng': -72.0167, 'department': 'Centre'},
    'Miragoâne': {'lat': 18.4428, 'lng': -73.0890, 'department': 'Nippes'},
    'Saint-Marc': {'lat': 19.1167, 'lng': -72.7000, 'department': 'Artibonite'},
    'Port-de-Paix': {'lat': 19.9333, 'lng': -72.8333, 'department': 'Nord-Ouest'},
    'Fort-Liberté': {'lat': 19.6667, 'lng': -71.8333, 'department': 'Nord-Est'},
}

CROP_TYPES = {
    'general': {'name': 'Général', 'advice_key': 'general'},
    'rice': {'name': 'Riz', 'advice_key': 'rice'},
    'maize': {'name': 'Maïs', 'advice_key': 'maize'},
    'beans': {'name': 'Haricot', 'advice_key': 'beans'},
    'banana': {'name': 'Banane', 'advice_key': 'banana'},
    'mango': {'name': 'Mangue', 'advice_key': 'mango'},
    'coffee': {'name': 'Café', 'advice_key': 'coffee'},
    'cacao': {'name': 'Cacao', 'advice_key': 'cacao'},
    'vegetables': {'name': 'Légumes', 'advice_key': 'vegetables'},
    'cassava': {'name': 'Manioc', 'advice_key': 'cassava'},
    'sugarcane': {'name': 'Canne à sucre', 'advice_key': 'sugarcane'}
}


# ============================================================================
# FONCTIONS PRINCIPALES
# ============================================================================

def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


def get_current_weather(lat: float = None, lng: float = None, 
                        city: str = None, department: str = None) -> Dict:
    """
    Récupère la météo actuelle pour une localisation
    
    Args:
        lat: Latitude
        lng: Longitude
        city: Nom de la ville
        department: Département d'Haïti
    
    Returns:
        Dict contenant les données météo
    """
    
    # Obtenir les coordonnées si seule la ville est fournie
    if city and not lat and not lng:
        city_data = HAITI_CITIES.get(city)
        if city_data:
            lat = city_data['lat']
            lng = city_data['lng']
            department = city_data['department']
    
    if not lat or not lng:
        # Coordonnées par défaut : Port-au-Prince
        lat = 18.5392
        lng = -72.3350
    
    # Essayer OpenWeatherMap d'abord
    weather_data = _get_weather_openweather(lat, lng)
    
    if not weather_data:
        # Fallback: NOAA
        weather_data = _get_weather_noaa(lat, lng)
    
    if not weather_data:
        # Fallback: Données simulées (en dernier recours)
        weather_data = _get_simulated_weather(lat, lng)
    
    # Ajouter les conseils agricoles
    if weather_data:
        weather_data['agricultural_advice'] = generate_agricultural_advice(weather_data)
        weather_data['location'] = {
            'lat': lat,
            'lng': lng,
            'city': city or _get_city_from_coords(lat, lng),
            'department': department or _get_department_from_coords(lat, lng)
        }
    
    return weather_data


def get_forecast(lat: float = None, lng: float = None, 
                 city: str = None, days: int = 5) -> List[Dict]:
    """
    Récupère les prévisions météo pour les prochains jours
    
    Args:
        lat: Latitude
        lng: Longitude
        city: Nom de la ville
        days: Nombre de jours (1-7)
    
    Returns:
        Liste des prévisions par jour
    """
    
    days = min(max(days, 1), 7)  # Limiter entre 1 et 7 jours
    
    # Obtenir les coordonnées
    if city and not lat and not lng:
        city_data = HAITI_CITIES.get(city)
        if city_data:
            lat = city_data['lat']
            lng = city_data['lng']
    
    if not lat or not lng:
        lat = 18.5392
        lng = -72.3350
    
    # Essayer OpenWeatherMap
    forecast = _get_forecast_openweather(lat, lng, days)
    
    if not forecast:
        # Fallback: NOAA
        forecast = _get_forecast_noaa(lat, lng, days)
    
    if not forecast:
        # Fallback: Données simulées
        forecast = _get_simulated_forecast(lat, lng, days)
    
    # Ajouter les alertes potentielles
    for day in forecast:
        day['alerts'] = _check_weather_alerts(day)
        day['agricultural_advice'] = generate_agricultural_advice(day)
    
    return forecast


def get_weather_alert(zone: str = None, department: str = None) -> List[Dict]:
    """
    Récupère les alertes météo actives pour une zone
    
    Args:
        zone: Zone spécifique
        department: Département d'Haïti
    
    Returns:
        Liste des alertes actives
    """
    alerts = []
    
    # Récupérer depuis l'API NOAA pour les cyclones
    cyclone_alerts = _get_cyclone_alerts_noaa()
    if cyclone_alerts:
        alerts.extend(cyclone_alerts)
    
    # Récupérer depuis OpenWeatherMap
    weather_alerts = _get_weather_alerts_openweather()
    if weather_alerts:
        alerts.extend(weather_alerts)
    
    # Filtrer par zone/département
    if zone:
        alerts = [a for a in alerts if a.get('zone') == zone or zone in a.get('zones', [])]
    if department:
        alerts = [a for a in alerts if a.get('department') == department]
    
    return alerts


def generate_agricultural_advice(weather_data: Dict, crop_type: str = 'general') -> Dict:
    """
    Génère des conseils agricoles basés sur les conditions météo
    
    Args:
        weather_data: Données météo
        crop_type: Type de culture
    
    Returns:
        Dict contenant les conseils
    """
    
    if not weather_data:
        return {'advice': 'Données météo non disponibles', 'actions': []}
    
    temperature = weather_data.get('temperature', 25)
    humidity = weather_data.get('humidity', 70)
    rain = weather_data.get('rain', 0)
    wind_speed = weather_data.get('wind_speed', 0)
    condition = weather_data.get('condition', 'clear').lower()
    
    advice = {
        'crop_type': crop_type,
        'crop_name': CROP_TYPES.get(crop_type, CROP_TYPES['general'])['name'],
        'temperature': temperature,
        'humidity': humidity,
        'rain': rain,
        'wind_speed': wind_speed,
        'advices': [],
        'warnings': [],
        'actions': []
    }
    
    # Conseils basés sur la température
    if temperature > 35:
        advice['warnings'].append("Température très élevée (>35°C). Risque de stress hydrique.")
        advice['actions'].append("Arroser tôt le matin ou tard le soir")
        advice['actions'].append("Utiliser du paillage pour conserver l'humidité")
    elif temperature > 30:
        advice['advices'].append("Température élevée. Surveiller l'évaporation.")
        advice['actions'].append("Augmenter légèrement l'irrigation")
    elif temperature < 20:
        advice['advices'].append("Température fraîche. Croissance ralentie.")
        advice['actions'].append("Protéger les jeunes plants")
    
    # Conseils basés sur l'humidité
    if humidity > 85:
        advice['warnings'].append("Humidité très élevée. Risque de maladies fongiques.")
        advice['actions'].append("Éviter d'irriguer le feuillage")
        advice['actions'].append("Assurer une bonne circulation d'air")
    elif humidity < 40:
        advice['advices'].append("Humidité faible. Risque de dessèchement.")
        advice['actions'].append("Augmenter l'irrigation")
    
    # Conseils basés sur la pluie
    if rain > 50:
        advice['warnings'].append("Fortes pluies annoncées. Risque d'inondation.")
        advice['actions'].append("Vérifier le drainage des parcelles")
        advice['actions'].append("Protéger les cultures sensibles")
        advice['actions'].append("Reporter les épandages d'engrais")
    elif rain > 20:
        advice['advices'].append("Pluies modérées attendues.")
        advice['actions'].append("Bon moment pour la plantation")
        advice['actions'].append("Réduire l'irrigation prévue")
    elif rain == 0:
        advice['advices'].append("Pas de pluie prévue.")
        advice['actions'].append("Maintenir l'irrigation")
    
    # Conseils basés sur le vent
    if wind_speed > 50:
        advice['warnings'].append("Vents forts (>50 km/h). Danger pour les cultures.")
        advice['actions'].append("Renforcer les tuteurs")
        advice['actions'].append("Protéger les serres")
        advice['actions'].append("Récolter les fruits mûrs")
    elif wind_speed > 30:
        advice['advices'].append("Vent modéré.")
        advice['actions'].append("Vérifier les attaches des plants")
    
    # Conseils spécifiques par culture
    crop_specific = _get_crop_specific_advice(crop_type, weather_data)
    advice['advices'].extend(crop_specific.get('advices', []))
    advice['warnings'].extend(crop_specific.get('warnings', []))
    advice['actions'].extend(crop_specific.get('actions', []))
    
    # Conseils saisonniers
    seasonal = _get_seasonal_advice(weather_data)
    advice['advices'].extend(seasonal.get('advices', []))
    
    # Condition générale
    if condition in ['thunderstorm', 'heavy rain']:
        advice['severity'] = 'warning'
    elif condition in ['rain', 'drizzle']:
        advice['severity'] = 'info'
    else:
        advice['severity'] = 'normal'
    
    return advice


def get_department_weather(department: str) -> Dict:
    """
    Récupère la météo pour tout un département
    """
    cities_in_department = [
        city for city, data in HAITI_CITIES.items() 
        if data['department'] == department
    ]
    
    if not cities_in_department:
        return {'error': f'Département {department} non trouvé'}
    
    # Prendre la principale ville du département
    main_city = cities_in_department[0]
    weather = get_current_weather(city=main_city)
    
    # Ajouter les alertes du département
    weather['department'] = department
    weather['department_alerts'] = get_weather_alert(department=department)
    
    return weather


def get_all_departments_weather() -> Dict:
    """
    Récupère la météo pour tous les départements d'Haïti
    """
    result = {}
    for dept_key, dept_name in HAITI_DEPARTMENTS.items():
        result[dept_key] = get_department_weather(dept_name)
    return result


def check_extreme_weather(lat: float = None, lng: float = None) -> Dict:
    """
    Vérifie les conditions météo extrêmes (cyclones, tempêtes)
    """
    weather = get_current_weather(lat, lng)
    
    alerts = {
        'has_alert': False,
        'alert_type': None,
        'severity': None,
        'message': None,
        'actions': []
    }
    
    if not weather:
        return alerts
    
    wind_speed = weather.get('wind_speed', 0)
    condition = weather.get('condition', '').lower()
    
    # Détection cyclone/tempête
    if wind_speed > 118:
        alerts.update({
            'has_alert': True,
            'alert_type': 'cyclone',
            'severity': 'critical',
            'message': 'Alerte cyclone - Vents extrêmement violents',
            'actions': [
                'Mettre tout le personnel en sécurité',
                'Protéger les infrastructures agricoles',
                'Récolter d\'urgence les cultures mûres',
                'Dégager les canaux d\'évacuation'
            ]
        })
    elif wind_speed > 88:
        alerts.update({
            'has_alert': True,
            'alert_type': 'tempete_tropicale',
            'severity': 'warning',
            'message': 'Tempête tropicale - Vents dangereux annoncés',
            'actions': [
                'Renforcer les structures légères',
                'Surveiller l\'évolution',
                'Préparer le matériel d\'urgence'
            ]
        })
    elif 'thunderstorm' in condition:
        alerts.update({
            'has_alert': True,
            'alert_type': 'orage',
            'severity': 'warning',
            'message': 'Orages violents attendus',
            'actions': [
                'Mettre les équipements électriques à l\'abri',
                'Éviter de travailler en plein champ',
                'Protéger le bétail'
            ]
        })
    
    # Détection inondation
    rain = weather.get('rain_24h', 0)
    if rain > 100:
        alerts.update({
            'has_alert': True,
            'alert_type': 'inondation',
            'severity': 'critical',
            'message': f'Risque d\'inondation - {rain}mm de pluie attendus',
            'actions': [
                'Vérifier le système de drainage',
                'Évacuer les zones à risque',
                'Protéger les semences et récoltes'
            ]
        })
    elif rain > 50:
        if not alerts['has_alert']:
            alerts.update({
                'has_alert': True,
                'alert_type': 'forte_pluie',
                'severity': 'warning',
                'message': f'Fortes pluies attendues - {rain}mm',
                'actions': [
                    'Vérifier les canaux',
                    'Protéger les cultures sensibles'
                ]
            })
    
    return alerts


# ============================================================================
# FONCTIONS INTERNES - API EXTERNES
# ============================================================================

def _get_weather_openweather(lat: float, lng: float) -> Optional[Dict]:
    """Récupère la météo depuis OpenWeatherMap"""
    try:
        api_key = current_app.config.get('OPENWEATHER_API_KEY')
        if not api_key:
            return None
        
        url = f"{current_app.config['OPENWEATHER_API_URL']}/weather"
        params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'metric',
            'lang': 'fr'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            return {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'condition': data['weather'][0]['description'],
                'condition_code': data['weather'][0]['id'],
                'icon': data['weather'][0]['icon'],
                'wind_speed': data['wind']['speed'],
                'wind_gust': data['wind'].get('gust', 0),
                'rain': data.get('rain', {}).get('1h', 0),
                'clouds': data['clouds']['all'],
                'visibility': data.get('visibility', 10000),
                'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).isoformat(),
                'sunset': datetime.fromtimestamp(data['sys']['sunset']).isoformat(),
                'source': 'openweathermap',
                'timestamp': utc_now().isoformat()
            }
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"OpenWeatherMap error: {str(e)}")
        return None


def _get_forecast_openweather(lat: float, lng: float, days: int) -> Optional[List[Dict]]:
    """Récupère les prévisions depuis OpenWeatherMap"""
    try:
        api_key = current_app.config.get('OPENWEATHER_API_KEY')
        if not api_key:
            return None
        
        url = f"{current_app.config['OPENWEATHER_API_URL']}/forecast"
        params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'metric',
            'lang': 'fr',
            'cnt': days * 8  # 8 prévisions par jour (3h intervalle)
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Grouper par jour
            forecast_by_day = {}
            for item in data['list']:
                date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
                
                if date not in forecast_by_day:
                    forecast_by_day[date] = {
                        'date': date,
                        'temperatures': [],
                        'conditions': [],
                        'rain_total': 0,
                        'humidity_avg': 0,
                        'wind_speed_avg': 0
                    }
                
                forecast_by_day[date]['temperatures'].append(item['main']['temp'])
                forecast_by_day[date]['conditions'].append(item['weather'][0]['description'])
                forecast_by_day[date]['rain_total'] += item.get('rain', {}).get('3h', 0)
                forecast_by_day[date]['humidity_avg'] += item['main']['humidity']
                forecast_by_day[date]['wind_speed_avg'] += item['wind']['speed']
            
            # Calculer les moyennes
            result = []
            for date, f in list(forecast_by_day.items())[:days]:
                count = len(f['temperatures'])
                result.append({
                    'date': date,
                    'temperature_min': min(f['temperatures']),
                    'temperature_max': max(f['temperatures']),
                    'temperature_avg': sum(f['temperatures']) / count,
                    'condition': max(set(f['conditions']), key=f['conditions'].count),
                    'rain_total': f['rain_total'],
                    'humidity_avg': f['humidity_avg'] / count,
                    'wind_speed_avg': f['wind_speed_avg'] / count,
                    'source': 'openweathermap'
                })
            
            return result
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"OpenWeatherMap forecast error: {str(e)}")
        return None


def _get_weather_noaa(lat: float, lng: float) -> Optional[Dict]:
    """Récupère la météo depuis NOAA"""
    try:
        # NOAA API nécessite des points de grille
        # Point de grille le plus proche pour Haïti
        grid_url = f"{current_app.config['NOAA_API_URL']}/points/{lat},{lng}"
        
        response = requests.get(grid_url, timeout=10)
        if response.status_code != 200:
            return None
        
        grid_data = response.json()
        forecast_url = grid_data['properties']['forecast']
        
        response = requests.get(forecast_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data['properties']['periods'][0]
            
            return {
                'temperature': current['temperature'],
                'feels_like': current['temperature'],
                'humidity': current.get('relativeHumidity', {}).get('value', 70),
                'condition': current['shortForecast'],
                'wind_speed': float(current['windSpeed'].split()[0]) if current['windSpeed'] else 0,
                'rain': 0,  # NOAA ne donne pas la pluie directement
                'source': 'noaa',
                'timestamp': utc_now().isoformat()
            }
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"NOAA error: {str(e)}")
        return None


def _get_forecast_noaa(lat: float, lng: float, days: int) -> Optional[List[Dict]]:
    """Récupère les prévisions depuis NOAA"""
    try:
        grid_url = f"{current_app.config['NOAA_API_URL']}/points/{lat},{lng}"
        response = requests.get(grid_url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        grid_data = response.json()
        forecast_url = grid_data['properties']['forecast']
        
        response = requests.get(forecast_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            result = []
            for period in data['properties']['periods'][:days*2]:
                result.append({
                    'date': period['startTime'].split('T')[0],
                    'temperature_min': period['temperature'] if 'Night' in period['name'] else None,
                    'temperature_max': period['temperature'] if 'Day' in period['name'] else None,
                    'condition': period['shortForecast'],
                    'rain_total': 0,
                    'humidity_avg': 70,
                    'wind_speed_avg': float(period['windSpeed'].split()[0]) if period['windSpeed'] else 0,
                    'source': 'noaa'
                })
            
            return result
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"NOAA forecast error: {str(e)}")
        return None


def _get_cyclone_alerts_noaa() -> List[Dict]:
    """Récupère les alertes cyclones depuis NOAA"""
    try:
        # NHC (National Hurricane Center) Atlantic
        url = "https://www.nhc.noaa.gov/gtwo.php?basin=atlc&fdays=2"
        # Note: Une vraie intégration utiliserait l'API NHC
        # Pour l'instant, retourner une liste vide et utiliser une source fiable
        
        return []
        
    except Exception as e:
        current_app.logger.error(f"Cyclone alerts error: {str(e)}")
        return []


def _get_weather_alerts_openweather() -> List[Dict]:
    """Récupère les alertes depuis OpenWeatherMap"""
    try:
        api_key = current_app.config.get('OPENWEATHER_API_KEY')
        if not api_key:
            return []
        
        # Les alertes sont dans les prévisions
        return []
        
    except Exception:
        return []


# ============================================================================
# FONCTIONS INTERNES - SIMULATION ET FALLBACK
# ============================================================================

def _get_simulated_weather(lat: float, lng: float) -> Dict:
    """Génère des données météo simulées (fallback)"""
    # Déterminer la saison (simplifiée)
    month = utc_now().month
    
    # Haïti : saison sèche (Nov-Avril) ou humide (Mai-Oct)
    is_rainy_season = 5 <= month <= 10
    
    import random
    random.seed(int(lat * 1000 + lng * 1000 + utc_now().day))
    
    if is_rainy_season:
        temperature = 28 + random.uniform(-3, 3)
        humidity = 75 + random.uniform(-10, 10)
        rain = random.uniform(0, 15)
        condition = random.choice(['pluie légère', 'pluie modérée', 'nuageux', 'orage'])
    else:
        temperature = 26 + random.uniform(-2, 2)
        humidity = 65 + random.uniform(-10, 10)
        rain = random.uniform(0, 5)
        condition = random.choice(['ensoleillé', 'partiellement nuageux', 'clair'])
    
    return {
        'temperature': round(temperature, 1),
        'feels_like': round(temperature + random.uniform(-2, 2), 1),
        'humidity': round(humidity),
        'pressure': 1013 + random.uniform(-10, 10),
        'condition': condition,
        'condition_code': 800,
        'icon': '01d',
        'wind_speed': round(random.uniform(0, 20), 1),
        'wind_gust': round(random.uniform(0, 30), 1),
        'rain': round(rain, 1),
        'rain_24h': round(rain * 24, 1),
        'clouds': random.randint(0, 100),
        'visibility': 10000,
        'source': 'simulated',
        'timestamp': utc_now().isoformat()
    }


def _get_simulated_forecast(lat: float, lng: float, days: int) -> List[Dict]:
    """Génère des prévisions simulées (fallback)"""
    import random
    random.seed(int(lat * 1000 + lng * 1000))
    
    forecasts = []
    for i in range(days):
        day = utc_now() + timedelta(days=i+1)
        is_rainy = random.random() > 0.7
        
        forecasts.append({
            'date': day.strftime('%Y-%m-%d'),
            'temperature_min': round(22 + random.uniform(-2, 2), 1),
            'temperature_max': round(30 + random.uniform(-2, 2), 1),
            'temperature_avg': round(26 + random.uniform(-2, 2), 1),
            'condition': 'pluie' if is_rainy else 'ensoleillé',
            'rain_total': round(random.uniform(0, 20), 1) if is_rainy else 0,
            'humidity_avg': round(70 + random.uniform(-15, 15)),
            'wind_speed_avg': round(random.uniform(5, 20), 1),
            'source': 'simulated'
        })
    
    return forecasts


def _check_weather_alerts(weather_data: Dict) -> List[Dict]:
    """Vérifie si les conditions météo nécessitent des alertes"""
    alerts = []
    
    rain = weather_data.get('rain_total', 0)
    wind = weather_data.get('wind_speed_avg', 0)
    
    if rain > 50:
        alerts.append({
            'type': 'pluie_excessive',
            'severity': 'warning',
            'message': f'Fortes pluies attendues: {rain}mm'
        })
    elif rain > 100:
        alerts.append({
            'type': 'inondation',
            'severity': 'critical',
            'message': f'Risque d\'inondation: {rain}mm'
        })
    
    if wind > 50:
        alerts.append({
            'type': 'vent_fort',
            'severity': 'warning',
            'message': f'Vents forts: {wind}km/h'
        })
    elif wind > 88:
        alerts.append({
            'type': 'tempete',
            'severity': 'critical',
            'message': 'Tempête tropicale possible'
        })
    
    return alerts


def _get_crop_specific_advice(crop_type: str, weather_data: Dict) -> Dict:
    """Conseils spécifiques par type de culture"""
    advice = {'advices': [], 'warnings': [], 'actions': []}
    
    temperature = weather_data.get('temperature', 25)
    humidity = weather_data.get('humidity', 70)
    
    if crop_type == 'rice':
        if temperature < 20:
            advice['warnings'].append("Riz: Température trop basse pour la croissance")
        if humidity < 50:
            advice['actions'].append("Riz: Maintenir une lame d'eau dans les rizières")
    
    elif crop_type == 'coffee':
        if temperature > 30:
            advice['warnings'].append("Café: Température élevée - risque pour la floraison")
        advice['actions'].append("Café: Ombrager les jeunes plants")
    
    elif crop_type == 'banana':
        if wind_speed > 30:
            advice['warnings'].append("Banane: Vents dangereux - risque de casse")
            advice['actions'].append("Banane: Renforcer les tuteurs")
    
    elif crop_type == 'vegetables':
        if temperature > 32:
            advice['advices'].append("Légumes: Protéger du soleil direct")
            advice['actions'].append("Arroser fréquemment mais en petite quantité")
    
    return advice


def _get_seasonal_advice(weather_data: Dict) -> Dict:
    """Conseils saisonniers"""
    month = utc_now().month
    advice = {'advices': []}
    
    # Saison cyclonique (Juin à Novembre)
    if 6 <= month <= 11:
        advice['advices'].append("Saison cyclonique: Préparer un plan d'urgence")
        advice['advices'].append("Vérifier les systèmes de drainage")
    
    # Grande saison sèche (Décembre à Mars)
    elif month in [12, 1, 2, 3]:
        advice['advices'].append("Période sèche: Optimiser l'irrigation")
        advice['advices'].append("Bonne période pour la préparation des sols")
    
    # Saison des pluies (Avril à Mai)
    elif month in [4, 5]:
        advice['advices'].append("Début des pluies: Période idéale pour planter")
    
    return advice


def _get_city_from_coords(lat: float, lng: float) -> str:
    """Trouve la ville la plus proche des coordonnées"""
    min_distance = float('inf')
    closest_city = 'Port-au-Prince'
    
    from math import radians, sin, cos, sqrt, atan2
    
    def distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    for city, data in HAITI_CITIES.items():
        dist = distance(lat, lng, data['lat'], data['lng'])
        if dist < min_distance:
            min_distance = dist
            closest_city = city
    
    return closest_city


def _get_department_from_coords(lat: float, lng: float) -> str:
    """Trouve le département le plus proche des coordonnées"""
    city = _get_city_from_coords(lat, lng)
    return HAITI_CITIES.get(city, {}).get('department', 'Ouest')