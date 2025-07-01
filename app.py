from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "replace_with_a_random_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///study.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    uploader_name = db.Column(db.String(100))
    course = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    questions = Question.query.all()
    return render_template('index.html', questions=questions)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        new_q = Question(filename=filename, uploader_name=request.form['name'], course=request.form['course'])
        db.session.add(new_q)
        db.session.commit()
        flash('File uploaded successfully')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    answer = ""
    context_text = ""
    questions = Question.query.all()

    if request.method == 'POST':
        user_input = request.form['question']
        selected_files = request.form.getlist('selected_files')

        # Load content from multiple files
        for filename in selected_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                with open(file_path, 'rb') as f:
                    if filename.endswith('.txt'):
                        context_text += f"\n\n--- {filename} ---\n"
                        context_text += f.read().decode('utf-8')
                    elif filename.endswith('.pdf'):
                        import PyPDF2
                        reader = PyPDF2.PdfReader(f)
                        context_text += f"\n\n--- {filename} ---\n"
                        for page in reader.pages:
                            context_text += page.extract_text()
                    else:
                        context_text += f"\n[Unsupported file format: {filename}]\n"
            except Exception as e:
                context_text += f"\n[Error reading {filename}: {e}]\n"

        # Send to Gemini
        import google.generativeai as genai
        genai.configure(api_key="AIzaSyB13dWQeZQdBWgQW0BKcutKgJdyOJ9ZHnk")
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        try:
            prompt = f"The following documents were provided:\n{context_text}\n\nUser's question: {user_input}"
            response = model.generate_content(prompt)
            answer = response.text.strip()
        except Exception as e:
            answer = f"⚠️ Gemini API Error: {str(e)}"

    return render_template('chat.html', answer=answer, questions=questions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
        else:
            new_user = User(email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
