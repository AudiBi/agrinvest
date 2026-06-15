# app/utils/file.py
"""
Gestion des fichiers pour AgriInvest Haïti
"""

import os
import uuid
from flask import current_app, url_for
from werkzeug.utils import secure_filename
from PIL import Image


ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt'},
    'video': {'mp4', 'webm', 'ogg'}
}


def allowed_file(filename, file_type='image'):
    """
    Vérifie si le type de fichier est autorisé
    
    Args:
        filename: Nom du fichier
        file_type: Type de fichier ('image', 'document', 'video')
    
    Returns:
        bool: True si autorisé
    """
    if not filename or '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(file_type, set())


def save_file(file, subfolder='uploads', file_type='image', resize=None):
    """
    Sauvegarde un fichier
    
    Args:
        file: Fichier uploadé
        subfolder: Sous-dossier de destination
        file_type: Type de fichier
        resize: Taille de redimensionnement (largeur, hauteur)
    
    Returns:
        Chemin du fichier sauvegardé
    """
    if not file or not file.filename:
        return None
    
    # Vérifier l'extension
    if not allowed_file(file.filename, file_type):
        return None
    
    # Générer un nom unique
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    # Créer le dossier
    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), subfolder)
    os.makedirs(upload_folder, exist_ok=True)
    
    # Sauvegarder le fichier
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    # Redimensionner si demandé
    if resize and file_type == 'image':
        _resize_image(filepath, resize)
    
    return os.path.join(subfolder, filename)


def get_file_url(filepath):
    """
    Récupère l'URL publique d'un fichier
    
    Args:
        filepath: Chemin relatif du fichier
    
    Returns:
        URL du fichier
    """
    if not filepath:
        return None
    
    return url_for('static', filename=f'uploads/{filepath}')


def _resize_image(filepath, size):
    """
    Redimensionne une image
    
    Args:
        filepath: Chemin de l'image
        size: Tuple (largeur, hauteur)
    """
    try:
        with Image.open(filepath) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(filepath, optimize=True, quality=85)
    except Exception as e:
        current_app.logger.error(f"Image resize error: {e}")


def delete_file(filepath):
    """
    Supprime un fichier
    
    Args:
        filepath: Chemin relatif du fichier
    
    Returns:
        bool: True si supprimé
    """
    if not filepath:
        return False
    
    full_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), filepath)
    
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        current_app.logger.error(f"File delete error: {e}")
    
    return False