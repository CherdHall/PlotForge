# app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import os
import json
from werkzeug.security import check_password_hash   # actually already used in model
from flask_login import login_user, logout_user, login_required, current_user

# ─── Extensions ───────────────────────────────────────────────────────────────
from extensions import db, login_manager
from models import Thread, Post, ListBoundaryOption

app = Flask(__name__)

# Config
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'DB', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-key-change-this-later-please-use-env-var'

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'          # redirect here when @login_required triggers
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# ─── User loader (required by Flask-Login) ────────────────────────────────────
from models import User #RJH- Does this need to be done here? Cleaner up top)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))   # Flask-SQLAlchemy 3.x style (or .query.get())

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def hello():
    return "Hello, PlotForge!"

# ─── Register ────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email    = request.form.get('email')
        password = request.form.get('password')

        if not all([username, email, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already taken.', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# ─── Login ───────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()  #Update last login
            db.session.commit()
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))   # or request.args.get('next')

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')

# ─── Logout ──────────────────────────────────────────────────────────────────
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('hello'))

# ─── Dashboard (protected example) ───────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# ─── New Proposal Thread Creation ────────────────────────────────────────────
@app.route('/proposals/new', methods=['GET', 'POST'])
@login_required
def new_proposal():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        max_members = request.form.get('max_members', type=int, default=15)

        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('new_proposal'))

        thread = Thread(
            title=title,
            is_proposal=True,
            leader_id=current_user.id,
            max_members=max_members,
            status='open',
            # Get boundary values
            genre_id          = request.form.get('genre_id', type=int),
            political_id      = request.form.get('political_id', type=int),
            violence_id       = request.form.get('violence_id', type=int),
            sex_id            = request.form.get('sex_id', type=int),
            style_id          = request.form.get('style_id', type=int),
            audience_id       = request.form.get('audience_id', type=int)
        )

        db.session.add(thread)
        db.session.commit()

        if description:
            post = Post(thread_id=thread.id, user_id=current_user.id, content=description)
            db.session.add(post)
            db.session.commit()

        flash('Proposal created successfully!', 'success')
        return redirect(url_for('dashboard'))

    # GET: load options for each dropdown
    genre_options     = ListBoundaryOption.query.filter_by(for_genre=True).order_by(ListBoundaryOption.sort_order).all()
    political_options = ListBoundaryOption.query.filter_by(for_political=True).order_by(ListBoundaryOption.sort_order).all()
    violence_options  = ListBoundaryOption.query.filter_by(for_violence=True).order_by(ListBoundaryOption.sort_order).all()
    sex_options       = ListBoundaryOption.query.filter_by(for_sex=True).order_by(ListBoundaryOption.sort_order).all()
    style_options     = ListBoundaryOption.query.filter_by(for_style=True).order_by(ListBoundaryOption.sort_order).all()
    audience_options  = ListBoundaryOption.query.filter_by(for_audience=True).order_by(ListBoundaryOption.sort_order).all()

    return render_template('new_proposal.html',
                           genre_options=genre_options,
                           political_options=political_options,
                           violence_options=violence_options,
                           sex_options=sex_options,
                           style_options=style_options,
                           audience_options=audience_options)

# ─── Create tables & run ─────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # safe to run multiple times
    app.run(debug=True)