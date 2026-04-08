# 🗳 EduVote — Secure Campus E-Voting System

A full-stack E-Voting web application built with **Python Flask**, featuring SSL/TLS encryption, AES-128 vote encryption, and real-time results.

---

## 🔐 Computer Network Concepts Applied

| Concept | Implementation |
|---|---|
| **SSL/TLS (HTTPS)** | `ssl_context='adhoc'` in Flask — all traffic encrypted in transit |
| **End-to-End Encryption** | Votes encrypted with **Fernet (AES-128-CBC + HMAC-SHA256)** before DB storage |
| **Password Hashing** | PBKDF2-HMAC via Werkzeug — protects voter credentials |
| **Client-Server Model** | Browser (client) ↔ Flask server ↔ SQLite DB |
| **Session Management** | Secure server-side sessions with secret key |
| **API Endpoint** | `/api/results` — JSON REST endpoint for real-time data |
| **Authentication** | Student ID + password login with verified voter check |
| **Access Control** | Route decorators prevent unauthorized access |

---

## 📁 Project Structure

```
evoting/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── evoting.db              # SQLite database (auto-created)
└── templates/
    ├── base.html           # Base layout with nav
    ├── index.html          # Landing page
    ├── register.html       # Voter registration
    ├── login.html          # Voter login
    ├── dashboard.html      # Voter dashboard
    ├── vote.html           # Vote casting page
    ├── confirmation.html   # Post-vote confirmation
    ├── results.html        # Real-time results
    ├── admin_login.html    # Admin login
    └── admin_dashboard.html # Admin panel
```

---

## 🚀 Setup & Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the App
```bash
python app.py
```

### 3. Access
- **Voter Portal:** https://localhost:5000
- **Admin Panel:** https://localhost:5000/admin/login
  - Username: `admin` | Password: `admin123`

> ⚠️ Browser will warn about self-signed SSL certificate — click "Advanced → Proceed" (this is expected in development)

---

## 👤 Default Test Data

The app auto-seeds:
- **6 candidates** across 3 positions (President, Vice President, Secretary)
- **1 active election** (Student Council Election 2025)
- **1 admin account**

---

## 🔑 Key Security Features

1. **SSL/TLS** — `app.run(ssl_context='adhoc')` enables HTTPS
2. **Vote Encryption** — `cryptography.Fernet` encrypts each vote before storage
3. **One Vote Per Voter** — DB flag prevents double voting
4. **Admin Verification** — Voters need admin approval before voting
5. **Password Hashing** — PBKDF2 via Werkzeug (not plaintext storage)
6. **Session Security** — `os.urandom(24)` secret key per server start
