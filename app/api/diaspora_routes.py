"""
Routes pour les campagnes diaspora
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import DiasporaCampaign, Project, User
from app.extensions import db
from app.utils.decorators import admin_required, ambassador_required, rate_limit
import json


diaspora_bp = Blueprint('diaspora', __name__, url_prefix='/diaspora')


def _percentage(value, name):
    """Pourcentage fini entre 0 et 100."""
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > 100:
        raise ValueError(f'{name} doit être compris entre 0 et 100')
    return amount


@diaspora_bp.route('/campaigns', methods=['GET'])
def list_campaigns():
    """Liste les campagnes diaspora actives"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    country = request.args.get('country')  # Filtrer par pays cible
    
    query = DiasporaCampaign.query.filter_by(status='active')
    
    if country:
        query = query.filter(DiasporaCampaign.target_countries.contains(country))
    
    pagination = query.order_by(DiasporaCampaign.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'campaigns': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@diaspora_bp.route('/campaigns', methods=['POST'])
@login_required
def create_campaign():
    """Crée une campagne diaspora"""
    data = request.get_json(silent=True) or {}

    if not isinstance(data.get('project_id'), int):
        return jsonify({'error': 'project_id requis'}), 400
    project = Project.query.get_or_404(data['project_id'])

    # Seul le propriétaire du projet ou un admin peut créer une campagne
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403

    try:
        countries = data.get('target_countries')
        if (not isinstance(countries, list) or not countries
                or not all(isinstance(c, str) and len(c) == 2 and c.isalpha() for c in countries)):
            raise ValueError('target_countries : liste de codes pays à 2 lettres requise')
        countries = sorted({c.upper() for c in countries})
        matching_pct = _percentage(data.get('matching_fund_percentage', 0), 'matching_fund_percentage')
        commission = _percentage(data.get('ambassador_commission', 0), 'ambassador_commission')
        cap = None
        if data.get('matching_fund_cap'):
            cap = Decimal(str(data['matching_fund_cap']))
            if not cap.is_finite() or cap < 0:
                raise ValueError('matching_fund_cap invalide')
        townhall = None
        if data.get('virtual_townhall_date'):
            townhall = datetime.fromisoformat(data['virtual_townhall_date'].replace('Z', '+00:00'))
            if townhall.tzinfo:
                townhall = townhall.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, InvalidOperation, AttributeError) as e:
        return jsonify({'error': str(e) if isinstance(e, ValueError) and 'invalide' in str(e) or 'requise' in str(e)
                        or 'doit' in str(e) else 'Paramètres de campagne invalides'}), 400

    ambassador_id = data.get('ambassador_id')
    if ambassador_id is not None:
        ambassador = db.session.get(User, ambassador_id) if isinstance(ambassador_id, int) else None
        if not ambassador or ambassador.role != 'ambassador' or not ambassador.is_active:
            return jsonify({'error': 'ambassador_id doit désigner un ambassadeur actif'}), 400

    campaign = DiasporaCampaign(
        project_id=data['project_id'],
        ambassador_id=ambassador_id,
        target_countries=json.dumps(countries),
        matching_fund_percentage=matching_pct,
        matching_fund_cap=cap,
        diaspora_specific_message=data.get('diaspora_specific_message'),
        ambassador_video_url=data.get('ambassador_video_url'),
        ambassador_commission=commission,
        virtual_townhall_link=data.get('virtual_townhall_link'),
        virtual_townhall_date=townhall,
        whatsapp_group_link=data.get('whatsapp_group_link'),
        facebook_event_link=data.get('facebook_event_link')
    )
    
    db.session.add(campaign)
    db.session.commit()
    
    return jsonify({
        'message': 'Campagne diaspora créée',
        'campaign': campaign.to_dict()
    }), 201


@diaspora_bp.route('/campaigns/<int:campaign_id>', methods=['GET'])
def get_campaign(campaign_id):
    """Récupère une campagne diaspora"""
    campaign = DiasporaCampaign.query.get_or_404(campaign_id)
    return jsonify(campaign.to_dict()), 200


@diaspora_bp.route('/campaigns/<int:campaign_id>/stats', methods=['GET'])
def get_campaign_stats(campaign_id):
    """Statistiques d'une campagne"""
    campaign = DiasporaCampaign.query.get_or_404(campaign_id)
    
    # Compter les contributions par pays
    from app.models import Contribution, User
    
    contributions_by_country = db.session.query(
        User.country,
        db.func.count(Contribution.id),
        db.func.sum(Contribution.amount_htg)
    ).join(
        Contribution, Contribution.investor_id == User.id
    ).filter(
        Contribution.project_id == campaign.project_id,
        Contribution.status == 'completed',
        User.country.in_(json.loads(campaign.target_countries))
    ).group_by(User.country).all()
    
    return jsonify({
        'campaign_id': campaign_id,
        'total_raised': float(campaign.total_amount_raised),
        'contributions_count': campaign.contributions_count,
        'matching_fund_available': float(max(Decimal('0'), campaign.matching_fund_cap - campaign.total_amount_raised)) if campaign.matching_fund_cap else 0,
        'by_country': [
            {
                'country': c[0],
                'count': c[1],
                'amount': float(c[2])
            } for c in contributions_by_country
        ]
    }), 200


@diaspora_bp.route('/ambassadors', methods=['GET'])
def list_ambassadors():
    """Liste les ambassadeurs disponibles"""
    ambassadors = User.query.filter_by(
        role='ambassador',
        is_active=True,
        is_verified=True
    ).all()
    
    return jsonify({
        'ambassadors': [{
            'id': a.id,
            'name': a.name,
            'country': a.country,
            'city': a.city,
            'avatar_url': a.avatar_url,
            'bio': a.bio
        } for a in ambassadors]
    }), 200


@diaspora_bp.route('/apply-ambassador', methods=['POST'])
@login_required
@rate_limit(limit=3, per=86400)
def apply_ambassador():
    """Postule pour devenir ambassadeur : le rôle n'est accordé que par un administrateur"""
    from app.models import Notification
    data = request.get_json(silent=True) or {}

    # Vérifier si l'utilisateur est éligible (doit être diaspora)
    if not current_user.is_diaspora:
        return jsonify({'error': 'Seuls les membres de la diaspora peuvent devenir ambassadeurs'}), 400
    if current_user.role == 'ambassador':
        return jsonify({'message': 'Vous êtes déjà ambassadeur'}), 200
    if current_user.role != 'investor':
        return jsonify({'error': 'Seuls les investisseurs peuvent postuler'}), 400

    current_user.diaspora_community = data.get('diaspora_community')
    for admin in User.query.filter_by(is_admin=True, is_active=True).all():
        db.session.add(Notification(
            user_id=admin.id,
            title="Candidature d'ambassadeur",
            message=f"{current_user.name} ({current_user.email}) souhaite devenir ambassadeur.",
            notification_type='info',
            data=json.dumps({'user_id': current_user.id, 'action': 'ambassador_application'})
        ))
    db.session.commit()

    return jsonify({
        'message': 'Votre candidature a été enregistrée. Un administrateur va l\'examiner.',
        'user': current_user.to_dict()
    }), 202


@diaspora_bp.route('/my-campaigns', methods=['GET'])
@login_required
def get_my_campaigns():
    """Récupère les campagnes où l'utilisateur est ambassadeur"""
    campaigns = DiasporaCampaign.query.filter_by(
        ambassador_id=current_user.id
    ).all()
    
    return jsonify({
        'campaigns': [c.to_dict() for c in campaigns]
    }), 200