# app/utils/storage.py
"""Stockage des images (projets, profils) : fine couche au-dessus de app.utils.file."""

from app.utils.file import save_file, delete_file


def upload_image(file, subfolder='projects', resize=None):
    """Enregistre une image uploadée. Retourne le chemin relatif, ou None si invalide."""
    return save_file(file, subfolder=subfolder, file_type='image', resize=resize)


def delete_image(path):
    """Supprime une image précédemment enregistrée. Retourne True si supprimée."""
    return delete_file(path)
