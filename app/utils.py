from flask import g, flash, redirect, url_for, session
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if hasattr(g, 'voter_id'):
            return f(*args, **kwargs)
        flash('Please login first.', 'error')
        return redirect(url_for('voter.login'))
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated

def format_doc(doc):
    if doc:
        doc['id'] = str(doc['_id'])
    return doc
