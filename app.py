#import flask into the app
from flask import Flask

# Creates an instance of the flask app
app = Flask(__name__)

# Define a route for the root URL '/' 
# and link it to the function below
@app.route("/")
def home(): 
    return "ServerSeal backend is running"

#checks if the file is run directly,
# then start the flask development server
if __name__ == "__main__":
    app.run(debug=True)


