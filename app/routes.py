from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, send_file, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from app import db, bcrypt, mail
from app.models import User, Project, Contribution
from datetime import datetime
import io, os
from xhtml2pdf import pisa

bp = Blueprint('main', __name__)

# Génération du PDF contrat
def render_contract_pdf(contribution):
    html = render_template('contract_template.html',
        date=contribution.timestamp.strftime('%d/%m/%Y'),
        investor_name=contribution.investor.name,
        farmer_name=contribution.project.farmer.name,
        amount=contribution.amount,
        project_title=contribution.project.title)
    
    pdf = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf)
    if pisa_status.err:
        return None
    pdf.seek(0)
    return pdf

# Routes
@bp.route('/')
def home():
    projects = Project.query.filter_by(status='published').all()
    return render_template('home.html', projects=projects)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé.', 'warning')
            return redirect(url_for('main.register'))

        user = User(role=role, name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Compte créé. Veuillez vous connecter.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Email ou mot de passe invalide.', 'danger')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'farmer':
        projects = Project.query.filter_by(farmer_id=current_user.id).all()
        return render_template('dashboard_farmer.html', projects=projects)
    elif current_user.role == 'investor':
        contributions = Contribution.query.filter_by(investor_id=current_user.id).all()
        return render_template('dashboard_investor.html', contributions=contributions)
    else:
        flash("Rôle non reconnu.", "danger")
        return redirect(url_for('main.home'))

@bp.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if current_user.role != 'farmer':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        location = request.form.get('location')
        amount_needed = float(request.form['amount_needed'])

        project = Project(
            title=title,
            description=description,
            location=location,
            amount_needed=amount_needed,
            farmer_id=current_user.id,
            status='published'
        )
        db.session.add(project)
        db.session.commit()
        flash('Projet créé avec succès.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('new_project.html')

@bp.route('/project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        if current_user.role != 'investor':
            flash("Seuls les investisseurs peuvent contribuer.", "danger")
            return redirect(url_for('main.project_detail', project_id=project.id))

        try:
            amount = float(request.form['amount'])
        except ValueError:
            flash("Montant invalide.", "danger")
            return redirect(url_for('main.project_detail', project_id=project.id))

        contribution = Contribution(
            investor_id=current_user.id,
            project_id=project.id,
            amount=amount
        )
        db.session.add(contribution)
        db.session.commit()

        # Générer PDF
        pdf_file = render_contract_pdf(contribution)
        if pdf_file is None:
            flash("Erreur PDF.", "danger")
            return redirect(url_for('main.dashboard'))

        # Sauver le PDF temporairement
        temp_dir = os.path.join(current_app.root_path, 'temp_pdfs')
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"contrat_{contribution.id}.pdf"
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(pdf_file.read())

        # Email de confirmation
        msg = Message("Confirmation d’investissement",
                      recipients=[current_user.email])
        msg.html = render_template('email/contribution_confirmation.html',
            investor_name=current_user.name,
            amount=amount,
            project_title=project.title,
            contract_url=url_for('main.download_contract', contribution_id=contribution.id, _external=True))
        mail.send(msg)

        flash("Contribution enregistrée. Contrat envoyé par email.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('project_detail.html', project=project)

@bp.route('/download_contract/<int:contribution_id>')
@login_required
def download_contract(contribution_id):
    contribution = Contribution.query.get_or_404(contribution_id)

    if contribution.investor_id != current_user.id and current_user.role != 'admin':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.dashboard'))

    temp_dir = os.path.join(current_app.root_path, 'temp_pdfs')
    filename = f"contrat_{contribution.id}.pdf"
    filepath = os.path.join(temp_dir, filename)

    if not os.path.exists(filepath):
        pdf_file = render_contract_pdf(contribution)
        if pdf_file is None:
            flash("Fichier introuvable.", "danger")
            return redirect(url_for('main.dashboard'))
        with open(filepath, 'wb') as f:
            f.write(pdf_file.read())

    return send_file(filepath, as_attachment=True, download_name=filename)
