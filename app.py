#import flask into the app
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home(): 
    return "ServerSeal backend is running"

if __name__ == "__main__":
    app.run(debug=True)
#Check "health" check ro a route
#Example ServerSeal backend ir running 

