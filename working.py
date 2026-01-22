import streamlit as st
# import PyPDF2
import re
import sqlite3
# from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load pre-trained Sentence Transformer model
# model = SentenceTransformer('all-MiniLM-L6-v2')

# Function to extract text from a PDF file
# def extract_text_from_pdf(pdf_file):
#     reader = PyPDF2.PdfReader(pdf_file)
#     text = ''
#     for page in reader.pages:
#         text += page.extract_text()
#     return text.strip()

# Function to split the extracted text into a list of answers
# Function to split text while preserving question numbers
# def split_answers(text):
#     matches = re.findall(r'Answer\s*(\d+)\s*:(.*?)(?=(Answer\s*\d+\s*:|$))', text, re.DOTALL)
#     answer_dict = {}
#     for match in matches:
#         question_number = int(match[0])  # Extracted question number
#         answer_text = match[1].strip()  # Extracted answer text
#         answer_dict[question_number] = answer_text
#     return answer_dict  # Return dictionary {question_number: answer}

# Function to compute similarity using Sentence Transformers
def compute_similarity(reference_answer, student_answer):
    if not student_answer.strip():
        return 0.0  # No answer provided, similarity is 0
    
    # Compute embeddings
    # ref_embedding = model.encode(reference_answer)
    # student_embedding = model.encode(student_answer)
    
    # Compute cosine similarity
    # similarity = cosine_similarity([ref_embedding], [student_embedding])[0][0]
    # return similarity

# Function to calculate marks dynamically based on similarity thresholds and max marks
def calculate_marks(similarity, max_marks):
    if similarity >= 0.9:
        return max_marks
    elif similarity >= 0.8:
        return max_marks * 0.8
    elif similarity >= 0.6:
        return max_marks * 0.6
    elif similarity >= 0.4:
        return max_marks * 0.4
    elif similarity >= 0.2:
        return max_marks * 0.2
    else:
        return 0

# Database connection and initialization
def init_db():
    conn = sqlite3.connect('results.db')
    cursor = conn.cursor()

    # Teacher registration table
    cursor.execute('''CREATE TABLE IF NOT EXISTS teachers (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      email TEXT UNIQUE,
                      password TEXT)''')

    # Classes and subjects table
    cursor.execute('''CREATE TABLE IF NOT EXISTS classes_subjects (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      teacher_id INTEGER,
                      class_name TEXT,
                      subject_name TEXT,
                      FOREIGN KEY (teacher_id) REFERENCES teachers (id))''')

    # Results table
    cursor.execute('''CREATE TABLE IF NOT EXISTS results (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      teacher_id INTEGER,
                      class_name TEXT,
                      subject_name TEXT,
                      student_name TEXT,
                      total_marks INTEGER,
                      max_marks INTEGER,
                      FOREIGN KEY (teacher_id) REFERENCES teachers (id))''')

    conn.commit()
    return conn

# Function for teacher registration
def register_teacher(conn, name, email, password):
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO teachers (name, email, password) VALUES (?, ?, ?)', (name, email, password))
        conn.commit()
        st.success("Registration successful!")
    except sqlite3.IntegrityError:
        st.error("Email already registered.")

# Function for teacher login
def login_teacher(conn, email, password):
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM teachers WHERE email = ? AND password = ?', (email, password))
    return cursor.fetchone()  # Returns (id, name) if valid, None otherwise

# Function to add class and subject for a teacher
def add_class_subject(conn, teacher_id, class_name, subject_name):
    cursor = conn.cursor()
    cursor.execute('INSERT INTO classes_subjects (teacher_id, class_name, subject_name) VALUES (?, ?, ?)',
                   (teacher_id, class_name, subject_name))
    conn.commit()

# Function to store results in the database
def store_results(conn, teacher_name, class_name, subject_name, student_name, marks, max_marks):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO results (teacher_id, class_name, subject_name, student_name, total_marks, max_marks)
        VALUES ((SELECT id FROM teachers WHERE name = ?), ?, ?, ?, ?, ?)
    ''', (teacher_name, class_name, subject_name, student_name, marks, max_marks))
    conn.commit()

# Function to fetch results from the database
def fetch_results(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.name AS teacher_name, r.class_name, r.subject_name, r.student_name, r.total_marks, r.max_marks
        FROM results r
        JOIN teachers t ON r.teacher_id = t.id
    ''')
    return cursor.fetchall()


