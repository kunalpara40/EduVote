"""
Run this script ONCE to fix your database.
It will upgrade the old database to the new schema.

Usage:
    python fix_db.py
"""
import sqlite3
from werkzeug.security import generate_password_hash

db = sqlite3.connect('evoting.db')
db.row_factory = sqlite3.Row

print("🔧 Fixing database schema...")

# Add missing columns to elections table if they don't exist
try:
    db.execute("ALTER TABLE elections ADD COLUMN description TEXT")
    print("  ✅ Added 'description' column to elections")
except: print("  ℹ️  'description' already exists")

try:
    db.execute("ALTER TABLE voters ADD COLUMN face_encoding TEXT")
    print("  ✅ Added 'face_encoding' column to voters")
except: print("  ℹ️  'face_encoding' already exists column")

try:
    db.execute("ALTER TABLE elections ADD COLUMN is_published INTEGER DEFAULT 1")
    print("  ✅ Added 'is_published' column to elections")
except: print("  ℹ️  'is_published' already exists")

try:
    db.execute("ALTER TABLE elections ADD COLUMN results_declared INTEGER DEFAULT 0")
    print("  ✅ Added 'results_declared' column to elections")
except: print("  ℹ️  'results_declared' already exists")

try:
    db.execute("ALTER TABLE elections ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    print("  ✅ Added 'created_at' column to elections")
except: print("  ℹ️  'created_at' already exists")

# Add election_id to candidates if missing
try:
    db.execute("ALTER TABLE candidates ADD COLUMN election_id INTEGER DEFAULT 1")
    print("  ✅ Added 'election_id' column to candidates")
except: print("  ℹ️  'election_id' already exists")

# Mark all existing elections as published
db.execute("UPDATE elections SET is_published=1 WHERE is_published IS NULL OR is_published=0")
print("  ✅ Marked all elections as published")

# Assign all candidates to election id=1 if unassigned
db.execute("UPDATE candidates SET election_id=1 WHERE election_id IS NULL OR election_id=0")
print("  ✅ Assigned all candidates to election #1")

# Fix elections table - rename old 'position' column issue
# Check if 'position' column exists in elections (old schema)
cols = [row[1] for row in db.execute("PRAGMA table_info(elections)").fetchall()]
print(f"  ℹ️  Elections columns: {cols}")

try:
    db.execute("ALTER TABLE votes ADD COLUMN election_id INTEGER DEFAULT 1")
    print("  ✅ Added 'election_id' column to votes")
except: print("  ℹ️  'election_id' already exists in votes")

db.execute("""
    CREATE TABLE IF NOT EXISTS voter_participation (
        voter_id INTEGER NOT NULL,
        election_id INTEGER NOT NULL,
        voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (voter_id, election_id)
    );
""")
print("  ✅ Ensured 'voter_participation' table exists")

# Populate voter_participation based on existing has_voted for election 1
db.execute("""
    INSERT OR IGNORE INTO voter_participation (voter_id, election_id)
    SELECT id, 1 FROM voters WHERE has_voted=1
""")
print("  ✅ Migrated existing has_voted data to voter_participation")

db.commit()
db.close()

print("\n🎉 Database fixed successfully!")
print("   Now restart your Flask app: python app.py")
