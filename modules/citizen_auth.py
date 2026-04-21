from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
import mysql.connector
from auth import db_config
from blockchain_config import land_chain
import datetime, re, ssl, os
import easyocr
import numpy as np
import cv2

# ─── SSL FIX ─────────────────────────────────────────────────
if (not os.environ.get('PYTHONHTTPSVERIFY', '') and
    getattr(ssl, '_create_unverified_context', None)):
    ssl._create_default_https_context = ssl._create_unverified_context

citizen_bp = Blueprint('citizen', __name__, url_prefix='/citizen')

_reader = None
def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'])
    return _reader

def get_db():
    return mysql.connector.connect(**db_config)

def get_common_context(user_name):
    """Returns (notif_count, is_verified, aadhaar_suffix)."""
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM notifications WHERE recipient=%s AND is_read=0",
            (user_name,)
        )
        row = cursor.fetchone()
        notif_count = row['cnt'] if row else 0
        cursor.execute(
            "SELECT aadhaar_verified, aadhaar_number FROM users WHERE username=%s",
            (user_name,)
        )
        info = cursor.fetchone()
        conn.close()
        is_verified = bool(info['aadhaar_verified']) if info else False
        suffix = None
        if info and info.get('aadhaar_number'):
            s = str(info['aadhaar_number'])
            suffix = s[-4:] if len(s) >= 4 else s
        return notif_count, is_verified, suffix
    except Exception as e:
        print(f"[Context Error] {e}")
        return 0, False, None

def extract_aadhaar_from_image(image_bytes):
    try:
        nparr  = np.frombuffer(image_bytes, np.uint8)
        img    = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray   = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        results = get_reader().readtext(thresh)
        lines   = [r[1].strip() for r in results]
        full    = " ".join(lines).upper()
        data    = {"number": None, "name": "", "dob": "", "gender": "Select"}
        raw = re.sub(r'[^0-9]', '', full.replace('I','1').replace('O','0'))
        m = re.search(r'\d{12}', raw)
        if m: data["number"] = m.group()
        if "FEMALE" in full: data["gender"] = "Female"
        elif "MALE" in full: data["gender"] = "Male"
        dm = re.search(r'(\d{2}/\d{2}/\d{4})', full)
        if dm: data["dob"] = dm.group()
        blacklist = ["PHOTO","DOB","DATE","GENDER","AADHAAR","GOVT","INDIA"]
        for i, line in enumerate(lines):
            if any(t in line.upper() for t in ["NAME","नाम"]):
                for offset in [1, 2]:
                    if i + offset < len(lines):
                        cand = lines[i+offset].strip()
                        if not any(b in cand.upper() for b in blacklist) and len(cand) > 2:
                            data["name"] = re.sub(r'[^a-zA-Z\s]', '', cand).strip()
                            break
                if data["name"]: break
        return (data, 'OCR_SUCCESS') if data["number"] else (None, "Aadhaar number not detected.")
    except Exception as e:
        return None, f"OCR Error: {str(e)}"

# ─── DASHBOARD ───────────────────────────────────────────────

