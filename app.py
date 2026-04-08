from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import sqlite3, os, json
from datetime import datetime
from functools import wraps
import face_recognition
import base64
import numpy as np
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.secret_key = os.urandom(24)

ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect('evoting.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            gender TEXT CHECK(gender IN ('Male', 'Female', 'Other')) NOT NULL,         
            student_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            has_voted INTEGER DEFAULT 0,
            face_encoding TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            position TEXT NOT NULL,
            manifesto TEXT,
            votes INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER DEFAULT 1,
            encrypted_vote TEXT NOT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS voter_participation (
            voter_id INTEGER NOT NULL,
            election_id INTEGER NOT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (voter_id, election_id)
        );

        CREATE TABLE IF NOT EXISTS elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            is_active INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 0,
            results_declared INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    ''')

    try:
        db.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                   ('admin', generate_password_hash('admin123')))
    except: pass

    try:
        db.execute("""INSERT INTO elections (title, description, start_time, end_time, is_active, is_published, results_declared)
                      VALUES (?,?,?,?,?,?,?)""",
                #    ('Student Council Election 2025', 'Annual student council election for all positions.',
                #     '2025-01-01 00:00:00', '2025-12-31 23:59:59', 1, 1, 0)
                    )
    except: pass

    try:
        candidates = [
            # (1, 'Rahul Sharma', 'Computer Science', 'President', 'I will improve lab facilities and startup culture.'),
         
           
        ]
        for c in candidates:
            db.execute("INSERT INTO candidates (election_id, name, department, position, manifesto) VALUES (?,?,?,?,?)", c)
    except: pass

    db.commit()
    db.close()

# ── Decorators ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'voter_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ── Voter Routes ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        try:
            face_image_data = request.form.get('face_image')
            if not face_image_data:
                flash('Please capture your face before registering.', 'error')
                return render_template('register.html')
            
            # Extract base64 image data
            header, encoded = face_image_data.split(",", 1)
            img_data = base64.b64decode(encoded)
            image_np = np.array(Image.open(BytesIO(img_data)).convert('RGB'))
            
            # Get face encoding
            face_encodings = face_recognition.face_encodings(image_np)
            if len(face_encodings) == 0:
                flash('No face detected in the image. Please try again.', 'error')
                return render_template('register.html')
            
            new_encoding = face_encodings[0]
            
            # Check for duplicate face
            existing_voters = db.execute("SELECT name, face_encoding FROM voters WHERE face_encoding IS NOT NULL").fetchall()
            for voter in existing_voters:
                try:
                    db_encoding = np.array(json.loads(voter['face_encoding']))
                    match = face_recognition.compare_faces([db_encoding], new_encoding, tolerance=0.5)[0]
                    if match:
                        flash(f'Duplicate face detected. Face is already registered.', 'error')
                        return render_template('register.html')
                except json.JSONDecodeError:
                    continue

            # Face is unique, proceed with info
            db.execute(
                "INSERT INTO voters (name, email,gender, student_id, password_hash, is_verified, face_encoding) VALUES (?,?,?,?,?,?,?)",
                (request.form['name'], request.form['email'], request.form['student_id'],
                 generate_password_hash(request.form['password']), 1, json.dumps(new_encoding.tolist()))
            )
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email or Student ID already registered.', 'error')
        finally:
            db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        voter = db.execute("SELECT * FROM voters WHERE student_id=?", (request.form['student_id'],)).fetchone()
        db.close()
        if voter and check_password_hash(voter['password_hash'], request.form['password']):
            if not voter['is_verified']:
                flash('Your account is pending verification.', 'error')
                return redirect(url_for('login'))
            session['voter_id'] = voter['id']
            session['voter_name'] = voter['name']
            return redirect(url_for('dashboard'))
        flash('Invalid Student ID or Password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    election = db.execute("SELECT * FROM elections WHERE is_active=1 AND is_published=1").fetchone()
    candidates = db.execute("SELECT * FROM candidates ORDER BY position").fetchall()
    voter = db.execute("SELECT face_encoding FROM voters WHERE id=?", (session['voter_id'],)).fetchone()
    has_face = voter['face_encoding'] is not None if voter else False
    
    has_voted = False
    if election:
        has_voted_record = db.execute("SELECT 1 FROM voter_participation WHERE voter_id=? AND election_id=?", (session['voter_id'], election['id'])).fetchone()
        if has_voted_record:
            has_voted = True
    db.close()
    return render_template('dashboard.html', election=election, candidates=candidates, has_voted=has_voted, has_face=has_face)

@app.route('/register_face', methods=['GET', 'POST'])
@login_required
def register_face():
    db = get_db()
    voter = db.execute("SELECT face_encoding FROM voters WHERE id=?", (session['voter_id'],)).fetchone()
    
    if voter and voter['face_encoding']:
        flash('You have already registered your face.', 'info')
        db.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        face_image_data = request.form.get('face_image')
        if not face_image_data:
            flash('Please capture your face.', 'error')
            db.close()
            return render_template('register_face.html')
        
        # Extract base64 image data
        header, encoded = face_image_data.split(",", 1)
        img_data = base64.b64decode(encoded)
        image_np = np.array(Image.open(BytesIO(img_data)).convert('RGB'))
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(image_np)
        if len(face_encodings) == 0:
            flash('No face detected in the image. Please try again.', 'error')
            db.close()
            return render_template('register_face.html')
        
        new_encoding = face_encodings[0]
        
        # Check for duplicate face
        existing_voters = db.execute("SELECT name, face_encoding FROM voters WHERE face_encoding IS NOT NULL AND id!=?", (session['voter_id'],)).fetchall()
        for v in existing_voters:
            try:
                db_encoding = np.array(json.loads(v['face_encoding']))
                match = face_recognition.compare_faces([db_encoding], new_encoding, tolerance=0.5)[0]
                if match:
                    flash('Duplicate face detected. Face is already registered.', 'error')
                    db.close()
                    return render_template('register_face.html')
            except json.JSONDecodeError:
                continue
                
        # Save face encoding
        db.execute("UPDATE voters SET face_encoding=? WHERE id=?", (json.dumps(new_encoding.tolist()), session['voter_id']))
        db.commit()
        db.close()
        flash('Face registered successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    db.close()
    return render_template('register_face.html')


# @app.route('/verify-face',method=['GET','POST'])
@app.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    db = get_db()
    
    voter = db.execute("SELECT * FROM voters WHERE id=?", (session['voter_id'],)).fetchone()
    
    election = db.execute("SELECT * FROM elections WHERE is_active=1 AND is_published=1").fetchone()
    if not election:
        election = db.execute("SELECT * FROM elections WHERE is_active=1").fetchone()
    if not election:
        flash('No active election at the moment.', 'error')
        db.close()
        return redirect(url_for('dashboard'))

    has_voted_record = db.execute("SELECT 1 FROM voter_participation WHERE voter_id=? AND election_id=?", (session['voter_id'], election['id'])).fetchone()
    if has_voted_record:
        flash('You have already cast your vote in this election!', 'error')
        db.close()
        return redirect(url_for('dashboard'))

    candidates = db.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY position", (election['id'],)).fetchall()
    if not candidates:
        candidates = db.execute("SELECT * FROM candidates ORDER BY position").fetchall()
        db.execute("UPDATE candidates SET election_id=?", (election['id'],))
        db.commit()
        candidates = db.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY position", (election['id'],)).fetchall()

    if request.method == 'POST':
        selections = {}
        positions = set(c['position'] for c in candidates)
        for pos in positions:
            cid = request.form.get(f"vote_{pos.replace(' ','_')}")
            if cid:
                selections[pos] = int(cid)

        if not selections:
            flash('Please select at least one candidate.', 'error')
            db.close()
            return render_template('vote.html', candidates=candidates, election=election)

        encrypted = cipher.encrypt(json.dumps(selections).encode()).decode()
        db.execute("INSERT INTO votes (election_id, encrypted_vote) VALUES (?, ?)", (election['id'], encrypted))
        for pos, cid in selections.items():
            db.execute("UPDATE candidates SET votes = votes + 1 WHERE id=?", (cid,))
        db.execute("UPDATE voters SET has_voted=1 WHERE id=?", (session['voter_id'],))
        db.execute("INSERT INTO voter_participation (voter_id, election_id) VALUES (?, ?)", (session['voter_id'], election['id']))
        db.commit()
        db.close()
        flash('✅ Your vote has been encrypted and recorded securely!', 'success')
        return redirect(url_for('confirmation'))

    db.close()
    return render_template('vote.html', candidates=candidates, election=election)

@app.route('/confirmation')
@login_required
def confirmation():
    return render_template('confirmation.html')

@app.route('/results')
def results():
    db = get_db()
    election = db.execute("SELECT * FROM elections WHERE is_active=1 AND is_published=1 ORDER BY id DESC").fetchone()
    if not election:
        election = db.execute("SELECT * FROM elections ORDER BY id DESC").fetchone()
    candidates = []
    total_votes = 0
    total_voters = db.execute("SELECT COUNT(*) as c FROM voters").fetchone()['c']
    if election:
        candidates = db.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY position, votes DESC", (election['id'],)).fetchall()
        if not candidates:
            candidates = db.execute("SELECT * FROM candidates ORDER BY position, votes DESC").fetchall()
        total_votes = db.execute("SELECT COUNT(*) as c FROM votes WHERE election_id=?", (election['id'],)).fetchone()['c']
    db.close()
    return render_template('results.html', candidates=candidates, election=election,
                           total_votes=total_votes, total_voters=total_voters)

@app.route('/api/results')
def api_results():
    db = get_db()
    election = db.execute("SELECT * FROM elections WHERE is_published=1 ORDER BY id DESC").fetchone()
    if election:
        candidates = db.execute("SELECT name, position, department, votes FROM candidates WHERE election_id=? ORDER BY position, votes DESC", (election['id'],)).fetchall()
        total = db.execute("SELECT COUNT(*) as c FROM votes WHERE election_id=?", (election['id'],)).fetchone()['c']
    else:
        candidates = db.execute("SELECT name, position, department, votes FROM candidates ORDER BY position, votes DESC").fetchall()
        total = db.execute("SELECT COUNT(*) as c FROM votes").fetchone()['c']
    db.close()
    return jsonify({'candidates': [dict(c) for c in candidates], 'total_votes': total})

# ── Admin Routes ──────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username=?", (request.form['username'],)).fetchone()
        db.close()
        if admin and check_password_hash(admin['password_hash'], request.form['password']):
            session['admin_id'] = admin['id']
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials ❌.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    elections = db.execute("SELECT * FROM elections ORDER BY created_at DESC").fetchall()
    voters = db.execute("SELECT * FROM voters ORDER BY registered_at DESC").fetchall()
    active_election = db.execute("SELECT * FROM elections WHERE is_active=1").fetchone()
    
    total_voters = len(voters)
    voters_list = []
    
    if active_election:
        total_votes = db.execute("SELECT COUNT(*) as c FROM votes WHERE election_id=?", (active_election['id'],)).fetchone()['c']
        voted_count = db.execute("SELECT COUNT(DISTINCT voter_id) as c FROM voter_participation WHERE election_id=?", (active_election['id'],)).fetchone()['c']
        active_voters_res = db.execute("SELECT voter_id FROM voter_participation WHERE election_id=?", (active_election['id'],)).fetchall()
        active_voted_set = set([r['voter_id'] for r in active_voters_res])
        for v in voters:
            v_dict = dict(v)
            v_dict['current_has_voted'] = 1 if v['id'] in active_voted_set else 0
            voters_list.append(v_dict)
    else:
        total_votes = db.execute("SELECT COUNT(*) as c FROM votes").fetchone()['c']
        voted_count = db.execute("SELECT COUNT(*) as c FROM voters WHERE has_voted=1").fetchone()['c']
        for v in voters:
            v_dict = dict(v)
            v_dict['current_has_voted'] = v['has_voted']
            voters_list.append(v_dict)
            
    candidates = db.execute("SELECT * FROM candidates ORDER BY election_id, position, votes DESC").fetchall()
    db.close()
    turnout = round((voted_count / total_voters * 100), 1) if total_voters > 0 else 0
    return render_template('admin_dashboard.html',
                           elections=elections, voters=voters_list, candidates=candidates,
                           total_votes=total_votes, total_voters=total_voters,
                           voted_count=voted_count, turnout=turnout,
                           active_election=active_election)

# ── Election CRUD ─────────────────────────────────────────────────────────────
@app.route('/admin/election/create', methods=['POST'])
@admin_required
def create_election():
    db = get_db()
    db.execute("""INSERT INTO elections (title, description, start_time, end_time, is_active, is_published, results_declared)
                  VALUES (?,?,?,?,0,0,0)""",
               (request.form['title'], request.form['description'],
                request.form['start_time'], request.form['end_time']))
    db.commit()
    db.close()
    flash('Election created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/edit/<int:eid>', methods=['POST'])
@admin_required
def edit_election(eid):
    db = get_db()
    db.execute("""UPDATE elections SET title=?, description=?, start_time=?, end_time=? WHERE id=?""",
               (request.form['title'], request.form['description'],
                request.form['start_time'], request.form['end_time'], eid))
    db.commit()
    db.close()
    flash('Election updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/delete/<int:eid>', methods=['POST'])
@admin_required
def delete_election(eid):
    db = get_db()
    db.execute("DELETE FROM elections WHERE id=?", (eid,))
    db.execute("DELETE FROM candidates WHERE election_id=?", (eid,))
    db.commit()
    db.close()
    flash('Election deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/publish/<int:eid>', methods=['POST'])
@admin_required
def publish_election(eid):
    db = get_db()
    db.execute("UPDATE elections SET is_published=1, is_active=1 WHERE id=?", (eid,))
    db.commit()
    db.close()
    flash('Election published and activated!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/unpublish/<int:eid>', methods=['POST'])
@admin_required
def unpublish_election(eid):
    db = get_db()
    db.execute("UPDATE elections SET is_published=0, is_active=0 WHERE id=?", (eid,))
    db.commit()
    db.close()
    flash('Election unpublished.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/declare/<int:eid>', methods=['POST'])
@admin_required
def declare_results(eid):
    db = get_db()
    db.execute("UPDATE elections SET results_declared=1, is_active=0 WHERE id=?", (eid,))
    db.commit()
    db.close()
    flash('Results declared! Voters can now see the results.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/undeclare/<int:eid>', methods=['POST'])
@admin_required
def undeclare_results(eid):
    db = get_db()
    db.execute("UPDATE elections SET results_declared=0 WHERE id=?", (eid,))
    db.commit()
    db.close()
    flash('Results hidden from public.', 'success')
    return redirect(url_for('admin_dashboard'))

# ── Candidate CRUD ────────────────────────────────────────────────────────────
@app.route('/admin/candidate/add', methods=['POST'])
@admin_required
def add_candidate():
    db = get_db()
    db.execute("INSERT INTO candidates (election_id, name, department, position, manifesto) VALUES (?,?,?,?,?)",
               (request.form['election_id'], request.form['name'],
                request.form['department'], request.form['position'], request.form['manifesto']))
    db.commit()
    db.close()
    flash(f"Candidate '{request.form['name']}' added successfully!", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/candidate/delete/<int:cid>', methods=['POST'])
@admin_required
def delete_candidate(cid):
    db = get_db()
    db.execute("DELETE FROM candidates WHERE id=?", (cid,))
    db.commit()
    db.close()
    flash('Candidate removed.', 'success')
    return redirect(url_for('admin_dashboard'))

# ── Voter Management ──────────────────────────────────────────────────────────
@app.route('/admin/verify_voter/<int:voter_id>', methods=['POST'])
@admin_required
def verify_voter(voter_id):
    db = get_db()
    db.execute("UPDATE voters SET is_verified=1 WHERE id=?", (voter_id,))
    db.commit()
    db.close()
    flash('Voter verified successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_voter/<int:voter_id>', methods=['POST'])
@admin_required
def delete_voter(voter_id):
    db = get_db()
    db.execute("DELETE FROM voters WHERE id=?", (voter_id,))
    db.commit()
    db.close()
    flash('Voter removed.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
