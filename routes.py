import os
from flask import Blueprint, request, jsonify, send_file, current_app
from models import db, Document, User, News, Page, Annotation
# from ocr import perform_ocr  # Import OCR functionality
from utils import *
from functools import wraps
from datetime import datetime

main_routes = Blueprint('main', __name__)

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
            current_user = User.verify_token(token, current_app.config['SECRET_KEY'])
            print(current_user)
            if not current_user:
                return jsonify({'message': 'Invalid token'}), 401
        except Exception:
            return jsonify({'message': 'Invalid token'}), 401

        return f(current_user, *args, **kwargs)  # Pass current_user to the route
    return decorated

@main_routes.route('/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    # Handle file upload
    file = request.files.get('file')
    file_type = request.form.get('type')
    
    # Save file and get file path
    server_base_path = os.path.dirname(os.path.realpath(__file__))
    storage_path = f"{server_base_path}/storage"
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)
    documents_path = f"{storage_path}/documents"
    if not os.path.exists(documents_path):
        os.makedirs(documents_path)
    file_path = f"{documents_path}/{file.filename}"
    file.save(file_path)
    
    # Create document
    document = Document(
        title=file.filename,
        type=file_type,
        file_path=file_path,
        user_id=current_user.id
    )
    db.session.add(document)
    db.session.commit()
    
    # Process thumbnails
    process_thumbnails(file_path, document.id)
    
    return jsonify({"status": True, "message": "File uploaded successfully", "document_id": document.id})

@main_routes.route('/register', methods=['POST'])
def register():
    data = request.json
    
    # Validate required fields
    if not all(k in data for k in ['username', 'email', 'password', 'confirm_password', 'role']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Validate role
    if data['role'] not in ['admin', 'reader', 'researcher']:
        return jsonify({'message': 'Invalid role'}), 400
    
    # Check if passwords match
    if data['password'] != data['confirm_password']:
        return jsonify({'message': 'Passwords do not match'}), 400
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already taken'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        role=data['role'],
        is_active=False  # Default to inactive
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully. Waiting for activation.'}), 201

@main_routes.route('/login', methods=['POST'])
def login():
    data = request.json
    
    # Validate required fields
    if not all(k in data for k in ['email', 'password']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Find user by email
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401
    
    # Generate access token
    token = user.generate_token(current_app.config['SECRET_KEY'])
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
    })

@main_routes.route('/doc-list', methods=['GET'])
# @token_required
def get_documents():
    documents = Document.query.all()  # Get all documents instead of filtering by user_id
    return jsonify([{
        "id": doc.id,
        "title": doc.title,
        # "type": doc.type,
        "pages_count": len(doc.pages),
        "thumbnail_url": f"/thumbnail/{doc.id}/1" if doc.thumbnails else None,
        "user_id": doc.user_id
    } for doc in documents])

