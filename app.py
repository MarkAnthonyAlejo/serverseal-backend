#import flask into the app
import os
from werkzeug.utils import secure_filename
from flask import Flask
from routes import main_bp

# Define where files will be stored and what types are allowed 
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Creates an instance of the flask app
app = Flask(__name__)

# Configure the app to use that folder 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the physical folder on your computer if it doesn't exist yet
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Connect the routes from routes.py to this app
app.register_blueprint(main_bp)

# and link it to the function below
@app.route("/")
def home(): 
    return "ServerSeal backend is running"

#checks if the file is run directly,
# then start the flask development server
if __name__ == "__main__":
    app.run(debug=True, port=5001)


