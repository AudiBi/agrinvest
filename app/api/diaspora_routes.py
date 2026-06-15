"""
Routes pour les campagnes diaspora
"""

from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import DiasporaCampaign, Project, User
from app.extensions import db
from app.utils.decorators import admin_required, ambassador_required
import json


diaspora_bp = Blueprint('diaspora', __name__, url_prefix='/diaspora')


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
    data = request.get_json()
    
    project = Project.query.get_or_404(data['project_id'])
    
    # Seul le propriétaire du projet ou un admin peut créer une campagne
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    campaign = DiasporaCampaign(
        project_id=data['project_id'],
        ambassador_id=data.get('ambassador_id'),
        target_countries=json.dumps(data['target_countries']),
        matching_fund_percentage=Decimal(str(data.get('matching_fund_percentage', 0))),
        matching_fund_cap=Decimal(str(data['matching_fund_cap'])) if data.get('matching_fund_cap') else None,
        diaspora_specific_message=data.get('diaspora_specific_message'),
        ambassador_video_url=data.get('ambassador_video_url'),
        ambassador_commission=Decimal(str(data.get('ambassador_commission', 0))),
        virtual_townhall_link=data.get('virtual_townhall_link'),
        virtual_townhall_date=datetime.fromisoformat(data['virtual_townhall_date'].replace('Z', '+00:00')) if data.get('virtual_townhall_date') else None,
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
        'matching_fund_available': float(campaign.matching_fund_cap - campaign.total_amount_raised) if campaign.matching_fund_cap else 0,
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
def apply_ambassador():
    """Postule pour devenir ambassadeur"""
    data = request.get_json()
    
    # Vérifier si l'utilisateur est éligible (doit être diaspora)
    if not current_user.is_diaspora:
        return jsonify({'error': 'Seuls les membres de la diaspora peuvent devenir ambassadeurs'}), 400
    
    # Mettre à jour le rôle
    current_user.role = 'ambassador'
    current_user.diaspora_community = data.get('diaspora_community')
    db.session.commit()
    
    return jsonify({
        'message': 'Votre candidature a été enregistrée. Un administrateur va l\'examiner.',
        'user': current_user.to_dict()
    }), 200


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