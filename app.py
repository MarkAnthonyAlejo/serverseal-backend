# import flask into the app
import os
from werkzeug.utils import secure_filename
from flask import Flask, jsonify
from flask_cors import CORS
from routes import main_bp

# Creates an instance of the flask app
app = Flask(__name__)
CORS(app)

# Define where files will be stored and what types are allowed
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configure the app to use that folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
# This line fixes 413 error, fixes file sizes
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024

# Create the physical folder on your computer if it doesn't exist yet
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Connect the routes from routes.py to this app
app.register_blueprint(main_bp)


@app.route("/")
def home():
    return "ServerSeal backend is running"


if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
