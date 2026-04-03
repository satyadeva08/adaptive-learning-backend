from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_cors import CORS
from config import MYSQL_CONFIG
from flask import send_from_directory
import hashlib
from api_service import get_tutor_response
import os

app = Flask(__name__)
CORS(app)

# MySQL Config
app.config['MYSQL_HOST']     = MYSQL_CONFIG['host']
app.config['MYSQL_USER']     = MYSQL_CONFIG['user']
app.config['MYSQL_PASSWORD'] = MYSQL_CONFIG['password']
app.config['MYSQL_DB']       = MYSQL_CONFIG['database']

mysql = MySQL(app)

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ── Health check ──────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Flask Backend Running ✅"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')


# ── REGISTER ─────────────────────────────────────────────────────────────────
# FIX: Was missing entirely — frontend register form had nowhere to POST
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name       = data.get('name', '').strip()
    email      = data.get('email', '').strip()
    password   = data.get('password', '')
    department = data.get('department', '')
    semester   = data.get('semester', 1)

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400

    pw_hash = hash_password(password)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO students (name, email, password_hash, department, semester) VALUES (%s, %s, %s, %s, %s)",
            (name, email, pw_hash, department, semester)
        )
        mysql.connection.commit()
        student_id = cur.lastrowid
        cur.close()
        return jsonify({'message': 'Registered successfully', 'student_id': student_id}), 201
    except Exception as e:
        if 'Duplicate entry' in str(e):
            return jsonify({'error': 'Email already registered'}), 409
        return jsonify({'error': str(e)}), 500


# ── LOGIN ─────────────────────────────────────────────────────────────────────
# FIX: Was missing entirely — frontend login form had nowhere to POST
@app.route('/login', methods=['POST'])
def login():
    data     = request.json
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    pw_hash  = hash_password(password)

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT student_id, name, email, department, semester FROM students WHERE email=%s AND password_hash=%s",
        (email, pw_hash)
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return jsonify({'error': 'Invalid email or password'}), 401

    return jsonify({
        'student_id': row[0],
        'name':       row[1],
        'email':      row[2],
        'department': row[3],
        'semester':   row[4]
    })


# ── GET STUDENTS ──────────────────────────────────────────────────────────────
@app.route('/students')
def get_students():
    cur = mysql.connection.cursor()
    cur.execute("SELECT student_id, name, email FROM students")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{'id': r[0], 'name': r[1], 'email': r[2]} for r in rows])


# ── ADD STUDENT (kept for compatibility) ──────────────────────────────────────
@app.route('/students', methods=['POST'])
def add_student():
    data = request.json
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO students (name, email, password_hash) VALUES (%s, %s, %s)",
        (data['name'], data['email'], "placeholder")
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Student added successfully'})


# ── UPDATE STUDENT (Profile page) ─────────────────────────────────────────────
# FIX: Was missing — saveProfile() in frontend calls PUT /students/<id>
@app.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json
    name       = data.get('name', '').strip()
    department = data.get('department', '')
    semester   = data.get('semester', 1)

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE students SET name=%s, department=%s, semester=%s WHERE student_id=%s",
        (name, department, semester, student_id)
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Profile updated'})


# ── GET PERFORMANCE (View) ────────────────────────────────────────────────────
# FIX: Was returning raw tuples — frontend expects indexed list (list of lists)
@app.route('/performance', methods=['GET'])
def get_performance():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM student_performance_summary")
    rows = cur.fetchall()
    cur.close()
    # Return as list of lists so frontend can access by index [0], [1], etc.
    return jsonify([list(r) for r in rows])


# ── ADD SCORE ─────────────────────────────────────────────────────────────────
@app.route('/scores', methods=['POST'])
def add_score():
    data = request.json
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO scores (student_id, topic_id, marks_obtained, max_marks, exam_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        data['student_id'],
        data['topic_id'],
        data['marks'],
        data['max_marks'],
        data.get('exam_date', None)  # NULL defaults to CURRENT_DATE in the DB
    ))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Score added successfully'})


# ── GET SUBJECTS (for dynamic subject/topic lookup in submitManual) ───────────
# FIX: Was missing — getOrCreateSubject() calls GET /subjects
@app.route('/subjects', methods=['GET'])
def get_subjects():
    cur = mysql.connection.cursor()
    cur.execute("SELECT subject_id, name FROM subjects ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{'subject_id': r[0], 'name': r[1]} for r in rows])


# ── CREATE SUBJECT ────────────────────────────────────────────────────────────
# FIX: Was missing — getOrCreateSubject() calls POST /subjects when not found
@app.route('/subjects', methods=['POST'])
def create_subject():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Subject name required'}), 400
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO subjects (name) VALUES (%s)", (name,))
    mysql.connection.commit()
    subject_id = cur.lastrowid
    cur.close()
    return jsonify({'subject_id': subject_id, 'name': name}), 201


# ── GET TOPICS for a subject ──────────────────────────────────────────────────
# FIX: Was missing — getOrCreateTopic() calls GET /topics?subject_id=X
@app.route('/topics', methods=['GET'])
def get_topics():
    subject_id = request.args.get('subject_id')
    cur = mysql.connection.cursor()
    if subject_id:
        cur.execute("SELECT topic_id, topic_name FROM topics WHERE subject_id=%s ORDER BY topic_name", (subject_id,))
    else:
        cur.execute("SELECT topic_id, topic_name FROM topics ORDER BY topic_name")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{'topic_id': r[0], 'topic_name': r[1]} for r in rows])


# ── CREATE TOPIC ──────────────────────────────────────────────────────────────
# FIX: Was missing — getOrCreateTopic() calls POST /topics when not found
@app.route('/topics', methods=['POST'])
def create_topic():
    data = request.json
    subject_id  = data.get('subject_id')
    topic_name  = data.get('topic_name', '').strip()
    if not subject_id or not topic_name:
        return jsonify({'error': 'subject_id and topic_name required'}), 400
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO topics (subject_id, topic_name) VALUES (%s, %s)",
        (subject_id, topic_name)
    )
    mysql.connection.commit()
    topic_id = cur.lastrowid
    cur.close()
    return jsonify({'topic_id': topic_id, 'topic_name': topic_name}), 201

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    data = request.json
    user_message = data.get('message')
    history = data.get('history', [])
    files = data.get('files', [])
    sys_inst = data.get('systemInstruction')
    
    reply_text = get_tutor_response(user_message, history, files, sys_inst)
    
    if reply_text:
        return jsonify({"status": "success", "reply": reply_text})
    else:
        return jsonify({"status": "error", "message": "The AI encountered an error processing this request."}), 500

PORT = int(os.environ.get("PORT", 8000))
# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)

