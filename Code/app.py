# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from datetime import datetime
import os
import json
from werkzeug.security import check_password_hash   # actually already used in model
from flask_login import login_user, logout_user, login_required, current_user

# ─── Extensions ───────────────────────────────────────────────────────────────
from extensions import db, login_manager
from models import Thread, Post, ListBoundaryOption, GroupMembership

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
    print(f"Current user ID: {current_user.id}")
    print(f"Current user username: {current_user.username}")

    user_proposals = Thread.query.filter_by(
        leader_id=current_user.id,
        is_proposal=True,
        status='open'
    ).order_by(Thread.created_at.desc()).all()

    print(f"Found {len(user_proposals)} open proposals for this user")
    for p in user_proposals:
        print(f" - Proposal ID {p.id}: {p.title} (status: {p.status}, is_proposal: {p.is_proposal})")

    return render_template('dashboard.html',
                           proposals=user_proposals,
                           user=current_user)     # ← this line fixes the error

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

        leader_membership = GroupMembership(
        user_id=current_user.id,
        thread_id=thread.id,
        role='leader'                  # or 'member' if you prefer uniform roles
        )
        db.session.add(leader_membership)
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

#Pasted in this chunk down, check for duplicates
@app.route('/proposals')
def proposals():
    open_proposals = Thread.query.filter_by(is_proposal=True, status='open') \
                                 .order_by(Thread.created_at.desc()).all()
    return render_template('proposals.html', proposals=open_proposals)


@app.route('/threads/<int:thread_id>')
def thread_detail(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    
    if not thread.is_proposal and not current_user.is_authenticated:
        abort(403)  # private → require login later

    # Load posts ordered
    posts = thread.posts.order_by(Post.created_at).all()
    
    # Check if current user can join/finalize
    is_leader = current_user.is_authenticated and thread.leader_id == current_user.id
    is_member = current_user.is_authenticated and GroupMembership.query.filter_by(user_id=current_user.id, thread_id=thread.id).first() is not None
    
    return render_template('thread.html', 
                           thread=thread, 
                           posts=posts, 
                           is_leader=is_leader, 
                           is_member=is_member)

@app.route('/threads/<int:thread_id>/post', methods=['POST'])
@login_required
def post_in_thread(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    
    content = request.form.get('content', '').strip()
    if not content:
        flash('Post cannot be empty.', 'danger')
        return redirect(url_for('thread_detail', thread_id=thread_id))
    
    new_post = Post(
        thread_id=thread.id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(new_post)
    db.session.commit()
    
    flash('Posted!', 'success')
    return redirect(url_for('thread_detail', thread_id=thread_id))

@app.route('/threads/<int:thread_id>/add_member/<int:user_id>', methods=['POST'])
@login_required
def add_member(thread_id, user_id):
    thread = Thread.query.get_or_404(thread_id)
    if thread.leader_id != current_user.id:
        abort(403)
    
    if GroupMembership.query.filter_by(user_id=user_id, thread_id=thread.id).first():
        flash('User is already a member.', 'info')
        return redirect(url_for('thread_detail', thread_id=thread_id))
    
    if len(thread.memberships) >= thread.max_members:
        flash('Group is full.', 'danger')
        return redirect(url_for('thread_detail', thread_id=thread_id))
    
    membership = GroupMembership(user_id=user_id, thread_id=thread.id, role='member')
    db.session.add(membership)
    db.session.commit()
    
    flash('Member added to group!', 'success')
    return redirect(url_for('thread_detail', thread_id=thread_id))

@app.route('/threads/<int:thread_id>/finalize', methods=['POST'])
@login_required
def finalize_thread(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    if thread.leader_id != current_user.id:
        abort(403)
    
    if thread.status != 'open':
        flash('Already finalized.', 'info')
        return redirect(url_for('thread_detail', thread_id=thread_id))
    
    thread.status = 'closed'
    thread.is_proposal = False  # now private workspace
    
    # Stub: create initial documents (expand later)
    canon = Document(thread_id=thread.id, title='Story Canon', type='story_canon', content='Initial canon summary...')
    chapter1 = Document(thread_id=thread.id, title='Chapter 1 Text', type='chapter_text', chapter_num=1, content='Start writing here...')
    db.session.add_all([canon, chapter1])
    
    db.session.commit()
    
    flash('Proposal finalized — private workspace created!', 'success')
    return redirect(url_for('thread_detail', thread_id=thread_id))


# CKEditor test page (minimal)
@app.route('/test-editor', methods=['GET', 'POST'])
def test_editor():
    if request.method == 'POST':
        content = request.form.get('editor_content', '')
        # Later: save to a Document row
        return f"<h1>Saved content:</h1><div>{content}</div>"
    
    return render_template('test_editor.html')

# ─── Create tables & run ─────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # safe to run multiple times
    app.run(debug=True)