@main_routes.route('/doc-detail/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    document = Document.query.filter_by(id=doc_id).first()
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    pages = []
    for page in document.pages:
        annotations = [{
            "id": ann.id,
            "target_text": ann.target_text,
            "type": ann.type,
            "content": ann.content
        } for ann in page.annotations]
        
        pages.append({
            "id": page.id,
            "text": page.text,
            "jp_translation": page.jp_translation,
            "annotations": annotations
        })
    
    return jsonify({
        "id": document.id,
        "title": document.title,
        "type": document.type,
        "pages": pages,
        "thumbnails": [{
            "page_number": thumb.page_number,
            "image_path": thumb.image_path
        } for thumb in document.thumbnails]
    })

@main_routes.route('/doc-edit/<int:doc_id>', methods=['PUT'])
@token_required
def edit_document(current_user, doc_id):
    document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    data = request.json
    if 'title' in data:
        document.title = data['title']
    
    if 'pages' in data:
        for page_data in data['pages']:
            page = Page.query.get(page_data['id'])
            if page:
                if page.document_id == document.id:
                    if 'text' in page_data:
                        page.text = page_data['text']
                    if 'jp_translation' in page_data:
                        page.jp_translation = page_data['jp_translation']
                    
                    # Handle annotations
                    if 'annotations' in page_data:
                        # Remove existing annotations not in the update
                        existing_ids = [a['id'] for a in page_data['annotations'] if 'id' in a]
                        Annotation.query.filter(
                            Annotation.page_id == page.id,
                            ~Annotation.id.in_(existing_ids) if existing_ids else True
                        ).delete(synchronize_session=False)
                        
                        # Update or create annotations
                        for ann_data in page_data['annotations']:
                            if 'id' in ann_data:
                                annotation = Annotation.query.get(ann_data['id'])
                                if annotation and annotation.page_id == page.id:
                                    annotation.target_text = ann_data.get('target_text', annotation.target_text)
                                    annotation.type = ann_data.get('type', annotation.type)
                                    annotation.content = ann_data.get('content', annotation.content)
                            else:
                                annotation = Annotation(
                                    target_text=ann_data.get('target_text'),
                                    type=ann_data.get('type'),
                                    content=ann_data.get('content'),
                                    page_id=page.id
                                )
                                db.session.add(annotation)
            else:
                # Create new page if it doesn't exist
                page = Page(
                    id=page_data['id'],
                    text=page_data.get('text'),
                    jp_translation=page_data.get('jp_translation'),
                    document_id=document.id
                )
                db.session.add(page)
                
                # Handle annotations for new page
                if 'annotations' in page_data:
                    for ann_data in page_data['annotations']:
                        annotation = Annotation(
                            target_text=ann_data.get('target_text'),
                            type=ann_data.get('type'),
                            content=ann_data.get('content'),
                            page_id=page_data['id']
                        )
                        db.session.add(annotation)
    db.session.commit()
    return jsonify({"message": "Document updated successfully"})

@main_routes.route('/doc-delete/<int:doc_id>', methods=['DELETE'])
@token_required
def delete_document(current_user, doc_id):
    document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    # Delete physical file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Delete thumbnails files
    for thumbnail in document.thumbnails:
        if os.path.exists(thumbnail.image_path):
            os.remove(thumbnail.image_path)
    
    # Delete document (will cascade delete pages, annotations, and thumbnails)
    db.session.delete(document)
    db.session.commit()
    
    return jsonify({"message": "Document deleted successfully"})

@main_routes.route('/search', methods=['GET'])
def search_documents():
    keyword = request.args.get('keyword')
    # Logic to search documents by keyword
    results = search_by_keyword(keyword)
    return jsonify(results)  # Return search results

@main_routes.route('/news', methods=['GET'])
def get_news():
    news_type = request.args.get('type')
    if news_type:
        news = News.query.filter_by(type=news_type).order_by(News.date.desc(), News.created_at.desc()).all()
    else:
        news = News.query.order_by(News.date.desc(), News.created_at.desc()).all()
    
    return jsonify([{
        'id': item.id,
        'title': item.title,
        'description': item.description,
        'isNew': item.type == 'new',
        'date': item.date.isoformat(),
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat()
    } for item in news])

@main_routes.route('/news', methods=['POST'])
@token_required
def create_news(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    data = request.json
    if not all(k in data for k in ['title', 'description', 'type', 'date']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    if data['type'] not in ['new', 'old']:
        return jsonify({'message': 'Invalid news type'}), 400
    
    try:
        # Parse the date string (expecting format: "YYYY-MM-DD")
        news_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    news = News(
        title=data['title'],
        description=data['description'],
        type=data['type'],
        date=news_date
    )
    
    db.session.add(news)
    db.session.commit()
    
    return jsonify({'message': 'News created successfully', 'id': news.id}), 201

@main_routes.route('/news/<int:news_id>', methods=['PUT'])
@token_required
def update_news(current_user, news_id):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    news = News.query.get_or_404(news_id)
    data = request.json
    
    if 'title' in data:
        news.title = data['title']
    if 'description' in data:
        news.description = data['description']
    if 'type' in data:
        if data['type'] not in ['new', 'old']:
            return jsonify({'message': 'Invalid news type'}), 400
        news.type = data['type']
    if 'date' in data:
        try:
            news_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            news.date = news_date
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    db.session.commit()
    return jsonify({'message': 'News updated successfully'})

@main_routes.route('/news/<int:news_id>', methods=['DELETE'])
@token_required
def delete_news(current_user, news_id):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    news = News.query.get_or_404(news_id)
    db.session.delete(news)
    db.session.commit()
    
    return jsonify({'message': 'News deleted successfully'})
