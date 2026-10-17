"""
Routes pour les cagnottes de groupe
"""

from decimal import Decimal
from datetime import datetime
from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import GroupContribution, GroupContributionInvite, Contribution, Project
from app.extensions import db
from app.utils.decorators import rate_limit


group_bp = Blueprint('groups', __name__, url_prefix='/groups')


@group_bp.route('', methods=['POST'])
@login_required
def create_group():
    """Crée une nouvelle cagnotte de groupe"""
    data = request.get_json()
    
    if not data.get('project_id') or not data.get('group_name'):
        return jsonify({'error': 'Projet et nom de groupe requis'}), 400
    
    project = Project.query.get_or_404(data['project_id'])
    
    # Vérifier que l'utilisateur peut créer une cagnotte pour ce projet
    if not current_user.is_admin and project.farmer_id != current_user.id:
        # Tout le monde peut créer une cagnotte pour un projet actif
        if project.status != 'published':
            return jsonify({'error': 'Ce projet n\'est pas disponible'}), 400
    
    group = GroupContribution(
        project_id=data['project_id'],
        created_by_id=current_user.id,
        group_name=data['group_name'],
        group_name_ht=data.get('group_name_ht'),
        group_type=data.get('group_type', 'family'),
        group_description=data.get('group_description'),
        target_amount=Decimal(str(data['target_amount'])),
        currency=data.get('currency', 'USD'),
        expires_at=datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00')) if data.get('expires_at') else None,
        max_members=data.get('max_members'),
        is_public=data.get('is_public', True),
        cover_image_url=data.get('cover_image_url')
    )
    
    db.session.add(group)
    db.session.commit()
    
    return jsonify({
        'message': 'Cagnotte créée avec succès',
        'group': group.to_dict()
    }), 201


@group_bp.route('/<int:group_id>', methods=['GET'])
def get_group(group_id):
    """Récupère une cagnotte"""
    group = GroupContribution.query.get_or_404(group_id)
    return jsonify(group.to_dict()), 200


@group_bp.route('/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id):
    """Invite des personnes à rejoindre une cagnotte"""
    group = GroupContribution.query.get_or_404(group_id)
    
    # Seul le créateur peut inviter
    if group.created_by_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    data = request.get_json()
    emails = data.get('emails', [])
    phones = data.get('phones', [])
    personal_message = data.get('personal_message')
    
    invites = []
    
    for email in emails:
        invite = GroupContributionInvite(
            group_id=group_id,
            invited_by_id=current_user.id,
            invite_email=email,
            personal_message=personal_message
        )
        db.session.add(invite)
        invites.append(invite)
        
        # Envoyer l'invitation par email (à implémenter)
        # send_group_invite_email(email, group, invite.invite_code)
    
    for phone in phones:
        invite = GroupContributionInvite(
            group_id=group_id,
            invited_by_id=current_user.id,
            invite_phone=phone,
            personal_message=personal_message
        )
        db.session.add(invite)
        invites.append(invite)
        
        # Envoyer l'invitation par SMS (à implémenter)
        # send_group_invite_sms(phone, group, invite.invite_code)
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(invites)} invitation(s) envoyée(s)',
        'invites': [i.to_dict() for i in invites]
    }), 201


@group_bp.route('/join/<invite_code>', methods=['POST'])
@login_required
def join_group(invite_code):
    """Rejoint une cagnotte via un code d'invitation"""
    invite = GroupContributionInvite.query.filter_by(
        invite_code=invite_code,
        status='pending'
    ).first()
    
    if not invite:
        return jsonify({'error': 'Invitation invalide ou expirée'}), 404
    
    group = invite.group
    
    # Vérifier si le groupe a encore de la place
    if group.max_members and group.member_count >= group.max_members:
        return jsonify({'error': 'Ce groupe a atteint son nombre maximum de membres'}), 400
    
    invite.status = 'accepted'
    invite.responded_at = utc_now()
    
    # Enregistrer que l'utilisateur a rejoint (via une contribution existante ou future)
    # La contribution réelle sera créée séparément
    
    db.session.commit()
    
    return jsonify({
        'message': 'Vous avez rejoint la cagnotte',
        'group': group.to_dict()
    }), 200


@group_bp.route('/<int:group_id>/contribute', methods=['POST'])
@login_required
def contribute_to_group(group_id):
    """Contribue à une cagnotte de groupe"""
    group = GroupContribution.query.get_or_404(group_id)
    
    data = request.get_json()
    amount = Decimal(str(data['amount']))
    
    # Créer la contribution liée au groupe
    contribution = Contribution(
        investor_id=current_user.id,
        project_id=group.project_id,
        group_id=group_id,
        amount=amount,
        currency=group.currency,
        amount_htg=amount,  # À convertir selon devise
        payment_method=data.get('payment_method', 'card'),
        investor_country=current_user.country or 'HT',
        is_anonymous=data.get('is_anonymous', False),
        message=data.get('message')
    )
    
    db.session.add(contribution)
    db.session.commit()
    
    # Mettre à jour le montant collecté du groupe
    group.add_contribution(amount)
    
    return jsonify({
        'message': 'Contribution ajoutée à la cagnotte',
        'contribution': contribution.to_dict(),
        'group': group.to_dict()
    }), 201


@group_bp.route('/my-groups', methods=['GET'])
@login_required
def get_my_groups():
    """Récupère mes cagnottes"""
    created = GroupContribution.query.filter_by(created_by_id=current_user.id).all()
    
    # Groups where user has contributed
    contributed_ids = db.session.query(Contribution.group_id).filter_by(
        investor_id=current_user.id,
        status='completed'
    ).distinct().all()
    
    contributed = GroupContribution.query.filter(
        GroupContribution.id.in_([c[0] for c in contributed_ids if c[0]])
    ).all() if contributed_ids else []
    
    return jsonify({
        'created': [g.to_dict() for g in created],
        'contributed': [g.to_dict() for g in contributed]
    }), 200