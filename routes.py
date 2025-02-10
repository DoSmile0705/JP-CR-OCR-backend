import os
from flask import Blueprint, request, jsonify, send_file
from models import db, Document
# from ocr import perform_ocr  # Import OCR functionality
from utils import *

main_routes = Blueprint('main', __name__)

@main_routes.route('/upload', methods=['POST'])
def upload_file():
    # Handle file upload
    file = request.files.get('file')
    file_type = request.form.get('type')
    server_base_path = os.path.dirname(os.path.realpath(__file__))
    storage_path = f"{server_base_path}/storage"
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)
    documents_path = f"{storage_path}/documents"
    if not os.path.exists(documents_path):
        os.makedirs(documents_path)
    file_path = f"{documents_path}/{file.filename}"
    file.save(file_path)
    
    # Extract text from file
    text = extract_text(file_type, file_path)
    
    # Save to document table
    document = Document(title=file.filename, type=file_type, file_path=file_path, text=text)
    db.session.add(document)
    db.session.commit()
    
    # Process thumbnails
    process_thumbnails(file_path, document.id)
    
    return jsonify({"status": True, "message": "File uploaded successfully", "document_id": document.id})

@main_routes.route('/doc-list', methods=['GET'])
def get_documents():
    documents = Document.query.all()
    return jsonify([{"id": doc.id, "title": doc.title, "type": doc.type, "thumbnail_url": f"/thumbnail/{doc.title}/1.jpg"} for doc in documents])

@main_routes.route('/doc-detail', methods=['GET'])
def view_document():
    doc_id = request.args.get('id')
    document = Document.query.get(doc_id)
    if document:
        return jsonify({"id": document.id, "title": document.title, "type": document.type, "text": document.text})
    return jsonify({"error": "Document not found"}), 404

@main_routes.route('/doc-edit', methods=['POST'])
def edit_document():
    data = request.json
    doc_id = data['id']
    text = data['text']
    document = Document.query.get(doc_id)
    if document:
        document.text = text
        db.session.commit()
        return jsonify({"status": True, "message": "Document edited successfully"})
    return jsonify({"error": "Document not found"}), 404

@main_routes.route('/doc-save', methods=['PUT'])
def save_document():
    data = request.json
    document = Document.query.get(data['id'])
    if document:
        document.title = data['title']
        document.text = data['text']
        db.session.commit()
        return jsonify({"status": True, "message": "Document saved successfully"})
    return jsonify({"error": "Document not found"}), 404

@main_routes.route('/doc-delete', methods=['DELETE'])
def delete_document():
    doc_id = request.args.get('id')
    document = Document.query.get(doc_id)
    if document:
        db.session.delete(document)
        db.session.commit()
        return jsonify({"status": True, "message": "Document deleted successfully"})
    return jsonify({"error": "Document not found"}), 404

@main_routes.route('/search-keyword', methods=['GET'])
def search_documents():
    keyword = request.args.get('keyword')
    # Logic to search documents by keyword
    results = search_by_keyword(keyword)
    return jsonify(results)  # Return search results
