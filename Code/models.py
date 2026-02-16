# models.py
# This file defines all database tables (models) for PlotForge using Flask-SQLAlchemy.
# Each class represents one table. Relationships allow easy querying 
# (e.g. thread.posts, user.groups, thread.documents).

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json  # used for JSON columns (boundaries, revision history)
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db   # ← Changed to import from extensions.py (breaks circular reference)

###################################################
################# Data Tables #####################
###################################################

# ────────────────────────────────────────────────
# USER MODEL
# Stores user accounts. Core for authentication, ownership, and contribution tracking.
# ────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    owned_threads = db.relationship('Thread', back_populates='leader', foreign_keys='Thread.leader_id')
    memberships = db.relationship('GroupMembership', back_populates='user', cascade='all, delete-orphan')

# ─── Flask-Login helper methods ──────────────────────────────────────
    def set_password(self, password: str):
        """Create hashed password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)
    # Flask-Login already gets is_active, is_authenticated, etc. from UserMixin
    # You can override them later if needed (e.g. banned users)
    def __repr__(self):
        return f'<User {self.username}>'

# ────────────────────────────────────────────────
# ASSOCIATION TABLE: GroupMembership
# Many-to-many link between User and Thread (group/workspace).
# Includes role ('leader' / 'member') and join timestamp.
# ────────────────────────────────────────────────
class GroupMembership(db.Model):
    __tablename__ = 'group_memberships'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'), nullable=False)

    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='memberships')
    thread = db.relationship('Thread', back_populates='memberships')

    __table_args__ = (db.UniqueConstraint('user_id', 'thread_id', name='unique_membership'),)

    def __repr__(self):
        return f'<Membership user={self.user_id} thread={self.thread_id} role={self.role}>'

# ────────────────────────────────────────────────
# THREAD MODEL
# Represents public proposal threads (recruitment) and private group workspaces.
# ────────────────────────────────────────────────
class Thread(db.Model):
    __tablename__ = 'threads'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    is_proposal = db.Column(db.Boolean, default=True)
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='open')
    max_members = db.Column(db.Integer, default=15)
    genre_id          = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)
    political_id      = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)
    violence_id       = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)
    sex_id            = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)
    style_id          = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)
    audience_id       = db.Column(db.Integer, db.ForeignKey('list_boundary_options.id'), nullable=True)

    leader = db.relationship('User', back_populates='owned_threads', foreign_keys=[leader_id])
    memberships = db.relationship('GroupMembership', back_populates='thread', cascade='all, delete-orphan')
    posts = db.relationship('Post', back_populates='thread', cascade='all, delete-orphan')
    documents = db.relationship('Document', back_populates='thread', cascade='all, delete-orphan')
    genre     = db.relationship('ListBoundaryOption', foreign_keys=[genre_id])
    political = db.relationship('ListBoundaryOption', foreign_keys=[political_id])
    violence  = db.relationship('ListBoundaryOption', foreign_keys=[violence_id])
    sex       = db.relationship('ListBoundaryOption', foreign_keys=[sex_id])
    style     = db.relationship('ListBoundaryOption', foreign_keys=[style_id])
    audience  = db.relationship('ListBoundaryOption', foreign_keys=[audience_id])

    def get_boundaries(self):
        try:
            return json.loads(self.boundaries)
        except:
            return {}

    def set_boundaries(self, data_dict):
        self.boundaries = json.dumps(data_dict)

    def __repr__(self):
        return f'<Thread {self.title} is_proposal={self.is_proposal}>'

# ────────────────────────────────────────────────
# POST MODEL
# Replies / comments inside any thread (public or private).
# ────────────────────────────────────────────────
class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

    thread = db.relationship('Thread', back_populates='posts')
    author = db.relationship('User')

    def __repr__(self):
        return f'<Post by user {self.user_id} in thread {self.thread_id}>'

# ────────────────────────────────────────────────
# DOCUMENT MODEL
# Editable rich-text documents: Story Canon, Chapter Text, Chapter Canon, custom docs.
# Each is associated with a thread (group/workspace).
# ────────────────────────────────────────────────
class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default='')
    type = db.Column(db.String(50), default='custom')
    chapter_num = db.Column(db.Integer, nullable=True)
    revision_history = db.Column(db.Text, default='[]')
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    thread = db.relationship('Thread', back_populates='documents')

    def get_revision_history(self):
        try:
            return json.loads(self.revision_history)
        except:
            return []

    def add_revision(self, user_id, summary):
        history = self.get_revision_history()
        history.append({
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'summary': summary[:200]
        })
        self.revision_history = json.dumps(history)

    def __repr__(self):
        return f'<Document {self.title} type={self.type} thread={self.thread_id}>'

###################################################
################# List Tables #####################
###################################################

# ────────────────────────────────────────────────
# Boundary Options (one table, boolean flags per category)
# ────────────────────────────────────────────────
class ListBoundaryOption(db.Model):
    __tablename__ = 'list_boundary_options'

    id = db.Column(db.Integer, primary_key=True)
    option_text = db.Column(db.String(100), nullable=False, unique=True)
    for_genre     = db.Column(db.Boolean, default=False)
    for_political = db.Column(db.Boolean, default=False)
    for_violence  = db.Column(db.Boolean, default=False)
    for_sex       = db.Column(db.Boolean, default=False)
    for_style     = db.Column(db.Boolean, default=False)
    for_audience  = db.Column(db.Boolean, default=False)
    sort_order    = db.Column(db.Integer, default=0)   # controls dropdown order

    def __repr__(self):
        return f'<BoundaryOption {self.option_text}>'

# ────────────────────────────────────────────────
# Future models
# - AiCallLog
# - Vote
# - AttributionLog
# ────────────────────────────────────────────────