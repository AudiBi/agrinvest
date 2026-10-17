"""
Routes pour les cagnottes de groupe
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from app.models.user import utc_now
from flask import request, jsonify, Blueprint, current_app
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import GroupContribution, GroupContributionInvite, Contribution, Project
from app.extensions import db
from app.utils.decorators import rate_limit
from app.utils.validators import validate_email
from app.utils.payments import initiate_payment


group_bp = Blueprint('groups', __name__, url_prefix='/groups')

MAX_INVITES_PER_REQUEST = 20


@group_bp.route('', methods=['POST'])
@login_required
def create_group():
    """Crée une nouvelle cagnotte de groupe"""
    data = request.get_json(silent=True) or {}

    if not data.get('project_id') or not data.get('group_name'):
        return jsonify({'error': 'Projet et nom de groupe requis'}), 400

    try:
        target_amount = Decimal(str(data.get('target_amount')))
        if not target_amount.is_finite() or target_amount <= 0:
            raise InvalidOperation
        expires_at = None
        if data.get('expires_at'):
            expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            if expires_at.tzinfo:  # colonnes DateTime naïves en UTC
                expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        max_members = data.get('max_members')
        if max_members is not None and (not isinstance(max_members, int) or max_members < 1):
            raise ValueError('max_members')
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return jsonify({'error': 'target_amount (> 0), expires_at (ISO 8601) ou max_members invalide'}), 400

    currency = (data.get('currency') or 'USD').upper()
    if currency not in current_app.config['SUPPORTED_CURRENCIES']:
        return jsonify({'error': f'Devise non supportée : {currency}'}), 400

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
        target_amount=target_amount,
        currency=currency,
        expires_at=expires_at,
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

    # Une cagnotte privée n'est visible que par son créateur, un admin, ses contributeurs et invités
    if not group.is_public:
        allowed = current_user.is_authenticated and (
            current_user.is_admin or group.created_by_id == current_user.id
            or Contribution.query.filter_by(group_id=group.id, investor_id=current_user.id).first()
            or group.invites.filter_by(invite_email=current_user.email, status='accepted').first())
        if not allowed:
            return jsonify({'error': 'Cagnotte introuvable'}), 404

    return jsonify(group.to_dict()), 200


@group_bp.route('/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id):
    """Invite des personnes à rejoindre une cagnotte"""
    group = GroupContribution.query.get_or_404(group_id)
    
    # Seul le créateur peut inviter
    if group.created_by_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    data = request.get_json(silent=True) or {}
    emails = data.get('emails', [])
    phones = data.get('phones', [])
    personal_message = data.get('personal_message')

    if (not isinstance(emails, list) or not isinstance(phones, list)
            or len(emails) + len(phones) > MAX_INVITES_PER_REQUEST
            or not all(isinstance(e, str) and validate_email(e) for e in emails)
            or not all(isinstance(p, str) and p.strip() for p in phones)):
        return jsonify({'error': f'emails/phones invalides (maximum {MAX_INVITES_PER_REQUEST} invitations)'}), 400

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

    if invite.expires_at and invite.expires_at < utc_now().replace(tzinfo=None):
        invite.status = 'expired'
        db.session.commit()
        return jsonify({'error': 'Invitation invalide ou expirée'}), 404

    # Une invitation adressée à un e-mail n'est utilisable que par ce compte
    if invite.invite_email and invite.invite_email.lower() != current_user.email.lower():
        return jsonify({'error': 'Invitation invalide ou expirée'}), 404

    if not group.is_open:
        return jsonify({'error': "Cette cagnotte n'accepte plus de membres"}), 409

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
    data = request.get_json(silent=True) or {}

    try:
        amount = Decimal(str(data.get('amount')))
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return jsonify({'error': 'Montant requis et strictement positif'}), 400

    payment_method = data.get('payment_method')
    if payment_method not in ('stripe', 'paypal', 'moncash'):
        return jsonify({'error': 'Méthode de paiement invalide (stripe, paypal ou moncash)'}), 400
    if payment_method in ('stripe', 'paypal') and group.currency == 'HTG':
        return jsonify({'error': "Ce moyen de paiement n'accepte pas le HTG"}), 400

    if not group.is_open:
        return jsonify({'error': "Cette cagnotte n'accepte plus de contributions"}), 409

    project = group.project
    from app.utils.exchange_rates import get_exchange_rate
    try:
        rate_htg = get_exchange_rate(group.currency, 'HTG')
        rate_project = get_exchange_rate(group.currency, project.currency)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    can_accept, error = project.can_accept_contribution(amount * rate_project)
    if not can_accept:
        return jsonify({'error': error}), 400

    # Contribution « pending » : la cagnotte n'est créditée qu'à la confirmation du paiement
    contribution = Contribution(
        investor_id=current_user.id,
        project_id=group.project_id,
        group_id=group_id,
        amount=amount,
        currency=group.currency,
        amount_htg=(amount * rate_htg).quantize(Decimal('0.01')),
        exchange_rate=rate_htg,
        exchange_rate_date=utc_now(),
        payment_method=payment_method,
        investor_country=current_user.country or 'HT',
        is_anonymous=bool(data.get('is_anonymous', False)),
        message=data.get('message')
    )

    db.session.add(contribution)
    db.session.commit()

    try:
        payment = initiate_payment(contribution)
    except Exception as e:
        contribution.mark_failed()
        current_app.logger.error(f"Paiement cagnotte {group_id} : {e}")
        return jsonify({'error': "Le paiement n'a pas pu être initié"}), 502

    return jsonify({
        'message': 'Contribution créée : elle sera ajoutée à la cagnotte après confirmation du paiement',
        'contribution': contribution.to_dict(),
        'payment_intent': payment,
        'payment_url': payment.get('approval_url'),
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