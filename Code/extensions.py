# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()  # unbound here — will be initialized later
login_manager = LoginManager()