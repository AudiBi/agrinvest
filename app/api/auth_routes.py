"""
Routes d'authentification
"""

from flask import request, jsonify, current_app, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from app.api import api_bp
from app.models import User
from app.extensions import db
from app.utils.decorators import rate_limit
from app.utils.validators import validate_email, validate_password


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['POST'])
@rate_limit(limit=10, per=3600)  # 10 tentatives par heure
def register():
    """
    Inscription utilisateur
    ---
    tags:
      - Authentification
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string}
            email: {type: string}
            password: {type: string}
            role: {type: string, enum: [investor, farmer]}
            phone: {type: string}
    responses:
      201: {description: Inscription réussie}
      400: {description: Données invalides}
      409: {description: Email déjà utilisé}
    """
    data = request.get_json()
    
    # Validation des champs obligatoires
    required_fields = ['name', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Le champ {field} est requis'}), 400
    
    # Validation email
    if not validate_email(data['email']):
        return jsonify({'error': 'Email invalide'}), 400
    
    # Validation mot de passe
    if not validate_password(data['password']):
        return jsonify({'error': 'Le mot de passe doit contenir au moins 8 caractères'}), 400
    
    # Vérifier si l'email existe déjà
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Cet email est déjà utilisé'}), 409
    
    # Créer l'utilisateur
    user = User(
        name=data['name'],
        email=data['email'],
        role=data.get('role', 'investor'),
        phone=data.get('phone'),
        location=data.get('location'),
        country=data.get('country'),
        preferred_currency=data.get('preferred_currency', 'USD'),
        preferred_language=data.get('preferred_language', 'ht')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Connexion automatique
    login_user(user)
    
    return jsonify({
        'message': 'Inscription réussie',
        'user': user.to_dict(include_email=True)
    }), 201


@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=20, per=3600)
def login():
    """
    Connexion utilisateur
    ---
    tags:
      - Authentification
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email: {type: string}
            password: {type: string}
            remember: {type: boolean}
    responses:
      200: {description: Connexion réussie}
      401: {description: Identifiants invalides}
    """
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    remember = data.get('remember', False)
    
    if not email or not password:
        return jsonify({'error': 'Email et mot de passe requis'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Email ou mot de passe invalide'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Compte désactivé'}), 401
    
    login_user(user, remember=remember)
    user.last_login_at = utc_now()
    db.session.commit()
    
    return jsonify({
        'message': 'Connexion réussie',
        'user': user.to_dict(include_email=True)
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    return jsonify({'message': 'Déconnexion réussie'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Récupère l'utilisateur connecté"""
    return jsonify(current_user.to_dict(include_email=True)), 200


@auth_bp.route('/me', methods=['PUT'])
@login_required
def update_current_user():
    """Met à jour l'utilisateur connecté"""
    data = request.get_json()
    current_user.update_profile(**data)
    return jsonify({
        'message': 'Profil mis à jour',
        'user': current_user.to_dict(include_email=True)
    }), 200


@auth_bp.route('/me/password', methods=['PUT'])
@login_required
def change_password():
    """Change le mot de passe"""
    data = request.get_json()
    
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not current_user.check_password(old_password):
        return jsonify({'error': 'Ancien mot de passe incorrect'}), 401
    
    if not validate_password(new_password):
        return jsonify({'error': 'Le nouveau mot de passe doit contenir au moins 8 caractères'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Mot de passe modifié avec succès'}), 200


@auth_bp.route('/password/reset-request', methods=['POST'])
@rate_limit(limit=3, per=3600)
def reset_password_request():
    """Demande de réinitialisation de mot de passe"""
    data = request.get_json()
    email = data.get('email')
    
    user = User.query.filter_by(email=email).first()
    if user:
        # Générer un token
        token = user.generate_reset_token()
        # Envoyer l'email (à implémenter)
        # send_reset_email(user.email, token)
        pass
    
    # Toujours retourner la même réponse pour éviter le probing
    return jsonify({'message': 'Si cet email existe, vous recevrez un lien de réinitialisation'}), 200


@auth_bp.route('/password/reset', methods=['POST'])
def reset_password():
    """Réinitialisation du mot de passe"""
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')
    
    if not validate_password(new_password):
        return jsonify({'error': 'Le mot de passe doit contenir au moins 8 caractères'}), 400
    
    user = User.verify_reset_token(token)
    if not user:
        return jsonify({'error': 'Token invalide ou expiré'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Mot de passe réinitialisé avec succès'}), 200


@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """Vérification de l'email"""
    user = User.verify_email_token(token)
    if not user:
        return jsonify({'error': 'Token invalide ou expiré'}), 400
    
    user.verify_email()
    return jsonify({'message': 'Email vérifié avec succès'}), 200