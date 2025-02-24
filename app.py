from flask import Flask, send_from_directory, abort

import os
from flask_cors import CORS
from config import Config
from database.init_db import init_db
from routes import main_routes

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS
CORS(app)

# Initialize the database
init_db(app)

# Register routes
app.register_blueprint(main_routes)

# Define the storage path where images are stored
STORAGE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
app.config["STORAGE_FOLDER"] = STORAGE_FOLDER
app.static_folder = STORAGE_FOLDER  # Set the static folder


# Route to serve images from nested folders
@app.route("/storage/<path:filepath>")
def get_image(filepath):
    requested_path = os.path.join(app.config["STORAGE_FOLDER"], filepath)

    # Security check to prevent directory traversal attacks
    if not os.path.abspath(requested_path).startswith(app.config["STORAGE_FOLDER"]):
        return abort(403)  # Forbidden

    if os.path.exists(requested_path) and os.path.isfile(requested_path):
        return send_from_directory(app.config["STORAGE_FOLDER"], filepath)
    else:
        return abort(404)  # Not Found

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
