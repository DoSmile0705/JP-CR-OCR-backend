from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    target_text = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(50), nullable=True) 
    content = db.Column(db.Text, nullable=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.Text, nullable=True)
    jp_translation = db.Column(db.Text, nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    
    # Relationship to annotations
    annotations = db.relationship('Annotation', backref='page', lazy=True, cascade="all, delete-orphan")

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Integer, nullable=True)
    file_path = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Add relationship to User
    user = db.relationship('User', backref='documents', lazy=True)

    # Relationship to Pages
    pages = db.relationship('Page', backref='document', lazy=True, cascade="all, delete-orphan")

    # Relationship to Thumbnails
    thumbnails = db.relationship('Thumbnail', backref='document', lazy=True, cascade="all, delete-orphan")


class Thumbnail(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Unique ID for each thumbnail
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # Page number associated with the thumbnail
    image_path = db.Column(db.String(200), nullable=False)  # Path to the thumbnail image

    # Ensure a document can't have duplicate thumbnails for the same page
    __table_args__ = (db.UniqueConstraint('document_id', 'page_number', name='unique_thumbnail_per_page'),)


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)  # For HTML content
    type = db.Column(db.String(10), nullable=False)  # 'new' or 'old'
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='reader')  # Possible values: admin, reader, researcher
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=False, nullable=False)  # Changed default to False

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.is_active:
            return False
        return check_password_hash(self.password_hash, password)

    def generate_token(self, secret_key):
        if not self.is_active:
            return None
        token = jwt.encode({
            'email': self.email,
            'exp': datetime.utcnow() + timedelta(days=1)  # Token expires in 1 day
        }, secret_key, algorithm='HS256')
        return token

    @staticmethod
    def verify_token(token, secret_key):
        try:
            data = jwt.decode(token, secret_key, algorithms=['HS256'])
            user = User.query.filter_by(email=data['email']).first()
            if user and user.is_active:
                return user
            return None
        except:
            return None

    def disable_user(self):
        if self.role != 'admin':
            self.is_active = False
            db.session.commit()

    def enable_user(self):
        if self.role != 'admin':
            self.is_active = True 
            db.session.commit()