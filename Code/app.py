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

        # Create public recruitment thread (proposal)
        recruitment = Thread(
            title=title,
            is_proposal=True,
            leader_id=current_user.id,
            max_members=max_members,
            status='open',
            boundary_genre=request.form.get('boundary_genre'),
            boundary_political=request.form.get('boundary_political'),
            boundary_violence=request.form.get('boundary_violence'),
            boundary_sex=request.form.get('boundary_sex'),
            boundary_style=request.form.get('boundary_style'),
            boundary_audience=request.form.get('boundary_audience')
        )
        db.session.add(recruitment)
        db.session.commit()

        # Auto-add leader to recruitment thread
        db.session.add(GroupMembership(
            user_id=current_user.id,
            thread_id=recruitment.id,
            role='leader'
        ))
        db.session.commit()

        # Create private workspace immediately
        workspace = Thread(
            title=f"Workspace: {title}",
            is_proposal=False,
            is_private_workspace=True,
            leader_id=current_user.id,
            max_members=max_members,
            status='active',
            boundary_genre=recruitment.boundary_genre,
            boundary_political=recruitment.boundary_political,
            boundary_violence=recruitment.boundary_violence,
            boundary_sex=recruitment.boundary_sex,
            boundary_style=recruitment.boundary_style,
            boundary_audience=recruitment.boundary_audience
        )
        db.session.add(workspace)
        db.session.commit()

        # Auto-add leader to workspace
        db.session.add(GroupMembership(
            user_id=current_user.id,
            thread_id=workspace.id,
            role='leader'
        ))
        db.session.commit()

        # Create default sub-threads in workspace
        social_chat = Thread(
            title="Social Chat (Not Book Related)",
            is_proposal=False,
            parent_thread_id=workspace.id,
            leader_id=current_user.id,
            status='active'
        )
        overall_arc = Thread(
            title="Overall Story Arc (Big Picture)",
            is_proposal=False,
            parent_thread_id=workspace.id,
            leader_id=current_user.id,
            status='active'
        )
        chapter_1 = Thread(
            title="Chapter 1",
            is_proposal=False,
            parent_thread_id=workspace.id,
            leader_id=current_user.id,
            status='active'
        )
        db.session.add_all([social_chat, overall_arc, chapter_1])
        db.session.commit()

        # Create default documents in workspace
        overall_doc = Document(
            thread_id=workspace.id,
            title="Overall Story Arc",
            type='story_arc',
            content='[Initial big-picture elements – edit here]',
            associated_thread_id=overall_arc.id
        )
        ch1_arc_doc = Document(
            thread_id=workspace.id,
            title="Chapter 1 Story Arc",
            type='chapter_arc',
            chapter_num=1,
            content='[Chapter 1 outline – edit here]',
            associated_thread_id=chapter_1.id
        )
        ch1_text_doc = Document(
            thread_id=workspace.id,
            title="Chapter 1 Text",
            type='chapter_text',
            chapter_num=1,
            content='[Start writing the actual chapter here]',
            associated_thread_id=chapter_1.id
        )
        db.session.add_all([overall_doc, ch1_arc_doc, ch1_text_doc])
        db.session.commit()

        # Optional: initial post in recruitment thread
        if description:
            db.session.add(Post(
                thread_id=recruitment.id,
                user_id=current_user.id,
                content=description
            ))
            db.session.commit()

        flash('Proposal created! Private workspace ready — start collaborating.', 'success')
        return redirect(url_for('workspace_dashboard', workspace_id=workspace.id))

    # GET unchanged
    # ... (genre_options etc.)

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

# CKEditor test page (minimal)
@app.route('/test-editor', methods=['GET', 'POST'])
def test_editor():
    if request.method == 'POST':
        content = request.form.get('editor_content', '')
        # Later: save to a Document row
        return f"<h1>Saved content:</h1><div>{content}</div>"
    
    return render_template('test_editor.html')

@app.route('/workspace/<int:workspace_id>')
@login_required
def workspace_dashboard(workspace_id):
    workspace = Thread.query.get_or_404(workspace_id)
    if not workspace.is_private_workspace:
        abort(404)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, thread_id=workspace.id
    ).first()
    if not membership:
        abort(403)

    sub_threads = Thread.query.filter_by(parent_thread_id=workspace.id).all()
    documents = Document.query.filter_by(thread_id=workspace.id).order_by(Document.title).all()

    return render_template('workspace_dashboard.html',
                           workspace=workspace,
                           sub_threads=sub_threads,
                           documents=documents)

@app.route('/my-workspaces')
@login_required
def my_workspaces():
    workspaces = Thread.query.join(GroupMembership).filter(
        GroupMembership.user_id == current_user.id,
        Thread.is_private_workspace == True,
        Thread.status == 'active'
    ).order_by(Thread.created_at.desc()).all()
    return render_template('my_workspaces.html', workspaces=workspaces)

# ─── Create tables & run ─────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # safe to run multiple times
    app.run(debug=True)