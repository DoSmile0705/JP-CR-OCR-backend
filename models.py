from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Integer, nullable=False)
    text = db.Column(db.JSON, nullable=False)  # Store text as a JSON array, each index = a page
    file_path = db.Column(db.String(200), nullable=False)

    # Relationship to Thumbnails
    thumbnails = db.relationship('Thumbnail', backref='document', lazy=True, cascade="all, delete-orphan")


class Thumbnail(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Unique ID for each thumbnail
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # Page number associated with the thumbnail
    image_path = db.Column(db.String(200), nullable=False)  # Path to the thumbnail image

    # Ensure a document can't have duplicate thumbnails for the same page
    __table_args__ = (db.UniqueConstraint('document_id', 'page_number', name='unique_thumbnail_per_page'),)

