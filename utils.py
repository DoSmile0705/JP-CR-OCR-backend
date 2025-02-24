import os
from flask import current_app
from models import db, Document, Thumbnail
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract  # Ensure you have Tesseract installed and configured
import fitz  # PyMuPDF for PDF handling

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
    text_pages = []
    # Convert the document to images first if it's not already an image
    if file_path.endswith('.pdf'):
        from pdf2image import convert_from_path
        POPPLER_PATH = r"C:\poppler-24.08.0\Library\bin"
        images = convert_from_path(file_path, dpi=200, poppler_path=POPPLER_PATH)
        for image in images:
            text_pages.append(pytesseract.image_to_string(image, lang='jpn_vert+chi_tra_vert'))
    else:
        # If it's an image file, directly apply OCR
        image = Image.open(file_path)
        text_pages.append(pytesseract.image_to_string(image, lang='jpn_vert+chi_tra_vert'))
    return text_pages
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
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
        # Handle image files
        from PIL import Image
        image = Image.open(file_path)
        thumbnail_path = os.path.join(thumbnail_dir, "1.jpg")
        # Convert RGBA to RGB before saving as JPEG
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        image.save(thumbnail_path, 'JPEG', quality=10)
        # Create a thumbnail record in the database
        thumbnail = Thumbnail(document_id=document_id, page_number=1, image_path=thumbnail_path)
        db.session.add(thumbnail)

    db.session.commit()  # Commit all thumbnail records to the database

def search_by_keyword(keyword):
    documents = Document.query.all()
    search_results = []
    
    for document in documents:
        matches = {
            "title_matches": [],
            "page_matches": []
        }
        
        # Search in document title
        if keyword.lower() in document.title.lower():
            matches["title_matches"].append({
                "text": document.title,
                "context": document.title
            })
        
        # Search in pages
        for page in document.pages:
            page_matches = []
                    
            # Search in page text
            if page.text and keyword.lower() in page.text.lower():
                start_idx = page.text.lower().find(keyword.lower())
                context_start = max(0, start_idx - 50)
                context_end = min(len(page.text), start_idx + len(keyword) + 50)
                context = page.text[context_start:context_end]
                page_matches.append({
                    "type": "text",
                    "text": keyword,
                    "context": f"...{context}..."
                })
            
            # Search in Japanese translation
            if page.jp_translation and keyword.lower() in page.jp_translation.lower():
                start_idx = page.jp_translation.lower().find(keyword.lower())
                context_start = max(0, start_idx - 50)
                context_end = min(len(page.jp_translation), start_idx + len(keyword) + 50)
                context = page.jp_translation[context_start:context_end]
                page_matches.append({
                    "type": "translation",
                    "text": keyword,
                    "context": f"...{context}..."
                })
            
            # Search in annotations
            for i, annotation in enumerate(page.annotations, 1):
                # Search in annotation name
                if annotation.target_text and keyword.lower() in annotation.target_text.lower():
                    page_matches.append({
                        "type": "annotation_name",
                        "text": annotation.target_text,
                        "context": f"#{i}: {annotation.target_text}"
                    })
                
                # Search in annotation type
                if annotation.type and keyword.lower() in annotation.type.lower():
                    page_matches.append({
                        "type": "annotation_type", 
                        "text": annotation.type,
                        "context": f"#{i}: {annotation.type}"
                    })
                
                # Search in annotation content
                if annotation.content and keyword.lower() in annotation.content.lower():
                    page_matches.append({
                        "type": "annotation_content",
                        "text": keyword,
                        "context": f"#{i}: {annotation.content}"
                    })
            if page_matches:
                matches["page_matches"].append({
                    "page_number": page.id,
                    "matches": page_matches,
                    "match_count": len(page_matches)
                })
        
        # Add document to results if any matches found
        if matches["title_matches"] or matches["page_matches"]:
            total_matches = len(matches["title_matches"]) + sum(page["match_count"] for page in matches["page_matches"])
            search_results.append({
                "id": document.id,
                "document_title": document.title,
                "matches": matches,
                "total_matches": total_matches
            })
    
    return search_results