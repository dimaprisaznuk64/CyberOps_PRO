import os

from flask import Flask, abort, make_response, redirect, render_template_string, request, session

app = Flask(__name__)
app.config.update(
    SECRET_KEY="hardcoded-secret-key",
    SESSION_COOKIE_HTTPONLY=False,
    SESSION_COOKIE_SAMESITE=None,
)
app.debug = True

USERNAME = "admin"
PASSWORD = "admin"

INDEX_HTML = """
<!doctype html><title>CiberOps Web Lab</title>
<h1>CiberOps Web Lab</h1>
<ul>
  <li><a href="/login">/login</a></li>
  <li><a href="/search?q=test">/search?q=...</a></li>
  <li><a href="/files?name=readme.txt">/files?name=...</a></li>
  <li><a href="/redirect?url=https://example.com">/redirect?url=...</a></li>
  <li><a href="/admin">/admin</a></li>
</ul>
"""


@app.after_request
def no_headers(response):
    return response


@app.get("/")
def index():
    return INDEX_HTML


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == USERNAME and request.form.get("password") == PASSWORD:
            session["user"] = USERNAME
            resp = make_response(redirect("/admin"))
            resp.set_cookie("role", "user")
            return resp
        return "wrong credentials", 401
    return render_template_string(
        """<form method="post">
Username: <input name="username"><br>
Password: <input name="password" type="password"><br><button>Login</button></form>"""
    )


@app.get("/admin")
def admin():
    if session.get("user") != USERNAME:
        abort(401)
    return "Admin panel: secrets file? try /files?name=admin.secret"


@app.get("/search")
def search():
    q = request.args.get("q", "")
    return render_template_string(f"<p>Results for: {q}</p><p>Nothing found.</p>")


@app.get("/redirect")
def redirect_to():
    url = request.args.get("url", "/")
    return redirect(url)


@app.get("/files")
def files():
    name = request.args.get("name", "readme.txt")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")
    path = os.path.join(base, name)
    if not os.path.exists(path):
        abort(404)
    with open(path, "rb") as fh:
        return fh.read()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)