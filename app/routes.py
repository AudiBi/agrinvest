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
from app.forms import ProjectForm, RegisterForm
from app.models import User
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from sqlalchemy import func
import pandas as pd


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
    query = request.args.get('q', '').strip()
    base_query = Project.query.filter_by(status='published')

    if query:
        base_query = base_query.filter(
            Project.title.ilike(f'%{query}%') |
            Project.location.ilike(f'%{query}%')
        )

    projects = base_query.all()
    return render_template('home.html', projects=projects,
        total_projects=Project.query.filter_by(status='published').count(),
        total_invested=db.session.query(func.sum(Contribution.amount)).scalar() or 0,
        total_investors=User.query.filter_by(role='investor').count())

@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            name=form.name.data,
            email=form.email.data,
            role=form.role.data,
            password=hashed_password 
        )
        # user.password_plain = form.password.data  
        db.session.add(user)
        db.session.commit()
        flash("Compte créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html", form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and user.verify_password(password):
            login_user(user)
            flash("Connexion réussie", "success")

            if user.role == "farmer":
                return redirect(url_for("main.dashboard"))
            else:
                return redirect(url_for("main.dashboard"))
        else:
            flash("Email ou mot de passe incorrect", "danger")

    return render_template("login.html")

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté(e).", "info")
    return redirect(url_for("main.login"))

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'farmer':
        projects = Project.query.filter_by(farmer_id=current_user.id).all()
        return render_template('dashboard_farmer.html', projects=projects)
    elif current_user.role == 'investor':
        page = request.args.get('page', 1, type=int)
        project_filter = request.args.get('project_id', type=int)

        query = Contribution.query.filter_by(investor_id=current_user.id)
        if project_filter:
            query = query.filter_by(project_id=project_filter)

        contributions = query.order_by(Contribution.timestamp.desc()).paginate(page=page, per_page=5)
        
        total_invested = db.session.query(func.sum(Contribution.amount)) \
            .filter_by(investor_id=current_user.id).scalar() or 0

        all_projects = Project.query.join(Contribution).filter(
            Contribution.investor_id == current_user.id).distinct().all()

        return render_template(
            'dashboard_investor.html',
            contributions=contributions,
            total_invested=total_invested,
            all_projects=all_projects,
            selected_project=project_filter
        )

    else:
        flash("Rôle non reconnu.", "danger")
        return redirect(url_for('main.home'))
    
@bp.route('/export_contributions')
@login_required
def export_contributions():
    if current_user.role != 'investor':
        flash("Accès réservé aux investisseurs.", "danger")
        return redirect(url_for('main.dashboard'))

    contributions = Contribution.query.filter_by(investor_id=current_user.id).all()

    data = [{
        "Projet": c.project.title,
        "Montant (HTG)": c.amount,
        "Date de contribution": c.timestamp.strftime("%Y-%m-%d %H:%M")
    } for c in contributions]

    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Contributions')
    output.seek(0)

    return send_file(output,
                     download_name="historique_contributions.xlsx",
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@bp.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if current_user.role != 'farmer':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.dashboard'))

    form = ProjectForm()

    if form.validate_on_submit():
        project = Project(
            title=form.title.data,
            description=form.description.data,
            location=form.location.data,
            amount_needed=form.amount_needed.data,
            farmer_id=current_user.id,
            status='published'
        )
        db.session.add(project)
        db.session.commit()
        flash('Projet créé avec succès.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('new_project.html', form=form)


@bp.route('/project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Total déjà collecté
    total_collected = db.session.query(
        db.func.sum(Contribution.amount)
    ).filter_by(project_id=project.id).scalar() or 0

    # Calcul du pourcentage
    percent_funded = min(int((total_collected / project.amount_needed) * 100), 100)

    # Limite à 100% max visuellement
    percent_funded = min(percent_funded, 100)

    if request.method == 'POST':
        if current_user.role != 'investor' and project.status != 'funded':
            flash("Seuls les investisseurs peuvent contribuer.", "danger")
            return redirect(url_for('main.project_detail', project_id=project.id))

        try:
            amount = float(request.form['amount'])
        except ValueError:
            flash("Montant invalide.", "danger")
            return redirect(url_for('main.project_detail', project_id=project.id))
        
        remaining = project.amount_needed - total_collected

        if remaining <= 0:
            flash("Ce projet est déjà totalement financé.", "info")
            return redirect(url_for('main.project_detail',project_id=project.id))

        if amount > remaining:
            flash(f"Montant trop élevé. Il ne reste que {remaining} HTG à financer.", "warning")
            return redirect(url_for('main.project_detail', project_id=project.id))

        contribution = Contribution(
            investor_id=current_user.id,
            project_id=project.id,
            amount=amount
        )
        db.session.add(contribution)

        # Vérifier si le projet est maintenant financé
        if (total_collected + amount) >= project.amount_needed:
            project.status = 'funded'

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
        # mail.send(msg)

        flash("Contribution enregistrée. Contrat envoyé par email.", "success")
        return redirect(url_for('main.dashboard', project_id=project.id))

    return render_template('project_detail.html', project=project,
        total_collected=total_collected, percent_funded=percent_funded)

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
