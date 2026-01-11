# Teacher-Student Attendance System

A comprehensive QR code-based attendance management system for educational institutions, featuring separate interfaces for teachers and students.

## 🎯 Overview

This system consists of two Flask applications that work together:

- **Teacher Portal** (`teacher.py`): Teachers generate QR codes for attendance sessions
- **Student Portal** (`student.py`): Students scan QR codes to mark their attendance

Both applications share a common SQLite database (`attendance.db`) and use secure HMAC-SHA256 signatures for QR code validation.

## 📋 Features

### Teacher Features
- Secure login with email/password
- Subject management dashboard
- QR code generation for attendance sessions
- Real-time attendance monitoring
- 30-second QR code expiry for security
- Live attendance count updates

### Student Features
- USN-based login system
- Device fingerprinting for security
- Camera-based QR code scanning
- Real-time validation feedback
- Duplicate attendance prevention
- Multi-device session management

### Security Features
- HMAC-SHA256 QR code signatures
- Time-based QR expiry (30 seconds)
- Device session tracking
- SQL injection prevention
- Cross-Site Request Forgery protection

## 🛠️ Installation

### Prerequisites
- Python 3.7+
- Webcam/camera access (for students)
- Modern web browser with camera permissions

### Dependencies

Install required packages:

```bash
pip install flask flask-cors qrcode[pil]
```

For QR code generation (teacher app):
```bash
pip install qrcode[pil]
```

For CORS support (student app):
```bash
pip install flask-cors
```

## 🚀 Setup and Running

### 1. Initialize Database

Run the teacher application first to create the database:

```bash
python teacher.py
```

This will:
- Create `attendance.db` SQLite database
- Initialize tables (teachers, subjects, students, attendance, qr_sessions, device_sessions)
- Populate with sample data (9 teachers, 10 subjects, 4 students)

### 2. Run Both Applications

#### Terminal 1 - Teacher Portal
```bash
python teacher.py
```
- Access: https://localhost:5000
- Default teachers listed in login page

#### Terminal 2 - Student Portal
```bash
python student.py
```
- Access: https://localhost:5001
- Login with student USN (e.g., 1VA23CI051)

### 3. Usage Workflow

1. **Teacher Login**: Use credentials from the login page info box
2. **Select Subject**: Choose from assigned subjects
3. **Generate QR**: Click "Generate QR Code" button
4. **Display QR**: Show the generated QR code to students (expires in 30 seconds)
5. **Student Scan**: Students scan the QR code using their device camera
6. **Monitor Attendance**: Teachers see live attendance updates

## 📊 Database Schema

### Tables
- `teachers`: Teacher information and credentials
- `subjects`: Subject details and teacher assignments
- `students`: Student information (USN, name, email)
- `attendance`: Attendance records with timestamps
- `qr_sessions`: QR code session data with signatures
- `device_sessions`: Student device tracking

### Sample Data
- **Teachers**: 9 faculty members with email/password login
- **Subjects**: 10 computer science subjects for 5th semester
- **Students**: 4 sample students with USN format 1VA23CI0XX

## 🔐 Security

- **QR Validation**: HMAC-SHA256 signatures prevent forgery
- **Time Limits**: 30-second expiry prevents replay attacks
- **Device Tracking**: Prevents multi-device simultaneous logins
- **Session Management**: Secure Flask sessions with secret keys

## 🐛 Troubleshooting

### Common Issues

1. **QR Code Not Scanning**
   - Ensure camera permissions are granted
   - Check QR code hasn't expired (30s limit)
   - Verify internet connection for real-time validation

2. **Database Errors**
   - Delete `attendance.db` and restart teacher.py
   - Check file permissions in the directory

3. **Port Conflicts**
   - Teacher: port 5000, Student: port 5001
   - Change ports in the `app.run()` calls if needed

4. **Missing Dependencies**
   - Install all required packages: `pip install flask flask-cors qrcode[pil]`

### Debug Mode
Both applications run in debug mode by default. Check console output for detailed error messages.

## 📁 File Structure

```
teacher_attendance/
├── teacher.py          # Teacher Flask application
├── student.py          # Student Flask application
├── gethash.py          # Password hashing utility
├── attendance.db       # SQLite database (auto-created)
└── README.md          # This file
```

## 🔧 Configuration

### Ports
- Teacher Portal: `https://localhost:5000`
- Student Portal: `https://localhost:5001`

### Secrets
- Database: `attendance.db`
- Secret Key: `'attendance-secret-2025'`
- Session Secret: `'teacher-attendance-secret-key-2025'` / `'student-attendance-secret-2025'`

### QR Settings
- Expiry: 30 seconds
- Error Correction: High (H)
- Box Size: 10x10 pixels

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Test both teacher and student portals
5. Submit a pull request

## 📄 License

This project is for educational purposes. Modify and distribute as needed.

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Verify all dependencies are installed
3. Ensure both applications are running simultaneously
4. Check browser console for JavaScript errors

---

**Note**: This system uses self-signed SSL certificates for HTTPS. Accept the security warning in your browser when accessing the applications.</content>
<parameter name="filePath">README.md
