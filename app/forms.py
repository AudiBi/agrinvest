from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField, PasswordField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

class RegisterForm(FlaskForm):
    role = SelectField("Rôle", choices=[("farmer", "Agriculteur"), ("investor", "Investisseur")], validators=[DataRequired()])
    name = StringField("Nom complet", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("S’inscrire")

class ProjectForm(FlaskForm):
    title = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    location = StringField('Localisation')
    amount_needed = DecimalField('Montant nécessaire (HTG)', validators=[DataRequired()])
    submit = SubmitField('Créer')