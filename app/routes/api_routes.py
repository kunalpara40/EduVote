from flask import Blueprint, jsonify
from datetime import datetime
from app.models import get_db
from app.utils import format_doc

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/results')
def api_results():
    db = get_db()
    election = format_doc(db.elections.find_one({"is_published": 1}, sort=[('_id', -1)]))
    
    if election and election.get('results_declared'):
        declared_at = election.get('results_declared_at')
        if declared_at and (datetime.now() - declared_at).total_seconds() > 600:
            return jsonify({'error': 'no active election result at that time'}), 403
            
    if election:
        candidates = list(db.candidates.find({"election_id": election['id']}, {"name": 1, "position": 1, "department": 1, "votes": 1, "_id": 0}).sort([("position", 1), ("votes", -1)]))
        total = db.votes.count_documents({"election_id": election['id']})
    else:
        candidates = list(db.candidates.find({}, {"name": 1, "position": 1, "department": 1, "votes": 1, "_id": 0}).sort([("position", 1), ("votes", -1)]))
        total = db.votes.count_documents({})
    return jsonify({'candidates': candidates, 'total_votes': total})
