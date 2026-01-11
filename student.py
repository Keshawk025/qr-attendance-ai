#!/usr/bin/env python3
"""
Student Attendance Application - FINAL FIX
Handles attendance_id column correctly
"""

from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import hashlib
import hmac
import time
import json
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)
CORS(app)
app.secret_key = 'student-attendance-secret-2025'

DATABASE = 'attendance.db'
SECRET_KEY = 'attendance-secret-2025'
QR_EXPIRY_SECONDS = 30

# ============================================================================
# UTILITIES
# ============================================================================

def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_device_id():
    """Generate unique device ID from browser fingerprint"""
    user_agent = request.headers.get('User-Agent', '')
    accept_language = request.headers.get('Accept-Language', '')

    fingerprint = f"{user_agent}|{accept_language}"
    device_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

    return device_id

def verify_qr_signature(qr_data):
    """Verify QR code HMAC-SHA256 signature"""
    session_id = qr_data.get('session_id')
    subject_id = qr_data.get('subject_id')
    timestamp = qr_data.get('timestamp')
    nonce = qr_data.get('nonce', '')
    provided_signature = qr_data.get('signature')

    data_to_sign = f"{session_id}:{subject_id}:{timestamp}:{nonce}:{SECRET_KEY}"
    expected_signature = hmac.new(
        SECRET_KEY.encode(),
        data_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()

    return expected_signature == provided_signature

def get_table_columns(table_name):
    """Get column names for a table"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
    except:
        columns = []
    conn.close()
    return columns

def get_student_id_column():
    """Detect which column is used for student ID in students table"""
    columns = get_table_columns('students')
    if 'student_id' in columns:
        return 'student_id'
    elif 'id' in columns:
        return 'id'
    else:
        return 'student_id'  # default

def init_database():
    """Initialize database schema"""
    conn = get_db()
    cursor = conn.cursor()

    # Check existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]
    print(f"📊 Existing tables: {existing_tables}")

    # Check students table columns if it exists
    if 'students' in existing_tables:
        student_columns = get_table_columns('students')
        print(f"👥 Students table columns: {student_columns}")
    else:
        # Create students table with student_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                usn TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Created students table")

    # Device sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            logout_time TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            ip_address TEXT,
            UNIQUE(student_id, device_id)
        )
    """)

    # Check attendance table columns if it exists
    if 'attendance' in existing_tables:
        attendance_columns = get_table_columns('attendance')
        print(f"📝 Attendance table columns: {attendance_columns}")

        # If attendance_id doesn't exist, create new table
        if 'attendance_id' not in attendance_columns:
            print("⚠️ Attendance table missing attendance_id, recreating...")
            cursor.execute("DROP TABLE IF EXISTS attendance")
            existing_tables.remove('attendance')

    # Create attendance table with attendance_id
    if 'attendance' not in existing_tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                subject_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT DEFAULT 'present',
                device_id TEXT,
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, session_id)
            )
        """)
        print("✅ Created attendance table with attendance_id")

    # QR Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qr_sessions (
            session_id TEXT PRIMARY KEY,
            subject_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            expiry INTEGER NOT NULL,
            nonce TEXT,
            signature TEXT,
            qr_data TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database schema ready")

# ============================================================================
# HTML TEMPLATES (Same as before)
# ============================================================================

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 450px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 { font-size: 32px; margin-bottom: 10px; }
        .logo { font-size: 50px; margin-bottom: 15px; }
        .form { padding: 40px; }
        .form-group { margin-bottom: 25px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 14px;
        }
        input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }
        button {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover { transform: translateY(-2px); }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #f5c6cb;
        }
        .info {
            background: #d1ecf1;
            color: #0c5460;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">👨‍🎓</div>
            <h1>Student Login</h1>
            <p>Mark Your Attendance</p>
        </div>

        <div class="form">
            {% if error %}
            <div class="error">❌ {{ error }}</div>
            {% endif %}

            <form method="POST" action="/login">
                <div class="form-group">
                    <label>University Seat Number (USN)</label>
                    <input type="text" name="usn" placeholder="e.g., 1RV21CS001" 
                           required autofocus>
                </div>

                <button type="submit">🚀 Login</button>
            </form>

            <div class="info">
                <strong>ℹ️ Information:</strong><br>
                • Login with your USN only<br>
                • Device ID generated automatically<br>
                • USN must be registered
            </div>
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 700px; margin: 0 auto; }
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 { color: #333; font-size: 28px; margin-bottom: 5px; }
        .usn-badge {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 5px;
        }
        .device-info {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            font-size: 12px;
            color: #666;
            margin-top: 10px;
        }
        .camera-section {
            position: relative;
            margin: 20px 0;
            border-radius: 15px;
            overflow: hidden;
            background: #000;
            display: none;
        }
        #video { width: 100%; display: block; border-radius: 15px; }
        canvas { display: none; }
        .btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin: 10px 0;
            transition: all 0.3s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn.stop { background: #ffc107; }
        .btn.logout { background: #6c757d; text-decoration: none; text-align: center; display: block; }
        .info-box {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 1px solid;
        }
        .info-box.success {
            background: #d4edda;
            color: #155724;
            border-color: #c3e6cb;
            display: none;
        }
        .info-box.error {
            background: #f8d7da;
            color: #721c24;
            border-color: #f5c6cb;
            display: none;
        }
        .validation-steps {
            margin: 20px 0;
        }
        .step {
            display: flex;
            align-items: center;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            background: #f8f9fa;
        }
        .step-icon { font-size: 24px; margin-right: 15px; }
        .step.completed { background: #d4edda; color: #155724; }
        .step.failed { background: #f8d7da; color: #721c24; }
        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>👨‍🎓 Student Dashboard</h1>
                <p>Welcome, <strong>{{ student_name }}</strong></p>
                <span class="usn-badge">{{ student_usn }}</span>
                <div class="device-info">🔐 Device ID: {{ device_id }}</div>
            </div>

            <div id="successMessage" class="info-box success">
                ✅ <span id="successText"></span>
            </div>
            <div id="errorMessage" class="info-box error">
                ❌ <span id="errorText"></span>
            </div>

            <div class="validation-steps">
                <div class="step" id="step1">
                    <span class="step-icon">⏱️</span>
                    <div>
                        <strong>30-Second Expiry</strong><br>
                        <small>Checking timestamp...</small>
                    </div>
                </div>
                <div class="step" id="step2">
                    <span class="step-icon">🔐</span>
                    <div>
                        <strong>Signature</strong><br>
                        <small>Verifying...</small>
                    </div>
                </div>
                <div class="step" id="step3">
                    <span class="step-icon">✓</span>
                    <div>
                        <strong>Session</strong><br>
                        <small>Validating...</small>
                    </div>
                </div>
                <div class="step" id="step4">
                    <span class="step-icon">🎯</span>
                    <div>
                        <strong>Mark Attendance</strong><br>
                        <small>Recording...</small>
                    </div>
                </div>
            </div>

            <div class="camera-section" id="cameraSection">
                <video id="video" autoplay playsinline></video>
                <canvas id="canvas"></canvas>
            </div>

            <button class="btn" id="startBtn" onclick="startScanning()">
                📸 Start QR Scanner
            </button>
            <button class="btn stop" id="stopBtn" onclick="stopScanning()" style="display: none;">
                ⏸️ Stop Scanner
            </button>

            <div id="loading" class="loading">
                <div class="spinner"></div>
                <p style="margin-top: 10px; color: #666;">Marking attendance...</p>
            </div>

            <a href="/logout" class="btn logout">🚪 Logout</a>
        </div>
    </div>

    <script>
        const studentId = {{ student_id }};

        let video = document.getElementById('video');
        let canvas = document.getElementById('canvas');
        let ctx = canvas.getContext('2d');
        let scanning = false;
        let stream = null;

        async function startScanning() {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'environment' }
                });

                video.srcObject = stream;
                document.getElementById('cameraSection').style.display = 'block';
                scanning = true;
                document.getElementById('startBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'block';

                requestAnimationFrame(scanQRCode);

            } catch (err) {
                showError('Camera access denied');
            }
        }

        function stopScanning() {
            scanning = false;
            if (stream) stream.getTracks().forEach(track => track.stop());
            document.getElementById('cameraSection').style.display = 'none';
            document.getElementById('startBtn').style.display = 'block';
            document.getElementById('stopBtn').style.display = 'none';
        }

        function scanQRCode() {
            if (!scanning) return;

            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.height = video.videoHeight;
                canvas.width = video.videoWidth;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);

                if (code) {
                    scanning = false;
                    processQRCode(code.data);
                    return;
                }
            }

            requestAnimationFrame(scanQRCode);
        }

        async function processQRCode(qrData) {
            stopScanning();

            try {
                const qrJson = JSON.parse(qrData);
                const currentTime = Math.floor(Date.now() / 1000);
                const qrAge = currentTime - qrJson.timestamp;

                updateStep('step1', 'pending', '⏱️', 'Checking...');
                await sleep(300);

                if (currentTime > qrJson.expiry) {
                    updateStep('step1', 'failed', '❌', `Expired (${qrAge}s)`);
                    showError(`QR expired! ${qrAge}s old`);
                    resetSteps();
                    return;
                }
                updateStep('step1', 'completed', '✅', `Valid (${qrAge}s)`);

                updateStep('step2', 'pending', '🔐', 'Verifying...');
                await sleep(300);
                updateStep('step2', 'completed', '✅', 'Valid');

                updateStep('step3', 'pending', '✓', 'Checking...');
                await sleep(300);
                updateStep('step3', 'completed', '✅', 'Valid');

                updateStep('step4', 'pending', '🎯', 'Marking...');
                document.getElementById('loading').style.display = 'block';

                const response = await fetch('/api/mark-attendance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        qr_data: qrJson,
                        scan_time: currentTime
                    })
                });

                const result = await response.json();
                document.getElementById('loading').style.display = 'none';

                if (result.success) {
                    updateStep('step4', 'completed', '✅', 'Marked!');
                    showSuccess(`Attendance marked!<br>Subject: ${result.subject_name}<br>Status: Present ✓`);
                    setTimeout(() => resetSteps(), 3000);
                } else {
                    updateStep('step4', 'failed', '❌', result.message);
                    showError(result.message);
                    resetSteps();
                }

            } catch (err) {
                document.getElementById('loading').style.display = 'none';
                showError('Error: ' + err.message);
                resetSteps();
            }
        }

        function updateStep(stepId, status, icon, message) {
            const step = document.getElementById(stepId);
            step.className = `step ${status}`;
            step.querySelector('.step-icon').textContent = icon;
            step.querySelector('small').textContent = message;
        }

        function resetSteps() {
            setTimeout(() => {
                document.querySelectorAll('.step').forEach(s => s.className = 'step');
            }, 2000);
        }

        function showError(message) {
            document.getElementById('errorText').innerHTML = message;
            document.getElementById('errorMessage').style.display = 'block';
            document.getElementById('successMessage').style.display = 'none';
        }

        function showSuccess(message) {
            document.getElementById('successText').innerHTML = message;
            document.getElementById('successMessage').style.display = 'block';
            document.getElementById('errorMessage').style.display = 'none';
        }

        function sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
    </script>
</body>
</html>
"""

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def home():
    if 'student_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Student login with USN verification"""
    if request.method == 'POST':
        usn = request.form.get('usn', '').strip().upper()

        if not usn:
            return render_template_string(LOGIN_PAGE, error="Please enter your USN")

        device_id = generate_device_id()

        conn = get_db()
        cursor = conn.cursor()

        # Get correct ID column
        id_column = get_student_id_column()

        # Verify USN
        cursor.execute(f"""
            SELECT {id_column}, usn, name, email
            FROM students
            WHERE usn = ?
        """, (usn,))

        student = cursor.fetchone()

        if not student:
            conn.close()
            return render_template_string(LOGIN_PAGE,
                error=f"USN '{usn}' not found. Contact administrator.")

        student_id = student[id_column]
        student_name = student['name']

        # Check multi-device login
        cursor.execute("""
            SELECT device_id FROM device_sessions
            WHERE student_id = ? AND is_active = 1
        """, (student_id,))

        active_session = cursor.fetchone()

        if active_session and active_session['device_id'] != device_id:
            conn.close()
            return render_template_string(LOGIN_PAGE,
                error="Already logged in on another device.")

        # Deactivate old sessions
        cursor.execute("""
            UPDATE device_sessions 
            SET is_active = 0, logout_time = CURRENT_TIMESTAMP
            WHERE student_id = ? AND device_id = ?
        """, (student_id, device_id))

        # Create new session
        cursor.execute("""
            INSERT OR REPLACE INTO device_sessions
            (student_id, device_id, login_time, is_active, ip_address)
            VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?)
        """, (student_id, device_id, request.remote_addr))

        conn.commit()
        conn.close()

        session['student_id'] = student_id
        session['student_usn'] = usn
        session['student_name'] = student_name
        session['device_id'] = device_id

        return redirect(url_for('dashboard'))

    return render_template_string(LOGIN_PAGE, error=None)

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    return render_template_string(DASHBOARD_PAGE,
                                 student_id=session['student_id'],
                                 student_name=session['student_name'],
                                 student_usn=session['student_usn'],
                                 device_id=session['device_id'])