@citizen_bp.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session['user'],))
    user_data = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) AS cnt FROM land_records WHERE owner_name=%s", (session['user'],))
    p_count = cursor.fetchone()['cnt']
    conn.close()
    chain = land_chain.chain
    latest_hash = chain[-1].get('hash', 'N/A') if chain else 'N/A'
    stats = {
        'shards': 4, 'blocks': len(chain), 'properties': p_count,
        'transactions': 0, 'uptime': '99.9%',
        'status': 'ONLINE', 'height': len(chain),
        'hash': latest_hash[:48] if latest_hash != 'N/A' else '0000000000000000',
    }
    global_activity = [
        {'index': b.get('index', i+1),
         'hash': b.get('hash', '')[:48] + '...',
         'timestamp': b.get('timestamp', '—')}
        for i, b in enumerate(reversed(chain))
    ]
    return render_template('citizen_overview.html',
                           user=session['user'], user_data=user_data, stats=stats,
                           my_property_count=p_count, global_activity=global_activity,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── AADHAAR UPLOAD ──────────────────────────────────────────

@citizen_bp.route('/aadhaar_upload', methods=['GET', 'POST'])
def aadhaar_upload():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])

    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session['user'],))
    user_data = cursor.fetchone()

    if request.method == 'POST':
        file = request.files.get('aadhaar_doc')

        if file and file.filename:
            # OCR path
            data, msg = extract_aadhaar_from_image(file.read())
            if data:
                cursor.execute(
                    """UPDATE users SET aadhaar_number=%s, full_name=%s, dob=%s, gender=%s,
                       aadhaar_verified=1 WHERE username=%s""",
                    (data['number'], data['name'], data['dob'], data['gender'], session['user']))
                conn.commit(); conn.close()
                flash("Aadhaar Verified via OCR!", "success")
                return redirect(url_for('citizen.aadhaar_profile'))
            conn.close()
            flash(msg, "danger")
        else:
            # Manual entry path
            aadhaar_number = request.form.get('aadhaar_number', '').strip()
            full_name      = request.form.get('full_name', '').strip()
            dob            = request.form.get('dob', '').strip()
            gender         = request.form.get('gender', '').strip()
            address        = request.form.get('address', '').strip()

            if not re.match(r'^\d{12}$', aadhaar_number):
                conn.close()
                flash("Aadhaar number must be exactly 12 digits.", "danger")
            else:
                cursor.execute(
                    """UPDATE users SET aadhaar_number=%s, full_name=%s, dob=%s, gender=%s,
                       aadhaar_address=%s, aadhaar_verified=1 WHERE username=%s""",
                    (aadhaar_number, full_name, dob, gender, address, session['user']))
                conn.commit(); conn.close()
                flash("Aadhaar Profile Saved & Verified!", "success")
                return redirect(url_for('citizen.aadhaar_profile'))

    else:
        conn.close()

    n_count, is_verified, suffix = get_common_context(session['user'])
    return render_template('citizen_aadhaar_upload.html',
                           user=session['user'], user_data=user_data,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── AADHAAR PROFILE ─────────────────────────────────────────

@citizen_bp.route('/aadhaar_profile', methods=['GET', 'POST'])
def aadhaar_profile():
    if 'user' not in session: return redirect(url_for('citizen.login'))

    if request.method == 'POST':
        conn = get_db(); cursor = conn.cursor()
        cursor.execute(
            """UPDATE users SET email=%s, mobile=%s, occupation=%s,
               annual_income=%s, address=%s WHERE username=%s""",
            (request.form.get('email','').strip(),
             request.form.get('mobile','').strip(),
             request.form.get('occupation','').strip(),
             request.form.get('annual_income','').strip() or None,
             request.form.get('address','').strip(),
             session['user']))
        conn.commit(); conn.close()
        flash("Profile Updated Successfully!", "success")
        return redirect(url_for('citizen.aadhaar_profile'))

    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session['user'],))
    user_data = cursor.fetchone(); conn.close()

    n_count, is_verified, suffix = get_common_context(session['user'])
    return render_template('citizen_aadhaar_profile.html',
                           user_data=user_data, user=session['user'],
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── PROPERTIES ──────────────────────────────────────────────

@citizen_bp.route('/my_properties')
def my_properties():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM land_records WHERE owner_name=%s", (session['user'],))
    assets = cursor.fetchall(); conn.close()
    return render_template('citizen_properties.html',
                           assets=assets, user=session['user'],
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

@citizen_bp.route('/market_listings')
def market_listings():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM land_records")
    listings = cursor.fetchall(); conn.close()
    return render_template('citizen_market.html',
                           all_properties=listings, user=session['user'],
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── TRANSFER HISTORY ────────────────────────────────────────

@citizen_bp.route('/transfer_history')
def transfer_history():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    conn = get_db(); cursor = conn.cursor(dictionary=True)

    # Detect which column to order by — avoids the created_at crash
    cursor.execute("SHOW COLUMNS FROM transfer_requests")
    col_names = {row['Field'] for row in cursor.fetchall()}
    order_col = next((c for c in ('created_at','timestamp','request_date','id')
                      if c in col_names), None)

    sql = "SELECT * FROM transfer_requests WHERE sender=%s OR receiver=%s"
    if order_col:
        sql += f" ORDER BY {order_col} DESC"
    cursor.execute(sql, (session['user'], session['user']))
    history = cursor.fetchall(); conn.close()

    approved_count = sum(1 for t in history if t.get('status') == 'Approved')
    rejected_count = sum(1 for t in history if t.get('status') == 'Rejected')
    pending_count  = sum(1 for t in history if t.get('status') not in ('Approved', 'Rejected'))
    return render_template('citizen_transfer_history.html',
                           all_transfers=history, user=session['user'],
                           approved_count=approved_count, rejected_count=rejected_count,
                           pending_count=pending_count,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── AUDIT TRAIL ─────────────────────────────────────────────

@citizen_bp.route('/audit_trail')
def audit_trail():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    chain = land_chain.chain
    try:
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT SUM(area_sqft) AS total FROM land_records")
        row = cursor.fetchone(); conn.close()
        total_sqft = float(row['total'] or 0)
        verified_acres = round(total_sqft / 43560, 2)
    except Exception:
        verified_acres = 0.0
    telemetry = {'verified_acres': verified_acres, 'active_shards': len(chain)}
    return render_template('citizen_audit.html',
                           user=session['user'], chain=chain, telemetry=telemetry,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── DISPUTE ─────────────────────────────────────────────────

@citizen_bp.route('/dispute_filing', methods=['GET', 'POST'])
def dispute_filing():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    disputes = []
    conn = get_db(); cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        survey_no = request.form.get('survey_no','').strip()
        party_b   = request.form.get('party_b','').strip()
        reason    = request.form.get('reason','').strip()
        if survey_no and party_b and reason:
            try:
                cursor.execute(
                    "INSERT INTO disputes (survey_no, party_a, party_b, reason, status) VALUES (%s,%s,%s,%s,'Pending')",
                    (survey_no, session['user'], party_b, reason))
                conn.commit()
                flash("Dispute filed successfully.", "success")
            except Exception as e:
                flash(f"Could not file dispute: {e}", "danger")
        else:
            flash("All fields are required.", "warning")

    try:
        cursor.execute("SELECT * FROM disputes WHERE party_a=%s", (session['user'],))
        disputes = cursor.fetchall()
    except Exception:
        disputes = []
    conn.close()

    return render_template('citizen_dispute.html',
                           user=session['user'], disputes=disputes,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── TAXATION ────────────────────────────────────────────────

@citizen_bp.route('/taxation')
def taxation():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM land_records WHERE owner_name=%s", (session['user'],))
    assets = cursor.fetchall(); conn.close()
    return render_template('citizen_taxation.html',
                           user=session['user'], assets=assets,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)

# ─── AUTH ────────────────────────────────────────────────────

@citizen_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session: return redirect(url_for('citizen.dashboard'))
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','').strip()
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
        user = cursor.fetchone(); conn.close()
        if user:
            session.update({'user': u, 'role': 'citizen'})
            return redirect(url_for('citizen.dashboard'))
        flash("Invalid username or password.", "danger")
    return render_template('citizen_login.html')

@citizen_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','').strip()
        if not u or not p:
            flash("Username and password are required.", "warning")
            return render_template('citizen_signup.html')
        try:
            conn = get_db(); cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, role, aadhaar_verified) VALUES (%s,%s,'citizen',0)",
                (u, p))
            conn.commit(); conn.close()
            flash("Account created! Please log in.", "success")
            return redirect(url_for('citizen.login'))
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")
    return render_template('citizen_signup.html')

# ─── NOTIFICATIONS ───────────────────────────────────────────

@citizen_bp.route('/notifications')
def notifications():
    if 'user' not in session: return jsonify([])
    conn = get_db(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications WHERE recipient=%s ORDER BY id DESC", (session['user'],))
    notes = cursor.fetchall(); conn.close()
    for n in notes:
        for k, v in n.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                n[k] = str(v)
    return jsonify(notes)

@citizen_bp.route('/notifications/mark_read', methods=['POST'])
def mark_notifications_read():
    if 'user' not in session: return jsonify({'status': 'error'})
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read=1 WHERE recipient=%s", (session['user'],))
    conn.commit(); conn.close()
    return jsonify({'status': 'ok'})
# ─── REGISTER PROPERTY ───────────────────────────────────────────────────────

@citizen_bp.route('/register_property', methods=['POST'])
def register_property():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'})
    location  = request.form.get('location', '').strip()
    survey_no = request.form.get('survey_no', '').strip()
    area      = request.form.get('area', '').strip()
    category  = request.form.get('category', 'Residential').strip()
    zoning    = request.form.get('zoning', '').strip()
    if not location or not survey_no or not area:
        return jsonify({'status': 'error', 'message': 'All fields are required.'})
    try:
        area_f = float(area)
        if area_f <= 0:
            return jsonify({'status': 'error', 'message': 'Area must be positive.'})
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid area value.'})
    try:
        import hashlib, json as _json, time as _time
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM land_records WHERE survey_no=%s", (survey_no,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Survey number already registered.'})
        prop_hash = hashlib.sha256(
            f"{survey_no}{location}{session['user']}{_time.time()}".encode()
        ).hexdigest()
        cursor.execute(
            """INSERT INTO land_records (owner_name, location_name, survey_no, area_sqft,
               land_category, zoning_code, property_hash)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (session['user'], location, survey_no, area_f, category, zoning, prop_hash)
        )
        conn.commit()
        land_id = cursor.lastrowid
        # Add to blockchain
        land_chain.add_block({
            'land_id': land_id, 'owner': session['user'],
            'survey': survey_no, 'location': location,
            'area_sqft': area_f, 'category': category
        })
        conn.close()
        return jsonify({'status': 'success', 'message': f'Property registered. Ledger ID: #{land_id}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ─── FILE DISPUTE (JSON endpoint) ────────────────────────────────────────────

@citizen_bp.route('/file_dispute', methods=['POST'])
def file_dispute():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'})
    survey_no = request.form.get('survey_no', '').strip()
    party_b   = request.form.get('party_b', '').strip()
    reason    = request.form.get('reason', '').strip()
    if not survey_no or not party_b or not reason:
        return jsonify({'status': 'error', 'message': 'All fields are required.'})
    try:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO disputes (survey_no, party_a, party_b, reason, status) VALUES (%s,%s,%s,%s,'Pending')",
            (survey_no, session['user'], party_b, reason)
        )
        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': 'Dispute filed successfully. Case assigned for tribunal review.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ─── FORENSIC VERIFY ─────────────────────────────────────────────────────────

@citizen_bp.route('/forensic_verify')
def forensic_verify():
    if 'user' not in session: return redirect(url_for('citizen.login'))
    n_count, is_verified, suffix = get_common_context(session['user'])
    query  = request.args.get('query', '').strip()
    chain  = land_chain.chain
    status = 'NOT_FOUND'
    result = {}
    if query:
        for block in chain:
            txs = block.get('transactions', [])
            block_hash = block.get('hash', '')
            for tx in txs:
                survey = str(tx.get('survey', tx.get('survey_no', tx.get('land_id', ''))))
                if query.lower() in survey.lower() or query.lower() in block_hash.lower():
                    status = 'VALIDATED'
                    result = block
                    break
            if status == 'VALIDATED':
                break
    try:
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT SUM(area_sqft) AS total FROM land_records")
        row = cursor.fetchone(); conn.close()
        total_sqft = float(row['total'] or 0)
        verified_acres = round(total_sqft / 43560, 2)
    except Exception:
        verified_acres = 0.0
    telemetry = {'verified_acres': verified_acres, 'active_shards': len(chain)}
    return render_template('citizen_forensic.html',
                           user=session['user'], chain=chain,
                           query=query, status=status, result=result,
                           telemetry=telemetry,
                           notif_count=n_count, aadhaar_verified=is_verified, aadhaar_suffix=suffix)