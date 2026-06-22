import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify(status="ok", version=os.environ.get("APP_VERSION", "dev"))

@app.route("/users")
def users():
    # TODO: paginate this, it loads the whole table
    return jsonify(count=1042)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
