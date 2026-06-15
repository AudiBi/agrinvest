# app/utils/pdf.py
"""
Génération de PDF pour AgriInvest Haïti
"""

from flask import current_app
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfgen import canvas
import os
from datetime import datetime


def generate_investment_contract_pdf(contribution):
    """
    Génère le contrat d'investissement en PDF
    
    Args:
        contribution: Objet Contribution
    
    Returns:
        BytesIO: Fichier PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2E7D32'),
        alignment=1,
        spaceAfter=30
    )
    
    normal_style = styles['Normal']
    
    # Contenu du document
    story = []
    
    # Titre
    story.append(Paragraph("Contrat d'investissement agricole", title_style))
    story.append(Spacer(1, 20))
    
    # Date
    story.append(Paragraph(f"Fait le {datetime.now().strftime('%d/%m/%Y')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Parties
    story.append(Paragraph("<b>Entre les soussignés :</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"- {contribution.investor.name}, ci-après dénommé 'l'Investisseur'", normal_style))
    story.append(Paragraph(f"- {contribution.project.farmer.name}, ci-après dénommé 'l'Agriculteur'", normal_style))
    story.append(Spacer(1, 20))
    
    # Objet
    story.append(Paragraph("<b>Article 1 - Objet du contrat</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Le présent contrat a pour objet de formaliser l'investissement de "
        f"{contribution.amount_htg:,.0f} HTG dans le projet '{contribution.project.title}'.",
        normal_style
    ))
    story.append(Spacer(1, 20))
    
    # Utilisation des fonds
    story.append(Paragraph("<b>Article 2 - Utilisation des fonds</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Les fonds seront utilisés exclusivement pour les besoins du projet agricole.",
        normal_style
    ))
    story.append(Spacer(1, 20))
    
    # Engagement
    story.append(Paragraph("<b>Article 3 - Engagements</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "L'Agriculteur s'engage à utiliser les fonds conformément au budget présenté "
        "et à fournir des rapports d'avancement réguliers.",
        normal_style
    ))
    story.append(Spacer(1, 20))
    
    # Signatures
    story.append(Paragraph("<b>Signatures :</b>", normal_style))
    story.append(Spacer(1, 30))
    
    # Tableau des signatures
    signature_data = [
        ["L'Investisseur", "L'Agriculteur"],
        ["", ""]
    ]
    signature_table = Table(signature_data, colWidths=[6*cm, 6*cm])
    signature_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(signature_table)
    
    # Générer le PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def generate_project_report_pdf(project):
    """
    Génère un rapport de projet en PDF
    
    Args:
        project: Objet Project
    
    Returns:
        BytesIO: Fichier PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2E7D32'),
        alignment=1
    )
    
    story = []
    story.append(Paragraph(f"Rapport du projet : {project.title}", title_style))
    story.append(Spacer(1, 20))
    
    # Informations générales
    story.append(Paragraph(f"Localisation : {project.location or 'Non spécifiée'}", styles['Normal']))
    story.append(Paragraph(f"Catégorie : {project.category or 'Non spécifiée'}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Financement
    story.append(Paragraph(f"Montant collecté : {project.amount_raised:,.0f} HTG", styles['Normal']))
    story.append(Paragraph(f"Objectif : {project.amount_needed:,.0f} HTG", styles['Normal']))
    story.append(Paragraph(f"Progression : {project.progress_percentage}%", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_investment_summary_pdf(contributions):
    """
    Génère un résumé des investissements en PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph("Résumé des investissements", styles['Heading1']))
    story.append(Spacer(1, 20))
    
    total = sum(c.amount_htg for c in contributions)
    story.append(Paragraph(f"Total investi : {total:,.0f} HTG", styles['Normal']))
    story.append(Paragraph(f"Nombre de contributions : {len(contributions)}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_project_overview_pdf(project, contributions):
    """
    Génère un aperçu complet du projet
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(project.title, styles['Heading1']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(project.description, styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer