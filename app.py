import os
import sys
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory, redirect
from flask_cors import CORS
from extensions import limiter
from routes import main_bp

load_dotenv()

# ---------------------------------------------------------------------------
# Startup env-var checks — fail loudly rather than silently misbehave in prod
# ---------------------------------------------------------------------------
_jwt_secret = os.environ.get('JWT_SECRET', '')
if not _jwt_secret or _jwt_secret == 'dev-secret-change-in-production':
    if os.environ.get('FLASK_ENV') == 'production':
        print('ERROR: JWT_SECRET is not set or is the default value. Refusing to start in production.', file=sys.stderr)
        sys.exit(1)
    else:
        print('WARNING: JWT_SECRET is not set. Using insecure default — set it before going to production.', file=sys.stderr)

if not os.environ.get('DATABASE_URL') and not os.environ.get('DB_HOST'):
    print('WARNING: Neither DATABASE_URL nor DB_HOST is set. Database connections will fail.', file=sys.stderr)

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

# Create the local upload folder (only needed when not using S3)
if not os.environ.get('AWS_S3_BUCKET') and not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Attach rate limiter
limiter.init_app(app)

# Connect the routes from routes.py to this app
app.register_blueprint(main_bp)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve a stored file.

    - S3 configured: redirect the browser to a short-lived presigned URL.
    - Local storage: serve the file directly from disk.
    """
    import storage
    url = storage.presigned_url(f"uploads/{filename}")
    if url:
        return redirect(url)
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/")
def home():
    return "ServerSeal backend is running"


if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
