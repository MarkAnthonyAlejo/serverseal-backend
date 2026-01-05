#import flask into the app
from flask import Flask
from routes import main_bp

# Creates an instance of the flask app
app = Flask(__name__)

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


