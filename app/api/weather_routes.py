"""
Routes pour la météo et les alertes
"""

from datetime import datetime, timezone
import re
from app.utils.weather import generate_agricultural_advice
from app.utils.notifications import send_weather_alert_notifications
from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import WeatherAlert, WeatherSubscription, User
from app.extensions import db
from app.utils.decorators import farmer_required, admin_required, rate_limit
from app.utils.weather import get_current_weather, get_forecast


weather_bp = Blueprint('weather', __name__, url_prefix='/weather')

SEVERITIES = ('info', 'warning', 'critical')
LANGUAGES = ('ht', 'fr', 'en')
PHONE_PATTERN = re.compile(r'^\+?[0-9 ()-]{7,20}$')


def _location_args():
    """(lat, lng, city) validés, ou ValueError. Les points d'accès publics appellent une API externe."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    city = (request.args.get('city') or '').strip() or None
    if (lat is None) != (lng is None):
        raise ValueError('lat et lng vont ensemble')
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError('Coordonnées hors limites')
    if lat is None and not city:
        raise ValueError('Coordonnées ou ville requises')
    if city and len(city) > 100:
        raise ValueError('city trop long')
    return lat, lng, city


def _parse_utc(value, name):
    try:
        moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'{name} invalide (format ISO 8601 attendu)')
    if moment.tzinfo:  # colonnes DateTime naïves, en UTC
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


@weather_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Récupère les alertes météo actives"""
    zone = request.args.get('zone')
    department = request.args.get('department')
    severity = request.args.get('severity')
    
    now = utc_now().replace(tzinfo=None)

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
    
    # Tri alphabétique sur le texte placerait « critical » après « warning » : on classe par gravité
    severity_rank = db.case((WeatherAlert.severity == 'critical', 0),
                            (WeatherAlert.severity == 'warning', 1), else_=2)
    alerts = query.order_by(severity_rank, WeatherAlert.starts_at).all()
    
    language = request.args.get('lang', 'ht')
    
    return jsonify({
        'alerts': [a.to_dict(language=language) for a in alerts],
        'count': len(alerts)
    }), 200


@weather_bp.route('/current', methods=['GET'])
@rate_limit(limit=30, per=60)  # point d'accès public qui consomme le quota d'une API externe
def get_weather():
    """Récupère la météo actuelle pour une localisation"""
    try:
        lat, lng, city = _location_args()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    department = request.args.get('department')

    weather = get_current_weather(lat=lat, lng=lng, city=city, department=department)

    if not weather:
        return jsonify({'error': 'Service météo indisponible'}), 503
    
    return jsonify(weather), 200


@weather_bp.route('/forecast', methods=['GET'])
@rate_limit(limit=30, per=60)
def get_forecast_route():
    """Récupère les prévisions météo"""
    try:
        lat, lng, city = _location_args()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    days = max(1, min(request.args.get('days', 5, type=int), 7))

    forecast = get_forecast(lat=lat, lng=lng, city=city, days=days)

    if not forecast:
        return jsonify({'error': 'Service météo indisponible'}), 503
    
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
    data = request.get_json(silent=True) or {}

    zone = data.get('zone')
    if not isinstance(zone, str) or not zone.strip() or len(zone) > 50:
        return jsonify({'error': 'Zone requise (50 caractères max)'}), 400
    zone = zone.strip()

    receive_sms = data.get('receive_sms', True)
    receive_whatsapp = data.get('receive_whatsapp', False)
    min_severity = data.get('min_severity', 'warning')
    language = data.get('language', 'ht')
    phone = data.get('phone_number', current_user.phone)
    if not isinstance(receive_sms, bool) or not isinstance(receive_whatsapp, bool):
        return jsonify({'error': 'receive_sms et receive_whatsapp doivent être des booléens'}), 400
    if min_severity not in SEVERITIES or language not in LANGUAGES:
        return jsonify({'error': f"min_severity ({', '.join(SEVERITIES)}) ou language ({', '.join(LANGUAGES)}) invalide"}), 400
    if phone is not None and not (isinstance(phone, str) and PHONE_PATTERN.match(phone)):
        return jsonify({'error': 'phone_number invalide'}), 400
    if (receive_sms or receive_whatsapp) and not phone:
        return jsonify({'error': 'phone_number requis pour recevoir des SMS ou des messages WhatsApp'}), 400

    data = {**data, 'zone': zone, 'phone_number': phone}

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
        'message': 'Abonnement météo créé' if not existing else 'Abonnement météo mis à jour',
        'subscription': subscription.to_dict() if 'subscription' in locals() else existing.to_dict()
    }), 200 if existing else 201


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
@rate_limit(limit=30, per=60)
def get_agricultural_advice():
    """Récupère les conseils agricoles basés sur la météo"""
    try:
        lat, lng, _city = _location_args()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    crop_type = request.args.get('crop_type', 'general')

    # Récupérer la météo actuelle
    weather = get_current_weather(lat=lat, lng=lng)

    if not weather:
        return jsonify({'error': 'Service météo indisponible'}), 503
    
    # Générer des conseils basés sur la météo
    advice = generate_agricultural_advice(weather, crop_type)
    
    return jsonify(advice), 200


@weather_bp.route('/alerts', methods=['POST'])
@login_required
@admin_required
def create_alert():
    """Crée une alerte météo (admin seulement)"""
    data = request.get_json(silent=True) or {}

    missing = [f for f in ('zone', 'alert_type', 'severity', 'message_ht', 'starts_at', 'ends_at') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Champs requis : {", ".join(missing)}'}), 400
    if data['severity'] not in SEVERITIES:
        return jsonify({'error': f"severity doit être parmi : {', '.join(SEVERITIES)}"}), 400
    if len(str(data['zone'])) > 50 or len(str(data['alert_type'])) > 30:
        return jsonify({'error': 'zone (50) ou alert_type (30) trop long'}), 400
    try:
        starts_at = _parse_utc(data['starts_at'], 'starts_at')
        ends_at = _parse_utc(data['ends_at'], 'ends_at')
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if ends_at <= starts_at:
        return jsonify({'error': 'ends_at doit être postérieur à starts_at'}), 400

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
        starts_at=starts_at,
        ends_at=ends_at,
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