# Streamlit App
st.title('Teacher Dashboard')

# Initialize database
conn = init_db()

# Tabs for registration and login
tab1, tab2 = st.tabs(["Register", "Login"])

# Teacher Registration
with tab1:
    st.header("Register as a Teacher")
    reg_name = st.text_input("Name")
    reg_email = st.text_input("Email")
    reg_password = st.text_input("Password", type="password")
    if st.button("Register"):
        register_teacher(conn, reg_name, reg_email, reg_password)

# Teacher Login
with tab2:
    st.header("Teacher Login")
    login_email = st.text_input("Email (Login)")
    login_password = st.text_input("Password (Login)", type="password")
    if st.button("Login"):
        teacher = login_teacher(conn, login_email, login_password)
        if teacher:
            teacher_id, teacher_name = teacher
            st.success(f"Welcome, {teacher_name}!")
            st.session_state['teacher_id'] = teacher_id
        else:
            st.error("Invalid login credentials.")

# Check if teacher is logged in
if 'teacher_id' in st.session_state:
    teacher_id = st.session_state['teacher_id']

    # Manage classes and subjects
    st.header("Manage Classes and Subjects")
    class_name = st.text_input("Class Name")
    subject_name = st.text_input("Subject Name")
    if st.button("Add Class & Subject"):
        add_class_subject(conn, teacher_id, class_name, subject_name)
        st.success(f"Added {class_name} - {subject_name} to your profile.")

    # Display all classes and subjects
    cursor = conn.cursor()
    cursor.execute('SELECT class_name, subject_name FROM classes_subjects WHERE teacher_id = ?', (teacher_id,))
    classes_subjects = cursor.fetchall()
    if classes_subjects:
        st.write("Your Classes and Subjects:")
        for class_name, subject_name in classes_subjects:
            st.write(f"Class: {class_name}, Subject: {subject_name}")
    else:
        st.write("No classes or subjects added yet.")

    # Placeholder for additional functionality
    st.header("Evaluate Student Answers")

def calculate_total_marks(marks_per_question, or_question_pairs):
    counted_or_questions = set()  # Track OR-type questions that have been counted
    total_marks = 0

    for i in range(len(marks_per_question)):
        # Check if the current question is in an OR-type pair
        if any(i in pair for pair in or_question_pairs):
            if i not in counted_or_questions:
                # Find the OR pair
                or_pair = next(pair for pair in or_question_pairs if i in pair)
                counted_or_questions.update(or_pair)  # Mark both as counted

                # Take the **higher** marks from the OR pair
                total_marks += max(marks_per_question[or_pair[0]], marks_per_question[or_pair[1]])
        else:
            # If it's a normal question, just add its marks
            total_marks += marks_per_question[i]

    return total_marks

# Streamlit App
st.title('Answer Key Comparison App')

# Initialize the database
conn = init_db()

# Sidebar configuration
# st.sidebar.title("Setup Questions")
# num_questions = st.sidebar.number_input("Number of Questions", min_value=1, max_value=100, step=1, value=10)

# # Input marks for each question
# marks_per_question = []
# for i in range(1, num_questions + 1):
#     marks = st.sidebar.number_input(f"Marks for Question {i}", min_value=1, max_value=10, step=1, value=5)
#     marks_per_question.append(marks)

# # Sidebar for defining OR-type question pairs
# st.sidebar.title("OR-Type Questions")
# or_question_pairs = []
# num_or_pairs = st.sidebar.number_input("Number of OR-Type Question Pairs", min_value=0, max_value=num_questions // 2, step=1, value=0)

# for i in range(num_or_pairs):
#     col1, col2 = st.sidebar.columns(2)
#     with col1:
#         q1 = st.number_input(f"OR Pair {i+1} - Question 1", min_value=1, max_value=num_questions, step=1)
#     with col2:
#         q2 = st.number_input(f"OR Pair {i+1} - Question 2", min_value=1, max_value=num_questions, step=1)
#     or_question_pairs.append((q1 - 1, q2 - 1))  # Store 0-based indices

# # Calculate total possible marks considering OR-type questions
# total_possible_marks = calculate_total_marks(marks_per_question, or_question_pairs)
# st.sidebar.write(f"Total Possible Marks: {total_possible_marks}")

