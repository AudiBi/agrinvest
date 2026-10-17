"""
Routes pour la météo et les alertes
"""

from datetime import datetime
from app.utils.weather import generate_agricultural_advice
from app.utils.notifications import send_weather_alert_notifications
from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import WeatherAlert, WeatherSubscription, User
from app.extensions import db
from app.utils.decorators import farmer_required, admin_required
from app.utils.weather import get_current_weather, get_forecast


weather_bp = Blueprint('weather', __name__, url_prefix='/weather')


@weather_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Récupère les alertes météo actives"""
    zone = request.args.get('zone')
    department = request.args.get('department')
    severity = request.args.get('severity')
    
    now = utc_now()
    
    query = WeatherAlert.query.filter(
        WeatherAlert.is_active == True,
        WeatherAlert.starts_at <= now,
        WeatherAlert.ends_at >= now
    )
    
    if zone:
        query = query.filter_by(zone=zone)
    if department:
        query = query.filter_by(department=department)
    if severity:
        query = query.filter_by(severity=severity)
    
    alerts = query.order_by(
        WeatherAlert.severity.desc(),
        WeatherAlert.starts_at
    ).all()
    
    language = request.args.get('lang', 'ht')
    
    return jsonify({
        'alerts': [a.to_dict(language=language) for a in alerts],
        'count': len(alerts)
    }), 200


@weather_bp.route('/current', methods=['GET'])
def get_weather():
    """Récupère la météo actuelle pour une localisation"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    city = request.args.get('city')
    department = request.args.get('department')
    
    if not lat and not lng and not city:
        return jsonify({'error': 'Coordonnées ou ville requises'}), 400
    
    weather = get_current_weather(lat=lat, lng=lng, city=city, department=department)
    
    if not weather:
        return jsonify({'error': 'Impossible de récupérer la météo'}), 500
    
    return jsonify(weather), 200


@weather_bp.route('/forecast', methods=['GET'])
def get_forecast_route():
    """Récupère les prévisions météo"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    city = request.args.get('city')
    days = request.args.get('days', 5, type=int)
    
    if not lat and not lng and not city:
        return jsonify({'error': 'Coordonnées ou ville requises'}), 400
    
    forecast = get_forecast(lat=lat, lng=lng, city=city, days=days)
    
    if not forecast:
        return jsonify({'error': 'Impossible de récupérer les prévisions'}), 500
    
    return jsonify(forecast), 200


@weather_bp.route('/subscriptions', methods=['GET'])
@login_required
@farmer_required
def get_subscriptions():
    """Récupère les abonnements météo de l'agriculteur"""
    subscriptions = WeatherSubscription.query.filter_by(
        farmer_id=current_user.id,
        is_active=True
    ).all()
    
    return jsonify({
        'subscriptions': [s.to_dict() for s in subscriptions]
    }), 200


@weather_bp.route('/subscriptions', methods=['POST'])
@login_required
@farmer_required
def create_subscription():
    """Crée un abonnement météo"""
    data = request.get_json()
    
    if not data.get('zone'):
        return jsonify({'error': 'Zone requise'}), 400
    
    # Vérifier si l'abonnement existe déjà
    existing = WeatherSubscription.query.filter_by(
        farmer_id=current_user.id,
        zone=data['zone']
    ).first()
    
    if existing:
        existing.is_active = True
        existing.receive_sms = data.get('receive_sms', True)
        existing.receive_whatsapp = data.get('receive_whatsapp', False)
        existing.min_severity = data.get('min_severity', 'warning')
        existing.language = data.get('language', 'ht')
        existing.phone_number = data.get('phone_number', current_user.phone)
    else:
        subscription = WeatherSubscription(
            farmer_id=current_user.id,
            zone=data['zone'],
            receive_sms=data.get('receive_sms', True),
            receive_whatsapp=data.get('receive_whatsapp', False),
            min_severity=data.get('min_severity', 'warning'),
            language=data.get('language', 'ht'),
            phone_number=data.get('phone_number', current_user.phone)
        )
        db.session.add(subscription)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Abonnement météo créé',
        'subscription': subscription.to_dict() if 'subscription' in locals() else existing.to_dict()
    }), 201


@weather_bp.route('/subscriptions/<int:sub_id>', methods=['DELETE'])
@login_required
@farmer_required
def delete_subscription(sub_id):
    """Supprime un abonnement météo"""
    subscription = WeatherSubscription.query.get_or_404(sub_id)
    
    if subscription.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    subscription.is_active = False
    db.session.commit()
    
    return jsonify({'message': 'Abonnement supprimé'}), 200


@weather_bp.route('/agricultural-advice', methods=['GET'])
def get_agricultural_advice():
    """Récupère les conseils agricoles basés sur la météo"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    crop_type = request.args.get('crop_type', 'general')
    
    # Récupérer la météo actuelle
    weather = get_current_weather(lat=lat, lng=lng)
    
    if not weather:
        return jsonify({'error': 'Impossible de récupérer la météo'}), 500
    
    # Générer des conseils basés sur la météo
    advice = generate_agricultural_advice(weather, crop_type)
    
    return jsonify(advice), 200


@weather_bp.route('/alerts', methods=['POST'])
@login_required
@admin_required
def create_alert():
    """Crée une alerte météo (admin seulement)"""
    data = request.get_json()
    
    alert = WeatherAlert(
        zone=data['zone'],
        department=data.get('department'),
        alert_type=data['alert_type'],
        severity=data['severity'],
        message_ht=data['message_ht'],
        message_fr=data.get('message_fr'),
        message_en=data.get('message_en'),
        agricultural_advice_ht=data.get('agricultural_advice_ht'),
        agricultural_advice_fr=data.get('agricultural_advice_fr'),
        starts_at=datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')),
        ends_at=datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')),
        source=data.get('source', 'manual')
    )
    
    db.session.add(alert)
    db.session.commit()
    
    # Envoyer des notifications aux abonnés
    send_weather_alert_notifications(alert)
    
    return jsonify({
        'message': 'Alerte créée',
        'alert': alert.to_dict()
    }), 201