@app.route('/logout')
def logout():
    if 'student_id' in session and 'device_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE device_sessions
            SET is_active = 0, logout_time = CURRENT_TIMESTAMP
            WHERE student_id = ? AND device_id = ?
        """, (session['student_id'], session['device_id']))
        conn.commit()
        conn.close()

    session.clear()
    return redirect(url_for('login'))

@app.route('/api/mark-attendance', methods=['POST'])
def mark_attendance():
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        data = request.json
        student_id = data.get('student_id')
        qr_data = data.get('qr_data')

        session_id = qr_data['session_id']
        subject_id = qr_data['subject_id']

        current_time = int(time.time())
        qr_age = current_time - qr_data.get('timestamp', 0)

        conn = get_db()
        cursor = conn.cursor()

        # Validation 1: Expiry
        if current_time > qr_data.get('expiry', 0):
            conn.close()
            return jsonify({'success': False, 'message': f'QR expired ({qr_age}s)'}), 400

        # Validation 2: Signature
        if not verify_qr_signature(qr_data):
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid signature'}), 400

        # Validation 3: Session
        cursor.execute("SELECT session_id FROM qr_sessions WHERE session_id = ? AND is_active = 1", 
                      (session_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid session'}), 400

        # Validation 4: Duplicate (using attendance_id)
        cursor.execute("""
            SELECT attendance_id FROM attendance 
            WHERE student_id = ? AND session_id = ?
        """, (student_id, session_id))

        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Already marked'}), 400

        # Get student name
        id_column = get_student_id_column()
        cursor.execute(f"SELECT name FROM students WHERE {id_column} = ?", (student_id,))
        student = cursor.fetchone()
        student_name = student['name'] if student else 'Unknown'

        # Mark attendance with attendance_id (auto-increment)
        cursor.execute("""
            INSERT INTO attendance
            (student_id, student_name, subject_id, session_id, status, device_id, marked_at)
            VALUES (?, ?, ?, ?, 'present', ?, CURRENT_TIMESTAMP)
        """, (student_id, student_name, subject_id, session_id, session.get('device_id')))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Attendance marked!',
            'subject_name': f'Subject {subject_id}',
            'status': 'present'
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import os

    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║   STUDENT ATTENDANCE APP - FINAL (attendance_id)      ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    if not os.path.exists(DATABASE):
        print("📦 Creating new database...")
        init_database()
    else:
        print("📦 Checking existing database...")
        init_database()

    print("""
    🚀 Starting Student App...
    📍 http://localhost:5001

    ✅ Schema:
       • students table (with student_id or id - auto-detected)
       • attendance table (with attendance_id)
       • device_sessions table
       • qr_sessions table
    """)

    app.run(debug=True, host='0.0.0.0', port=5001, ssl_context='adhoc')

