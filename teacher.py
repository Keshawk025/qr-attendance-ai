from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_file
import sqlite3
import hashlib
import hmac
import json
import time
import os
from io import BytesIO

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'teacher-attendance-secret-key-2025'

DATABASE = 'attendance.db'
SECRET_KEY = 'attendance-secret-2025'

def delta_hashes_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT UNIQUE NOT NULL,
            subject_name TEXT NOT NULL,
            teacher_id INTEGER NOT NULL,
            class_name TEXT,
            semester TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        )
    """)

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
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (session_id) REFERENCES qr_sessions(session_id),
            UNIQUE(student_id, session_id)
        )
    """)

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

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM teachers")
    if cursor.fetchone()[0] == 0:
        teachers_data = [
            ("Mrs. Shilpa Patil", "shilpapatil@saividya.ac.in", "shilpa123", "Computer Science"),
            ("Dr. Kumaresh Sheelavant", "kumareshsheelavant@saividya.ac.in", "kumaresh123", "Computer Science"),
            ("Dr. A C Vikramathithan", "vikramathithan@saividya.ac.in", "vikram123", "Computer Science"),
            ("Ms. Shail Kumari Shah", "shailshah@saividya.ac.in", "shail123", "Computer Science"),
            ("Ms. Pooja A", "poojaa@saividya.ac.in", "pooja123", "Computer Science"),
            ("Ms. Jayshri", "jayshri@saividya.ac.in", "jayshri123", "Computer Science"),
            ("Dr. Bhagya N P", "bhagyanp@saividya.ac.in", "bhagya123", "Environmental Science"),
            ("Dr. Sukruth Gowda M A", "sukruthgowda@saividya.ac.in", "sukruth123", "Computer Science"),
            ("Mrs. Geetha M", "geetham@saividya.ac.in", "geetha123", "Physical Education")
        ]

        teacher_map = {}
        for idx, (name, email, password, dept) in enumerate(teachers_data, 1):
            password_hash = delta_hashes_password(password)
            cursor.execute("""
                INSERT INTO teachers (name, email, password_hash, department)
                VALUES (?, ?, ?, ?)
            """, (name, email, password_hash, dept))
            teacher_map[idx] = cursor.lastrowid

        subjects_data = [
            ("BCS501", "Software Engineering & Project Management", 1, "5th Semester", "CS-A"),
            ("BCS502", "Computer Networks", 2, "5th Semester", "CS-A"),
            ("BCS503", "Theory of Computation", 3, "5th Semester", "CS-A"),
            ("BAIL504", "Data Visualization Lab", 4, "5th Semester", "CS-A"),
            ("BRMK557", "Research Methodology & IPR", 5, "5th Semester", "CS-A"),
            ("BCS515C", "Unix System Programming", 6, "5th Semester", "CS-A"),
            ("BCS508", "Environmental Studies and E-waste Management", 7, "5th Semester", "CS-A"),
            ("BCI586", "Mini Project", 8, "5th Semester", "CS-A"),
            ("BCS502L", "Computer Networks Lab", 2, "5th Semester", "CS-A"),
            ("BNSK559", "NSS/PE/Sports/Yoga", 9, "5th Semester", "CS-A"),
        ]

        for code, name, teacher_id, sem, class_name in subjects_data:
            cursor.execute("""
                INSERT INTO subjects (subject_code, subject_name, teacher_id, semester, class_name)
                VALUES (?, ?, ?, ?, ?)
            """, (code, name, teacher_id, sem, class_name))

        students = [
            ('1VA23CI051', 'Keshaw', 'keshaw@saividya.ac.in'),
            ('1VA23CI052', 'Karthik', 'karthik@saividya.ac.in'),
            ('1VA23CI016', 'Ashraya', 'ashraya@saividya.ac.in'),
            ('1VA23CI004', 'Aishwarya', 'aishwarya@saividya.ac.in')
        ]

        for usn, name, email in students:
            cursor.execute("""
                INSERT INTO students (usn, name, email)
                VALUES (?, ?, ?)
            """, (usn, name, email))

        conn.commit()

    conn.close()
    print("✅ Database initialized")

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teacher Login</title>
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
            box-shadow: 0 20px 30px rgba(0, 0, 0, 0.3);
            max-width: 450px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 30px;
            text-align: center;
            color: white;
        }
        .logo {
            width: 80px;
            height: 80px;
            background: white;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
        }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .form-container { padding: 40px 30px; }
        .form-group { margin-bottom: 25px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
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
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
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
        }
        button:hover { transform: translateY(-2px); }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .info {
            background: #d1ecf1;
            color: #0c5460;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 13px;
            max-height: 250px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">👨‍🏫</div>
            <h1>Saividya Teacher Portal</h1>
            <p>Smart Attendance System</p>
        </div>
        <div class="form-container">
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            <form method="POST">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" name="email" placeholder="teacher@saividya.ac.in" required autofocus>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="Enter password" required>
                </div>
                <button type="submit">🚀 Login</button>
            </form>
            <div class="info">
                <strong>Teachers:</strong><br>
                shilpapatil@saividya.ac.in / shilpa123<br>
                kumareshsheelavant@saividya.ac.in / kumaresh123<br>
                vikramathithan@saividya.ac.in / vikram123<br>
                shailshah@saividya.ac.in / shail123<br>
                poojaa@saividya.ac.in / pooja123<br>
                jayshri@saividya.ac.in / jayshri123<br>
                bhagyanp@saividya.ac.in / bhagya123<br>
                sukruthgowda@saividya.ac.in / sukruth123<br>
                geetham@saividya.ac.in / geetha123
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
    <title>Teacher Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        .header h1 { color: #333; font-size: 28px; }
        .logout-btn {
            padding: 10px 20px;
            background: #ff6b6b;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
        }
        .subject-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .subject-card {
            padding: 20px;
            background: #f8f9fa;
            border-radius: 15px;
            cursor: pointer;
            border: 3px solid transparent;
            transition: all 0.3s;
        }
        .subject-card:hover {
            border-color: #667eea;
            transform: translateY(-5px);
        }
        .subject-card.selected {
            border-color: #667eea;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .subject-code { font-size: 11px; opacity: 0.8; margin-bottom: 8px; font-weight: 600; }
        .subject-name { font-size: 16px; font-weight: 700; margin: 10px 0; }
        .generate-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
        }
        .generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .qr-section {
            text-align: center;
            padding: 30px;
        }
        .qr-code-img { max-width: 300px; border: 5px solid #667eea; border-radius: 10px; }
        .timer {
            font-size: 48px;
            font-weight: bold;
            color: #667eea;
            margin: 20px 0;
        }
        .timer.warning { color: #ff6b6b; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .attendance-item {
            display: flex;
            justify-content: space-between;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        .hidden { display: none !important; }
        .refresh-btn {
            padding: 12px 24px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <div>
                    <h1>👨‍🏫 Teacher Dashboard</h1>
                    <p>Welcome, {{ teacher_name }}</p>
                </div>
                <a href="/logout" class="logout-btn">🚪 Logout</a>
            </div>
            <div id="subjectSelection">
                <h3 style="margin-bottom: 20px; color: #333;">Your Subjects</h3>
                {% if subjects|length == 0 %}
                <p style="color: #999; text-align: center; padding: 40px;">No subjects assigned</p>
                {% else %}
                <div class="subject-grid">
                    {% for subject in subjects %}
                    <div class="subject-card" onclick="selectSubject({{ subject.subject_id }}, '{{ subject.subject_name }}', '{{ subject.subject_code }}')">
                        <div class="subject-code">{{ subject.subject_code }}</div>
                        <div class="subject-name">{{ subject.subject_name }}</div>
                        <div style="font-size: 12px; color: #666;">{{ subject.class_name }}</div>
                    </div>
                    {% endfor %}
                </div>
                <button class="generate-btn" id="generateBtn" onclick="generateQR()" disabled>
                    📱 Generate QR Code for Attendance
                </button>
                {% endif %}
            </div>
            <div id="qrSection" class="hidden">
                <div class="qr-section">
                    <h2>Scan QR Code</h2>
                    <div class="timer" id="qrTimer">30</div>
                    <img id="qrCodeImage" class="qr-code-img" alt="QR Code">
                    <p style="margin-top: 20px;">
                        Subject: <strong><span id="selectedSubjectName"></span></strong><br>
                        <span style="font-size: 12px; color: #999;">Session ID</span>
                    </p>
                    <p style="font-size: 14px; color: #999;">
                        <span id="sessionID"></span>
                    </p>
                </div>
                <div style="background: #d4edda; padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <strong>✅ Students Present:</strong> <span id="presentCount">0</span>
                </div>
                <h3 style="margin: 20px 0;">Live Attendance</h3>
                <div id="attendanceList" style="max-height: 400px; overflow-y: auto;">
                    <p style="text-align: center; color: #999; padding: 40px;">
                        Waiting for students...
                    </p>
                </div>
                <button class="refresh-btn" onclick="refreshQR()">🔄 Refresh QR Code</button>
                <button class="logout-btn" onclick="backToSubjects()" style="margin-left: 10px;">← Back</button>
            </div>
        </div>
    </div>
    <script>
        let selectedSubjectId = null;
        let selectedSubjectName = '';
        let selectedSubjectCode = '';
        let currentSessionId = null;
        let qrTimer = null;
        let timeLeft = 30;
        let attendanceCount = 0;

        function selectSubject(id, name, code) {
            selectedSubjectId = id;
            selectedSubjectName = name;
            selectedSubjectCode = code;
            document.querySelectorAll('.subject-card').forEach(card => {
                card.classList.remove('selected');
            });
            event.target.closest('.subject-card').classList.add('selected');
            document.getElementById('generateBtn').disabled = false;
        }

        async function generateQR() {
            if (!selectedSubjectId) {
                alert('Please select a subject');
                return;
            }
            try {
                const response = await fetch('/api/generate-qr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject_id: selectedSubjectId })
                });
                const data = await response.json();
                if (data.success) {
                    currentSessionId = data.session_id;
                    document.getElementById('subjectSelection').classList.add('hidden');
                    document.getElementById('qrSection').classList.remove('hidden');
                    document.getElementById('selectedSubjectName').textContent = selectedSubjectName;
                    document.getElementById('sessionID').textContent = currentSessionId;
                    document.getElementById('qrCodeImage').src = `/api/qr-image/${currentSessionId}`;
                    startTimer();
                    pollAttendance();
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (error) {
                alert('Error generating QR');
            }
        }

        function startTimer() {
            timeLeft = 30;
            const timerElement = document.getElementById('qrTimer');
            timerElement.classList.remove('warning');
            if (qrTimer) clearInterval(qrTimer);
            qrTimer = setInterval(() => {
                timeLeft--;
                timerElement.textContent = timeLeft;
                if (timeLeft <= 10) timerElement.classList.add('warning');
                if (timeLeft <= 0) {
                    clearInterval(qrTimer);
                    timerElement.textContent = 'EXPIRED';
                }
            }, 1000);
        }

        async function refreshQR() {
            await generateQR();
            attendanceCount = 0;
            document.getElementById('presentCount').textContent = '0';
            document.getElementById('attendanceList').innerHTML = '<p style="text-align: center; color: #999; padding: 40px;">Waiting for students...</p>';
        }

        async function pollAttendance() {
            if (!currentSessionId) return;
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/attendance-list/${currentSessionId}`);
                    const data = await response.json();
                    if (data.success && data.records.length > attendanceCount) {
                        updateAttendanceList(data.records);
                        attendanceCount = data.records.length;
                    }
                } catch (error) {
                    console.error('Poll error:', error);
                }
            }, 3000);
            setTimeout(() => clearInterval(interval), 120000);
        }

        function updateAttendanceList(records) {
            const listElement = document.getElementById('attendanceList');
            listElement.innerHTML = '';
            document.getElementById('presentCount').textContent = records.length;
            records.forEach(record => {
                const item = document.createElement('div');
                item.className = 'attendance-item';
                const time = new Date(record.marked_at).toLocaleTimeString();
                item.innerHTML = `
                    <div>
                        <div style="font-weight: 600;">${record.student_name}</div>
                        <div style="font-size: 12px; color: #666;">USN: ${record.usn || 'N/A'}</div>
                    </div>
                    <div style="color: #999; font-size: 12px;">${time}</div>
                `;
                listElement.appendChild(item);
            });
        }

        function backToSubjects() {
            if (qrTimer) clearInterval(qrTimer);
            currentSessionId = null;
            document.getElementById('qrSection').classList.add('hidden');
            document.getElementById('subjectSelection').classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    if 'teacher_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password_hash = delta_hashes_password(password)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT teacher_id, name, email
            FROM teachers
            WHERE email = ? AND password_hash = ?
        """, (email, password_hash))
        teacher = cursor.fetchone()
        conn.close()
        if teacher:
            session['teacher_id'] = teacher[0]
            session['teacher_name'] = teacher[1]
            session['teacher_email'] = teacher[2]
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_PAGE, error="Invalid credentials")
    return render_template_string(LOGIN_PAGE, error=None)

@app.route('/dashboard')
def dashboard():
    if 'teacher_id' not in session:
        return redirect(url_for('login'))
    teacher_id = session['teacher_id']
    teacher_name = session['teacher_name']
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject_id, subject_code, subject_name, class_name, semester
        FROM subjects
        WHERE teacher_id = ?
        ORDER BY subject_name
    """, (teacher_id,))
    subjects = cursor.fetchall()
    conn.close()
    return render_template_string(DASHBOARD_PAGE, teacher_name=teacher_name, subjects=subjects)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/generate-qr', methods=['POST'])
def generate_qr():
    if 'teacher_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    try:
        data = request.json
        subject_id = data['subject_id']
        timestamp = int(time.time())
        session_id = f"SESSION_{subject_id}_{timestamp}"
        nonce = hashlib.sha256(f"{session_id}{timestamp}".encode()).hexdigest()[:16]
        qr_payload = {
            'session_id': session_id,
            'subject_id': subject_id,
            'timestamp': timestamp,
            'expiry': timestamp + 30,
            'nonce': nonce
        }
        message = f"{session_id}:{subject_id}:{timestamp}:{nonce}:{SECRET_KEY}"
        signature = hmac.new(
            SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        qr_payload['signature'] = signature
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qr_sessions 
            (session_id, subject_id, timestamp, expiry, nonce, signature, qr_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, subject_id, timestamp, timestamp + 30, nonce, signature, json.dumps(qr_payload)))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'session_id': session_id, 'qr_data': qr_payload, 'expires_in': 30})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/qr-image/<session_id>')
def get_qr_image(session_id):
    if not QR_AVAILABLE:
        return "QR library not available", 500
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT qr_data FROM qr_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return "Session not found", 404
        qr_data = json.loads(row[0])
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return send_file(img_buffer, mimetype='image/png')
    except Exception as e:
        return str(e), 500

@app.route('/api/attendance-list/<session_id>')
def get_attendance_list(session_id):
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.attendance_id, a.student_name, a.marked_at, s.usn
            FROM attendance a
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE a.session_id = ?
            ORDER BY a.marked_at DESC
        """, (session_id,))
        records = cursor.fetchall()
        conn.close()
        return jsonify({'success': True, 'total_present': len(records), 'records': [dict(r) for r in records]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("="*70)
    print("🎓 FINAL TEACHER APP - SAIVIDYA WITH REAL STUDENTS")
    print("="*70)
    if not QR_AVAILABLE:
        print("\n⚠️ pip install qrcode[pil]")
    if not os.path.exists(DATABASE):
        print("\n🔧 Creating database...")
        init_database()
    else:
        print("\n✅ Database found")
    print("\n✅ 9 Teachers with their subjects")
    print("✅ 14 Students (including real ones)")
    print("✅ HTTPS enabled")
    print("\n🚀 Starting on https://localhost:5000")
    print("="*70)
    print()
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc')
