from flask import Flask, request, g
import jwt
from app.config import Config
from cryptography.fernet import Fernet
import os

ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register blueprints
    from app.routes.api_routes import api_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.voter_routes import voter_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(voter_bp)
    
    @app.before_request
    def load_jwt_voter():
        token = request.cookies.get('voter_token')
        if token:
            try:
                data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=["HS256"])
                g.voter_id = data['voter_id']
                g.voter_name = data['voter_name']
            except Exception:
                pass

    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
        
    return app
