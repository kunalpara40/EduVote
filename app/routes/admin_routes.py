from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from app.models import get_db
from app.utils import admin_required, format_doc
from bson.objectid import ObjectId
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        db = get_db()
        admin = format_doc(db.admins.find_one({"username": request.form['username']}))
        if admin and check_password_hash(admin['password_hash'], request.form['password']):
            session['admin_id'] = admin['id']
            return redirect(url_for('admin.admin_dashboard'))
        flash('Invalid credentials ❌.', 'error')
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    db = get_db()
    elections = [format_doc(e) for e in db.elections.find().sort("created_at", -1)]
    voters = [format_doc(v) for v in db.voters.find().sort("registered_at", -1)]
    active_election = format_doc(db.elections.find_one({"is_active": 1}))
    
    total_voters = len(voters)
    voters_list = []
    
    if active_election:
        total_votes = db.votes.count_documents({"election_id": active_election['id']})
        voted_count = len(db.voter_participation.distinct("voter_id", {"election_id": active_election['id']}))
        active_voters_res = list(db.voter_participation.find({"election_id": active_election['id']}, {"voter_id": 1}))
        active_voted_set = set([r['voter_id'] for r in active_voters_res])
        for v in voters:
            v_dict = dict(v)
            v_dict['current_has_voted'] = 1 if v['id'] in active_voted_set else 0
            voters_list.append(v_dict)
    else:
        total_votes = db.votes.count_documents({})
        voted_count = db.voters.count_documents({"has_voted": 1})
        for v in voters:
            v_dict = dict(v)
            v_dict['current_has_voted'] = v.get('has_voted', 0)
            voters_list.append(v_dict)
            
    candidates = [format_doc(c) for c in db.candidates.find().sort([("election_id", 1), ("position", 1), ("votes", -1)])]
    turnout = round((voted_count / total_voters * 100), 1) if total_voters > 0 else 0
    return render_template('admin_dashboard.html',
                           elections=elections, voters=voters_list, candidates=candidates,
                           total_votes=total_votes, total_voters=total_voters,
                           voted_count=voted_count, turnout=turnout,
                           active_election=active_election)

# ── Election CRUD ─────────────────────────────────────────────────────────────
@admin_bp.route('/election/create', methods=['POST'])
@admin_required
def create_election():
    db = get_db()
    db.elections.insert_one({
        "title": request.form['title'],
        "description": request.form['description'],
        "start_time": request.form['start_time'],
        "end_time": request.form['end_time'],
        "is_active": 0,
        "is_published": 0,
        "results_declared": 0,
        "created_at": datetime.now()
    })
    flash('Election created successfully!', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/edit/<eid>', methods=['POST'])
@admin_required
def edit_election(eid):
    db = get_db()
    db.elections.update_one(
        {"_id": ObjectId(eid)},
        {"$set": {
            "title": request.form['title'],
            "description": request.form['description'],
            "start_time": request.form['start_time'],
            "end_time": request.form['end_time']
        }}
    )
    flash('Election updated successfully!', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/delete/<eid>', methods=['POST'])
@admin_required
def delete_election(eid):
    db = get_db()
    db.elections.delete_one({"_id": ObjectId(eid)})
    db.candidates.delete_many({"election_id": eid})
    flash('Election deleted.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/publish/<eid>', methods=['POST'])
@admin_required
def publish_election(eid):
    db = get_db()
    db.elections.update_one({"_id": ObjectId(eid)}, {"$set": {"is_published": 1, "is_active": 1}})
    flash('Election published and activated!', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/unpublish/<eid>', methods=['POST'])
@admin_required
def unpublish_election(eid):
    db = get_db()
    db.elections.update_one({"_id": ObjectId(eid)}, {"$set": {"is_published": 0, "is_active": 0}})
    flash('Election unpublished.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/declare/<eid>', methods=['POST'])
@admin_required
def declare_results(eid):
    db = get_db()
    db.elections.update_one({"_id": ObjectId(eid)}, {"$set": {"results_declared": 1, "is_active": 0, "results_declared_at": datetime.now()}})
    flash('Results declared! Voters can now see the results.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/election/undeclare/<eid>', methods=['POST'])
@admin_required
def undeclare_results(eid):
    db = get_db()
    db.elections.update_one({"_id": ObjectId(eid)}, {"$set": {"results_declared": 0}, "$unset": {"results_declared_at": 1}})
    flash('Results hidden from public.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

# ── Candidate CRUD ────────────────────────────────────────────────────────────
@admin_bp.route('/candidate/add', methods=['POST'])
@admin_required
def add_candidate():
    db = get_db()
    db.candidates.insert_one({
        "election_id": request.form['election_id'],
        "name": request.form['name'],
        "department": request.form['department'],
        "position": request.form['position'],
        "manifesto": request.form['manifesto'],
        "votes": 0
    })
    flash(f"Candidate '{request.form['name']}' added successfully!", 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/candidate/delete/<cid>', methods=['POST'])
@admin_required
def delete_candidate(cid):
    db = get_db()
    db.candidates.delete_one({"_id": ObjectId(cid)})
    flash('Candidate removed.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

# ── Voter Management ──────────────────────────────────────────────────────────
@admin_bp.route('/verify_voter/<voter_id>', methods=['POST'])
@admin_required
def verify_voter(voter_id):
    db = get_db()
    db.voters.update_one({"_id": ObjectId(voter_id)}, {"$set": {"is_verified": 1}})
    flash('Voter verified successfully.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/delete_voter/<voter_id>', methods=['POST'])
@admin_required
def delete_voter(voter_id):
    db = get_db()
    db.voters.delete_one({"_id": ObjectId(voter_id)})
    flash('Voter removed.', 'success')
    return redirect(url_for('admin.admin_dashboard'))