# teacher_name = st.text_input("Teacher's Name", key="teacher_name_key")
# subject_name = st.text_input("Subject Name", key="subject_name_key")

# if teacher_name and subject_name:
#     st.write(f"Teacher: {teacher_name}")
#     st.write(f"Subject: {subject_name}")

# # Upload answer key PDF
# answer_key_pdf = st.file_uploader("Upload Answer Key PDF", type="pdf")

# # Upload student answer PDFs
# student_pdfs = st.file_uploader("Upload Student Answer PDFs", type="pdf", accept_multiple_files=True)

# # Process the answer key
# if answer_key_pdf:
#     answer_key_text = extract_text_from_pdf(answer_key_pdf)
#     answer_key_list = split_answers(answer_key_text)

#     if len(answer_key_list) != num_questions:
#         st.error(f"The answer key contains {len(answer_key_list)} answers, but {num_questions} were specified.")
#         st.stop()
# # Evaluate student answers
# if student_pdfs and answer_key_pdf:
#     student_answers_list = []
#     student_names = []
#     student_question_marks = []  # Stores per-question marks for each student
#     total_marks_list = []

#     for student_pdf in student_pdfs:
#         student_text = extract_text_from_pdf(student_pdf)
#         student_answers_dict = split_answers(student_text)  # Dictionary {question_num: answer}

#         # Ensure student answers are properly aligned with expected question numbers
#         formatted_student_answers = {q_num: student_answers_dict.get(q_num, "") for q_num in range(1, num_questions + 1)}

#         student_answers_list.append(formatted_student_answers)
#         student_names.append(student_pdf.name.split(".")[0])  # Extract student name from filename

#     # Process student answers and calculate marks
#     for student_answers in student_answers_list:
#         student_marks = 0
#         evaluated_or_questions = set()  # Track processed OR-type questions
#         question_marks = {}  # Stores marks per question

#         # Evaluate OR-type question pairs
#         for q1, q2 in or_question_pairs:
#             if q1 in evaluated_or_questions or q2 in evaluated_or_questions:
#                 continue  # Skip already evaluated OR question

#             evaluated_or_questions.add(q1)
#             evaluated_or_questions.add(q2)

#             # Get student's answers for OR-pair
#             student_answer_q1 = student_answers.get(q1 + 1, "")
#             student_answer_q2 = student_answers.get(q2 + 1, "")

#             # Compute similarity for both questions
#             similarity_q1 = compute_similarity(answer_key_list.get(q1 + 1, ""), student_answer_q1) if student_answer_q1.strip() else 0
#             similarity_q2 = compute_similarity(answer_key_list.get(q2 + 1, ""), student_answer_q2) if student_answer_q2.strip() else 0

#             # Calculate marks for both
#             marks_q1 = calculate_marks(similarity_q1, marks_per_question[q1])
#             marks_q2 = calculate_marks(similarity_q2, marks_per_question[q2])

#             # Award the higher marks from the OR pair
#             final_marks = max(marks_q1, marks_q2)

#             student_marks += final_marks
#             question_marks[q1 + 1] = final_marks  # Store marks for tracking

#         # Evaluate normal (non-OR) questions
#         for i in range(num_questions):
#             if any(i in pair for pair in or_question_pairs):
#                 continue  # Skip OR-type questions since they are already handled

#             student_answer = student_answers.get(i + 1, "")
#             similarity = compute_similarity(answer_key_list.get(i + 1, ""), student_answer) if student_answer.strip() else 0
#             marks = calculate_marks(similarity, marks_per_question[i])

#             student_marks += marks
#             question_marks[i + 1] = marks  # Store for tracking

#         # Store total marks and per-question marks
#         total_marks_list.append(student_marks)
#         student_question_marks.append(question_marks)

    # Display results
    # for student_name, marks, question_marks in zip(student_names, total_marks_list, student_question_marks):
    #     st.write(f"Results for {student_name}:")
    #     for q_num, q_marks in question_marks.items():
    #         st.write(f"  Question {q_num}: {q_marks} marks")
    #     st.write(f"Total marks: {marks}/{total_possible_marks}\n")

    # # Store results in the database
    # for student_name, marks in zip(student_names, total_marks_list):
    #     store_results(conn, teacher_name, class_name, subject_name, student_name, marks, total_possible_marks)
