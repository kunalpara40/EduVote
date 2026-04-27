from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import get_db
from app.utils import login_required, format_doc
from app.services.email_service import send_otp_email_helper
from app import cipher
import face_recognition
import base64
import numpy as np
from io import BytesIO
from PIL import Image
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
import json, jwt, random
from datetime import datetime, timedelta
from app.config import Config

voter_bp = Blueprint('voter', __name__)

@voter_bp.route('/')
def index():
    return render_template('index.html')

@voter_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        email = request.form['email']
        student_id = request.form['student_id']

        if db.voters.find_one({"$or": [{"email": email}, {"student_id": student_id}]}):
            flash('Email or Student ID already registered.', 'error')
            return render_template('register.html')

        try:
            face_image_data = request.form.get('face_image')
            if not face_image_data:
                flash('Please capture your face before registering.', 'error')
                return render_template('register.html')
            
            header, encoded = face_image_data.split(",", 1)
            img_data = base64.b64decode(encoded)
            image_np = np.array(Image.open(BytesIO(img_data)).convert('RGB'))
            
            face_encodings = face_recognition.face_encodings(image_np)
            if len(face_encodings) == 0:
                flash('No face detected in the image. Please try again.', 'error')
                return render_template('register.html')
            
            new_encoding = face_encodings[0]
            
            existing_voters = list(db.voters.find({"face_encoding": {"$ne": None}}, {"name": 1, "face_encoding": 1}))
            for voter in existing_voters:
                try:
                    db_encoding = np.array(json.loads(voter['face_encoding']))
                    match = face_recognition.compare_faces([db_encoding], new_encoding, tolerance=0.5)[0]
                    if match:
                        flash(f'Duplicate face detected. Face is already registered.', 'error')
                        return render_template('register.html')
                except (json.JSONDecodeError, TypeError):
                    continue

            otp = str(random.randint(100000, 999999))
            try:
                send_otp_email_helper(email, otp)
            except Exception as e:
                flash(f'Failed to send OTP email: {str(e)}', 'error')
                return render_template('register.html')

            pending_data = {
                "name": request.form['name'],
                "email": email,
                "gender": request.form.get('gender', 'Other'),
                "student_id": student_id,
                "password_hash": generate_password_hash(request.form['password']),
                "face_encoding": json.dumps(new_encoding.tolist()),
                "otp": otp,
                "created_at": datetime.now()
            }
            
            db.pending_voters.update_one({"email": email}, {"$set": pending_data}, upsert=True)
            session['pending_email'] = email
            
            return redirect(url_for('voter.verify_otp'))
            
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template('register.html')
            
    return render_template('register.html')

