from flask import Flask, render_template, request, session, redirect, url_for, flash, Response
import sqlite3
# from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
def init_db():
    conn = sqlite3.connect('results.db')
    return conn

# model = SentenceTransformer('all-MiniLM-L6-v2')

def compute_similarity(reference_answer, student_answer):
    if not student_answer.strip():
        return 0.0
    # ref_embedding = model.encode(reference_answer)
    # student_embedding = model.encode(student_answer)
    # similarity = cosine_similarity([ref_embedding], [student_embedding])[0][0]
    # return float(similarity)
    return 0

def calculate_marks(similarity, max_marks):
    if similarity >= 0.8:
        return max_marks
    elif similarity >= 0.6:
        return max_marks * 0.8
    elif similarity >= 0.4:
        return max_marks * 0.6
    elif similarity >= 0.2:
        return max_marks * 0.4
    else:
        return 0

def setup():
    conn = init_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER,
        question_text TEXT,
        model_answer TEXT,
        max_marks INTEGER,
        created_at TEXT,
        FOREIGN KEY (teacher_id) REFERENCES teachers(id)
    )''')
    try:
        c.execute('ALTER TABLE questions ADD COLUMN allow_resubmission INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE questions ADD COLUMN deadline_at TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE questions ADD COLUMN open_at TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE questions ADD COLUMN close_at TEXT')
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        student_id INTEGER,
        answer_text TEXT,
        marks_obtained REAL,
        similarity REAL,
        submitted_at TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id),
        FOREIGN KEY (student_id) REFERENCES students(id)
    )''')
    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_submission ON submissions (question_id, student_id)')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
setup()

# Function for teacher login
def login_teacher(conn, email, password):
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM teachers WHERE email = ? AND password = ?', (email, password))
    return cursor.fetchone()

# Fetch classes and subjects for a teacher
def fetch_classes_subjects(conn, teacher_id):
    cursor = conn.cursor()
    cursor.execute('SELECT class_name, subject_name FROM classes_subjects WHERE teacher_id = ?', (teacher_id,))
    return cursor.fetchall()

