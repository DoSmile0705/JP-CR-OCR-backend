import os
from flask import current_app
from models import db, Document, Thumbnail
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract  # Ensure you have Tesseract installed and configured
import fitz  # PyMuPDF for PDF handling

# Define the storage path
STORAGE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'storage')

def extract_text(doc_type, file_path):
    """Extract text from the document based on its type."""
    if int(doc_type) in [1, 2]:
        return read_from_file(file_path)
    else:
        return OCR_from_file(file_path)

def read_from_file(file_path):
    """Read text from a supported document file and return an array of text."""
    # Implement logic to read text from .docx or .pdf files
    # For example, using PyPDF2 for PDFs or python-docx for DOCX
    text_pages = []
    if file_path.endswith('.pdf'):
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text("text")
                # Fix possible vertical text issues
                text = text.replace("\n", "")  # Remove unnecessary line breaks
                text_pages.append(text)
    elif file_path.endswith('.docx'):
        from docx import Document
        doc = Document(file_path)
        for para in doc.paragraphs:
            text_pages.append(para.text)
    return text_pages

def OCR_from_file(file_path):
    """Perform OCR on the document file to extract text."""
    # Use Tesseract to perform OCR on the document
    text = ""
    # Convert the document to images first if it's not already an image
    if file_path.endswith('.pdf'):
        from pdf2image import convert_from_path
        images = convert_from_path(file_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
    else:
        # If it's an image file, directly apply OCR
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
    return text.strip()

def process_thumbnails(file_path, document_id):
    """Process the document file to create thumbnails."""
    # Get the file name without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    thumbnail_dir = os.path.join(STORAGE_PATH, 'thumbnails', file_name)
    os.makedirs(thumbnail_dir, exist_ok=True)

    # Convert the document to images
    if file_path.endswith('.pdf'):
        from pdf2image import convert_from_path
        POPPLER_PATH = r"C:\poppler-24.08.0\Library\bin"
        images = convert_from_path(file_path, dpi=200, poppler_path=POPPLER_PATH)
        for page_number, image in enumerate(images, start=1):
            thumbnail_path = os.path.join(thumbnail_dir, f"{page_number}.jpg")
            image.save(thumbnail_path, 'JPEG', quality=10)
            # Create a thumbnail record in the database
            thumbnail = Thumbnail(document_id=document_id, page_number=page_number, image_path=thumbnail_path)
            db.session.add(thumbnail)
    else:
        # Handle other file types if necessary
        pass

    db.session.commit()  # Commit all thumbnail records to the database