@voter_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    pending_email = session.get('pending_email')
    if not pending_email:
        flash('Session expired or invalid. Please register your details first.', 'error')
        return redirect(url_for('voter.register'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        db = get_db()
        pending_record = db.pending_voters.find_one({"email": pending_email})
        
        if not pending_record or pending_record.get('otp') != otp:
            flash('Invalid OTP. Please carefully check the code sent to your email.', 'error')
            return render_template('verify_otp.html')

        try:
            db.voters.insert_one({
                "name": pending_record['name'],
                "email": pending_record['email'],
                "gender": pending_record['gender'],
                "student_id": pending_record['student_id'],
                "password_hash": pending_record['password_hash'],
                "is_verified": 1,
                "has_voted": 0,
                "face_encoding": pending_record['face_encoding'],
                "registered_at": datetime.now()
            })
            
            db.pending_voters.delete_one({"email": pending_email})
            session.pop('pending_email', None)
            
            flash('OTP Verified! Registration successful. Please login.', 'success')
            return redirect(url_for('voter.login'))
        except DuplicateKeyError:
            flash('Error checking uniqueness constraints, please retry.', 'error')
            return redirect(url_for('voter.register'))
            
    return render_template('verify_otp.html')

@voter_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        voter = format_doc(db.voters.find_one({"student_id": request.form['student_id']}))
        if voter and check_password_hash(voter['password_hash'], request.form['password']):
            if not voter.get('is_verified', 0):
                flash('Your account is pending verification.', 'error')
                return redirect(url_for('voter.login'))
            
            from app import create_app
            token = jwt.encode({
                'voter_id': voter['id'],
                'voter_name': voter['name'],
                'exp': datetime.utcnow() + timedelta(hours=12)
            }, Config.JWT_SECRET, algorithm="HS256")
            
            resp = make_response(redirect(url_for('voter.dashboard')))
            resp.set_cookie('voter_token', token, httponly=True)
            return resp
            
        flash('Invalid Student ID or Password.', 'error')
    return render_template('login.html')

@voter_bp.route('/logout')
def logout():
    resp = make_response(redirect(url_for('voter.index')))
    resp.delete_cookie('voter_token')
    session.clear()
    return resp

@voter_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    election = format_doc(db.elections.find_one({"is_active": 1, "is_published": 1}))
    candidates = [format_doc(c) for c in db.candidates.find().sort("position", 1)]
    voter = format_doc(db.voters.find_one({"_id": ObjectId(g.voter_id)}))
    has_face = voter.get('face_encoding') is not None if voter else False
    
    has_voted = False
    if election:
        has_voted_record = db.voter_participation.find_one({
            "voter_id": g.voter_id,
            "election_id": election['id']
        })
        if has_voted_record:
            has_voted = True
    return render_template('dashboard.html', election=election, candidates=candidates, has_voted=has_voted, has_face=has_face, voter_name=getattr(g, 'voter_name', 'Voter'))

@voter_bp.route('/register_face', methods=['GET', 'POST'])
@login_required
def register_face():
    db = get_db()
    voter = format_doc(db.voters.find_one({"_id": ObjectId(g.voter_id)}))
    
    if voter and voter.get('face_encoding'):
        flash('You have already registered your face.', 'info')
        return redirect(url_for('voter.dashboard'))

    if request.method == 'POST':
        face_image_data = request.form.get('face_image')
        if not face_image_data:
            flash('Please capture your face.', 'error')
            return render_template('register_face.html')
        
        header, encoded = face_image_data.split(",", 1)
        img_data = base64.b64decode(encoded)
        image_np = np.array(Image.open(BytesIO(img_data)).convert('RGB'))
        
        face_encodings = face_recognition.face_encodings(image_np)
        if len(face_encodings) == 0:
            flash('No face detected in the image. Please try again.', 'error')
            return render_template('register_face.html')
        
        new_encoding = face_encodings[0]
        
        existing_voters = list(db.voters.find({
            "face_encoding": {"$ne": None},
            "_id": {"$ne": ObjectId(g.voter_id)}
        }))
        for v in existing_voters:
            try:
                db_encoding = np.array(json.loads(v['face_encoding']))
                match = face_recognition.compare_faces([db_encoding], new_encoding, tolerance=0.5)[0]
                if match:
                    flash('Duplicate face detected. Face is already registered.', 'error')
                    return render_template('register_face.html')
            except (json.JSONDecodeError, TypeError):
                continue
                
        db.voters.update_one(
            {"_id": ObjectId(g.voter_id)},
            {"$set": {"face_encoding": json.dumps(new_encoding.tolist())}}
        )
        flash('Face registered successfully!', 'success')
        return redirect(url_for('voter.dashboard'))
        
    return render_template('register_face.html')

@voter_bp.route('/verify_face', methods=['GET', 'POST'])
@login_required
def verify_face():
    db = get_db()
    voter = format_doc(db.voters.find_one({"_id": ObjectId(g.voter_id)}))
    
    if not voter or not voter.get('face_encoding'):
        flash('Please register your face first.', 'error')
        return redirect(url_for('voter.register_face'))

    election = format_doc(db.elections.find_one({"is_active": 1, "is_published": 1}))
    if not election:
        election = format_doc(db.elections.find_one({"is_active": 1}))
    if not election:
        flash('No active election at the moment.', 'error')
        return redirect(url_for('voter.dashboard'))

    has_voted_record = db.voter_participation.find_one({
        "voter_id": g.voter_id,
        "election_id": election['id']
    })
    if has_voted_record:
        flash('You have already cast your vote in this election!', 'error')
        return redirect(url_for('voter.dashboard'))

    if request.method == 'POST':
        face_image_data = request.form.get('face_image')
        if not face_image_data:
            flash('Please capture your face.', 'error')
            return render_template('verify_face.html')
        
        header, encoded = face_image_data.split(",", 1)
        img_data = base64.b64decode(encoded)
        image_np = np.array(Image.open(BytesIO(img_data)).convert('RGB'))
        
        face_encodings = face_recognition.face_encodings(image_np)
        if len(face_encodings) == 0:
            flash('No face detected in the image. Please try again.', 'error')
            return render_template('verify_face.html')
        
        captured_encoding = face_encodings[0]
        
        try:
            db_encoding = np.array(json.loads(voter['face_encoding']))
            match = face_recognition.compare_faces([db_encoding], captured_encoding, tolerance=0.5)[0]
            if match:
                session['face_verified'] = True
                return redirect(url_for('voter.vote'))
            else:
                flash('Face is not matching', 'error')
                return redirect(url_for('voter.index'))
        except (json.JSONDecodeError, TypeError):
            flash('Error decoding stored face. Please re-register your face.', 'error')
            return redirect(url_for('voter.index'))
            
    return render_template('verify_face.html')

@voter_bp.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    if not session.get('face_verified'):
        flash('You must verify your face before voting.', 'error')
        return redirect(url_for('voter.verify_face'))
        
    db = get_db()
    voter = format_doc(db.voters.find_one({"_id": ObjectId(g.voter_id)}))
    
    election = format_doc(db.elections.find_one({"is_active": 1, "is_published": 1}))
    if not election:
        election = format_doc(db.elections.find_one({"is_active": 1}))
    if not election:
        flash('No active election at the moment.', 'error')
        return redirect(url_for('voter.dashboard'))

    has_voted_record = db.voter_participation.find_one({
        "voter_id": g.voter_id,
        "election_id": election['id']
    })
    if has_voted_record:
        flash('You have already cast your vote in this election!', 'error')
        return redirect(url_for('voter.dashboard'))

    candidates = [format_doc(c) for c in db.candidates.find({"election_id": election['id']}).sort("position", 1)]
    if not candidates:
        all_cands = list(db.candidates.find())
        for c in all_cands:
            db.candidates.update_one({"_id": c['_id']}, {"$set": {"election_id": election['id']}})
        candidates = [format_doc(c) for c in db.candidates.find({"election_id": election['id']}).sort("position", 1)]

    if request.method == 'POST':
        selections = {}
        positions = set(c['position'] for c in candidates)
        for pos in positions:
            cid = request.form.get(f"vote_{pos.replace(' ','_')}")
            if cid:
                selections[pos] = cid

        if not selections:
            flash('Please select at least one candidate.', 'error')
            return render_template('vote.html', candidates=candidates, election=election)

        encrypted = cipher.encrypt(json.dumps(selections).encode()).decode()
        db.votes.insert_one({
            "election_id": election['id'],
            "encrypted_vote": encrypted,
            "voted_at": datetime.now()
        })
        for pos, cid in selections.items():
            db.candidates.update_one({"_id": ObjectId(cid)}, {"$inc": {"votes": 1}})
            
        db.voters.update_one({"_id": ObjectId(g.voter_id)}, {"$set": {"has_voted": 1}})
        db.voter_participation.insert_one({
            "voter_id": g.voter_id,
            "election_id": election['id'],
            "voted_at": datetime.now()
        })
        
        session.pop('face_verified', None)
        flash('✅ Your vote has been encrypted and recorded securely!', 'success')
        return redirect(url_for('voter.confirmation'))

    return render_template('vote.html', candidates=candidates, election=election)

@voter_bp.route('/confirmation')
@login_required
def confirmation():
    return render_template('confirmation.html')

@voter_bp.route('/results')
def results():
    db = get_db()
    election = format_doc(db.elections.find_one({"is_active": 1, "is_published": 1}, sort=[('_id', -1)]))
    if not election:
        election = format_doc(db.elections.find_one(sort=[('_id', -1)]))
        
    if election and election.get('results_declared'):
        declared_at = election.get('results_declared_at')
        if declared_at and (datetime.now() - declared_at).total_seconds() > 600:
            return render_template('results.html', no_active_result=True)
            
    candidates = []
    total_votes = 0
    total_voters = db.voters.count_documents({})
    
    gender_stats = {
        'registered': {
            'male': db.voters.count_documents({"gender": "male"}),
            'female': db.voters.count_documents({"gender": "female"}),
            'other': db.voters.count_documents({"gender": {"$nin": ["male", "female"]}})
        },
        'voted': {'male': 0, 'female': 0, 'other': 0}
    }
    
    if election:
        candidates = [format_doc(c) for c in db.candidates.find({"election_id": election['id']}).sort([("position", 1), ("votes", -1)])]
        if not candidates:
            candidates = [format_doc(c) for c in db.candidates.find().sort([("position", 1), ("votes", -1)])]
        total_votes = db.votes.count_documents({"election_id": election['id']})
        
        participated = list(db.voter_participation.find({"election_id": election['id']}, {"voter_id": 1}))
        voter_id_strings = [p['voter_id'] for p in participated]
        if voter_id_strings:
            voter_ids = [ObjectId(v_str) for v_str in voter_id_strings]
            gender_stats['voted']['male'] = db.voters.count_documents({"_id": {"$in": voter_ids}, "gender": "male"})
            gender_stats['voted']['female'] = db.voters.count_documents({"_id": {"$in": voter_ids}, "gender": "female"})
            gender_stats['voted']['other'] = db.voters.count_documents({"_id": {"$in": voter_ids}, "gender": {"$nin": ["male", "female"]}})
            
    return render_template('results.html', candidates=candidates, election=election,
                           total_votes=total_votes, total_voters=total_voters, 
                           gender_stats=gender_stats)
