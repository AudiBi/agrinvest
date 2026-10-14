import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Le mode debug (Werkzeug) n'est activé qu'en développement explicite
    app.run(debug=os.environ.get('FLASK_ENV') == 'development')