# Fetch results for a specific class and subject
def fetch_results_for_class_subject(conn, teacher_id, class_name, subject_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT student_name, total_marks, max_marks
        FROM results
        WHERE teacher_id = (SELECT id FROM teachers WHERE id = ?)
        AND class_name = ? AND subject_name = ?
    ''', (teacher_id, class_name, subject_name))
    return cursor.fetchall()

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    role = request.form.get('role')
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not role or not name or not email or not password:
        return render_template('index.html', error='All fields are required.')
    conn = init_db()
    cur = conn.cursor()
    try:
        if role == 'teacher':
            cur.execute('INSERT INTO teachers (name, email, password) VALUES (?, ?, ?)', (name, email, generate_password_hash(password)))
        elif role == 'student':
            cur.execute('INSERT INTO students (name, email, password) VALUES (?, ?, ?)', (name, email, generate_password_hash(password)))
        else:
            conn.close()
            return render_template('index.html', error='Invalid role.')
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template('index.html', error='Email already registered.')
    conn.close()
    return render_template('index.html', message='Registration successful. Please log in.')

@app.route('/login', methods=['POST'])
def login():
    role = request.form.get('role')
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    conn = init_db()
    cur = conn.cursor()
    user = None
    name = None
    if role == 'teacher':
        cur.execute('SELECT id, name, password FROM teachers WHERE email = ?', (email,))
        row = cur.fetchone()
        if row and check_password_hash(row[2], password):
            user = row[0]
            name = row[1]
            session['teacher_id'] = user
            session['teacher_name'] = name
    elif role == 'student':
        cur.execute('SELECT id, name, password FROM students WHERE email = ?', (email,))
        row = cur.fetchone()
        if row and check_password_hash(row[2], password):
            user = row[0]
            name = row[1]
            session['student_id'] = user
            session['student_name'] = name
    conn.close()
    if not user:
        return render_template('index.html', error='Invalid login credentials.')
    session['role'] = role
    session['user_id'] = user
    session['user_name'] = name
    if role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'role' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/teacher/dashboard', methods=['GET'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    teacher_id = session.get('teacher_id')
    teacher_name = session.get('teacher_name')
    conn = init_db()
    cur = conn.cursor()
    cur.execute('SELECT id, question_text, model_answer, max_marks, created_at, allow_resubmission, open_at, close_at FROM questions WHERE teacher_id = ? ORDER BY id DESC', (teacher_id,))
    questions = cur.fetchall()
    now = datetime.now()
    for q in questions:
        qid = q[0]
        close_at = q[7]
        if close_at:
            try:
                if now >= datetime.fromisoformat(close_at):
                    cur2 = conn.cursor()
                    cur2.execute('SELECT id FROM students WHERE id NOT IN (SELECT student_id FROM submissions WHERE question_id = ?)', (qid,))
                    missing = cur2.fetchall()
                    for row in missing:
                        sid = row[0]
                        cur2.execute('INSERT OR IGNORE INTO submissions (question_id, student_id, answer_text, marks_obtained, similarity, submitted_at) VALUES (?, ?, ?, ?, ?, ?)', (qid, sid, '', 0.0, 0.0, datetime.now().isoformat()))
                    conn.commit()
            except Exception:
                pass
    cur.execute('SELECT COUNT(*) FROM students')
    student_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT s.student_id) FROM submissions s JOIN questions q ON s.question_id = q.id WHERE q.teacher_id = ?', (teacher_id,))
    submitted_student_count = cur.fetchone()[0]
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    per_page = 10
    offset = (page - 1) * per_page
    cur.execute('''
        SELECT COUNT(*)
        FROM submissions s
        JOIN questions q ON s.question_id = q.id
        WHERE q.teacher_id = ?
    ''', (teacher_id,))
    total_count = cur.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page if total_count else 1
    cur.execute('''
        SELECT s.id, st.name, q.question_text, s.marks_obtained, s.similarity, s.submitted_at
        FROM submissions s
        JOIN students st ON s.student_id = st.id
        JOIN questions q ON s.question_id = q.id
        WHERE q.teacher_id = ?
        ORDER BY s.id DESC
        LIMIT ? OFFSET ?
    ''', (teacher_id, per_page, offset))
    submissions = cur.fetchall()
    conn.close()
    return render_template(
        'teacher_dashboard.html',
        teacher_name=teacher_name,
        questions=questions,
        student_count=student_count,
        submitted_student_count=submitted_student_count,
        submissions=submissions,
        page=page,
        total_pages=total_pages
    )

@app.route('/teacher/submissions/<int:submission_id>')
def teacher_submission_detail(submission_id):
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    teacher_id = session.get('teacher_id')
    conn = init_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.id, st.name, q.question_text, q.model_answer, s.answer_text, s.marks_obtained, s.similarity, s.submitted_at
        FROM submissions s
        JOIN students st ON s.student_id = st.id
        JOIN questions q ON s.question_id = q.id
        WHERE s.id = ? AND q.teacher_id = ?
    ''', (submission_id, teacher_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        flash('Submission not found.', 'error')
        return redirect(url_for('teacher_dashboard'))
    return render_template('submission_detail.html', submission=row)

@app.route('/teacher/questions/create', methods=['POST'])
def create_question():
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    question_text = request.form.get('question_text', '').strip()
    model_answer = request.form.get('model_answer', '').strip()
    max_marks = request.form.get('max_marks', '').strip()
    if not question_text or not model_answer or not max_marks:
        flash('All fields are required to create a question.', 'error')
        return redirect(url_for('teacher_dashboard'))
    try:
        max_marks_val = int(max_marks)
    except ValueError:
        flash('Max marks must be a number.', 'error')
        return redirect(url_for('teacher_dashboard'))
    conn = init_db()
    cur = conn.cursor()
    allow_resub = 1 if request.form.get('allow_resubmission') else 0
    open_at = request.form.get('open_at', '').strip() or None
    close_at = request.form.get('close_at', '').strip() or None
    deadline_at = close_at
    cur.execute('INSERT INTO questions (teacher_id, question_text, model_answer, max_marks, created_at, allow_resubmission, deadline_at, open_at, close_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (session.get('teacher_id'), question_text, model_answer, max_marks_val, datetime.now().isoformat(), allow_resub, deadline_at, open_at, close_at))
    conn.commit()
    conn.close()
    flash('Question created successfully.', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/questions/<int:question_id>/update', methods=['POST'])
def update_question(question_id):
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    question_text = request.form.get('question_text', '').strip()
    model_answer = request.form.get('model_answer', '').strip()
    max_marks = request.form.get('max_marks', '').strip()
    try:
        max_marks_val = int(max_marks)
    except ValueError:
        flash('Max marks must be a number.', 'error')
        return redirect(url_for('teacher_dashboard'))
    conn = init_db()
    cur = conn.cursor()
    allow_resub = 1 if request.form.get('allow_resubmission') else 0
    open_at = request.form.get('open_at', '').strip() or None
    close_at = request.form.get('close_at', '').strip() or None
    deadline_at = close_at
    cur.execute('UPDATE questions SET question_text = ?, model_answer = ?, max_marks = ?, allow_resubmission = ?, deadline_at = ?, open_at = ?, close_at = ? WHERE id = ? AND teacher_id = ?', (question_text, model_answer, max_marks_val, allow_resub, deadline_at, open_at, close_at, question_id, session.get('teacher_id')))
    conn.commit()
    conn.close()
    flash('Question updated.', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/questions/<int:question_id>/delete', methods=['POST'])
def delete_question(question_id):
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    conn = init_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM submissions WHERE question_id = ?', (question_id,))
    cur.execute('DELETE FROM questions WHERE id = ? AND teacher_id = ?', (question_id, session.get('teacher_id')))
    conn.commit()
    conn.close()
    flash('Question deleted.', 'warning')
    return redirect(url_for('teacher_dashboard'))

@app.route('/student/dashboard', methods=['GET'])
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('index'))
    student_id = session.get('student_id')
    student_name = session.get('student_name')
    conn = init_db()
    cur = conn.cursor()
    cur.execute('SELECT q.id, q.question_text, q.max_marks, t.name, q.allow_resubmission, q.open_at, q.close_at FROM questions q JOIN teachers t ON q.teacher_id = t.id ORDER BY q.id DESC')
    questions = cur.fetchall()
    cur.execute('''
        SELECT s.id, s.question_id, q.question_text, s.marks_obtained, s.similarity, s.submitted_at
        FROM submissions s
        JOIN questions q ON s.question_id = q.id
        WHERE s.student_id = ?
        ORDER BY s.id DESC
    ''', (student_id,))
    my_submissions = cur.fetchall()
    conn.close()
    submitted_qids = {row[1] for row in my_submissions}
    now = datetime.now()
    not_open_qids = set()
    deadline_locked_qids = set()
    submittable_qids = set()
    auto_submitted = False
    conn2 = init_db()
    cur2 = conn2.cursor()
    for q in questions:
        qid = q[0]
        allow_resub = bool(q[4])
        open_at = q[5]
        close_at = q[6]
        opened = True
        locked_deadline = False
        if open_at:
            try:
                if now < datetime.fromisoformat(open_at):
                    opened = False
            except Exception:
                pass
        if close_at:
            try:
                if now >= datetime.fromisoformat(close_at):
                    locked_deadline = True
            except Exception:
                pass
        if not opened:
            not_open_qids.add(qid)
        if locked_deadline:
            if qid not in submitted_qids:
                cur2.execute('INSERT OR IGNORE INTO submissions (question_id, student_id, answer_text, marks_obtained, similarity, submitted_at) VALUES (?, ?, ?, ?, ?, ?)', (qid, student_id, '', 0.0, 0.0, datetime.now().isoformat()))
                conn2.commit()
                submitted_qids.add(qid)
                auto_submitted = True
            deadline_locked_qids.add(qid)
        already_submitted = (qid in submitted_qids)
        allowed_by_resub = (not already_submitted) or allow_resub
        allowed_by_deadline = not locked_deadline
        allowed_by_open = opened
        if allowed_by_resub and allowed_by_deadline and allowed_by_open:
            submittable_qids.add(qid)
    conn2.close()
    if auto_submitted:
        flash('Some answers were auto-submitted due to the end of the time window.', 'info')
    return render_template('student_dashboard.html', student_name=student_name, questions=questions, my_submissions=my_submissions, submitted_qids=submitted_qids, deadline_locked_qids=deadline_locked_qids, submittable_qids=submittable_qids, not_open_qids=not_open_qids, server_now=datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))

@app.route('/student/submit/<int:question_id>', methods=['POST'])
def submit_answer(question_id):
    if session.get('role') != 'student':
        return redirect(url_for('index'))
    student_id = session.get('student_id')
    answer_text = request.form.get('answer_text', '').strip()
    if not answer_text:
        flash('Answer cannot be empty.', 'error')
        return redirect(url_for('student_dashboard'))
    conn = init_db()
    cur = conn.cursor()
    cur.execute('SELECT model_answer, max_marks, allow_resubmission, open_at, close_at FROM questions WHERE id = ?', (question_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash('Question not found.', 'error')
        return redirect(url_for('student_dashboard'))
    model_answer = row[0]
    max_marks = int(row[1])
    allow_resub = bool(row[2])
    open_at = row[3]
    close_at = row[4]
    if open_at:
        try:
            if datetime.now() < datetime.fromisoformat(open_at):
                conn.close()
                flash('This question is not open yet.', 'error')
                return redirect(url_for('student_dashboard'))
        except Exception:
            pass
    if close_at:
        try:
            if datetime.now() >= datetime.fromisoformat(close_at):
                conn.close()
                flash('Time window has ended. Submissions are closed.', 'error')
                return redirect(url_for('student_dashboard'))
        except Exception:
            pass
    cur.execute('SELECT id FROM submissions WHERE question_id = ? AND student_id = ?', (question_id, student_id))
    existing = cur.fetchone()
    if existing:
        if not allow_resub:
            conn.close()
            flash('You have already submitted for this question. Resubmission is not allowed.', 'error')
            return redirect(url_for('student_dashboard'))
        sim = compute_similarity(model_answer, answer_text)
        marks = calculate_marks(sim, max_marks)
        cur.execute('UPDATE submissions SET answer_text = ?, marks_obtained = ?, similarity = ?, submitted_at = ? WHERE id = ?', (answer_text, float(marks), float(sim), datetime.now().isoformat(), existing[0]))
        flash(f'Resubmission successful. Marks: {marks:.2f}/{max_marks}', 'info')
    else:
        sim = compute_similarity(model_answer, answer_text)
        marks = calculate_marks(sim, max_marks)
        cur.execute('INSERT INTO submissions (question_id, student_id, answer_text, marks_obtained, similarity, submitted_at) VALUES (?, ?, ?, ?, ?, ?)', (question_id, student_id, answer_text, float(marks), float(sim), datetime.now().isoformat()))
        flash(f'Answer submitted. Marks: {marks:.2f}/{max_marks}', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('student_dashboard'))

@app.route('/teacher/export/csv', methods=['GET'])
def export_teacher_csv():
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    teacher_id = session.get('teacher_id')
    teacher_name = session.get('teacher_name') or 'teacher'
    conn = init_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.id, st.name, st.email, q.id, q.question_text, s.answer_text, s.marks_obtained, s.similarity, q.max_marks, s.submitted_at
        FROM submissions s
        JOIN students st ON s.student_id = st.id
        JOIN questions q ON s.question_id = q.id
        WHERE q.teacher_id = ?
        ORDER BY s.id DESC
    ''', (teacher_id,))
    rows = cur.fetchall()
    conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Submission ID', 'Student Name', 'Student Email', 'Question ID', 'Question', 'Student Answer', 'Obtained Score', 'Similarity', 'Max Marks', 'Submitted At'])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], f"{float(r[6]):.2f}", f"{float(r[7]):.3f}", r[8], r[9]])
    csv_data = output.getvalue()
    output.close()
    filename = f"{teacher_name.replace(' ', '_')}_submissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

if __name__ == '__main__':
    app.run(debug=True)
