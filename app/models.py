from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash
from app.config import Config

# Initialize connection once
db_client = MongoClient(Config.MONGODB_URI)
db = db_client['evoting_db']

def get_db():
    return db

def init_db():
    # Indexes for unique constraints
    db.voters.create_index('email', unique=True)
    db.voters.create_index('student_id', unique=True)
    db.admins.create_index('username', unique=True)

    try:
        if not db.admins.find_one({'username': 'admin'}):
            db.admins.insert_one({
                'username': 'admin',
                'password_hash': generate_password_hash('admin123')
            })
    except DuplicateKeyError:
        pass
