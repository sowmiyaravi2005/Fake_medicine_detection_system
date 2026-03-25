import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from functools import wraps

import qrcode
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "medicine.db")
QR_FOLDER = os.path.join(BASE_DIR, "static", "qrcodes")


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FMDS_SECRET", "change-this-on-deploy")
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    with closing(get_db()) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                license_number TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                manufacturing_date TEXT NOT NULL,
                medicine_name TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                batch_number TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                qr_code_data TEXT NOT NULL UNIQUE,
                qr_image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(admin_id) REFERENCES admins(id) ON DELETE CASCADE,
                UNIQUE(admin_id, batch_number)
            )
            """
        )
        columns = [row["name"] for row in db.execute("PRAGMA table_info(medicines)").fetchall()]
        if "manufacturing_date" not in columns:
            db.execute("ALTER TABLE medicines ADD COLUMN manufacturing_date TEXT")
        db.commit()


def user_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "user" or not session.get("user_id"):
            flash("Please log in as a user to continue.", "warning")
            return redirect(url_for("user_login"))
        return view(*args, **kwargs)

    return wrapped


def admin_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin" or not session.get("admin_id"):
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_current_year():
    return {"current_year": datetime.utcnow().year}


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/user/register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return redirect(url_for("user_register"))

        hashed = generate_password_hash(password)

        try:
            with closing(get_db()) as db:
                db.execute(
                    """
                    INSERT INTO users (username, email, password, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, email, hashed, datetime.utcnow().isoformat()),
                )
                db.commit()
            flash("User registered successfully. Please log in.", "success")
            return redirect(url_for("user_login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("user_register"))

    return render_template("user_register.html")


@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please provide username and password.", "warning")
            return redirect(url_for("user_login"))

        with closing(get_db()) as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("user_login"))

        session.clear()
        session["user_id"] = user["id"]
        session["user_username"] = user["username"]
        session["role"] = "user"
        flash("Welcome back!", "success")
        return redirect(url_for("scanner"))

    return render_template("user_login.html")


@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        license_number = request.form.get("license_number", "").strip()

        if not username or not password or not license_number:
            flash("All fields are required to register.", "warning")
            return redirect(url_for("admin_register"))

        hashed = generate_password_hash(password)

        try:
            with closing(get_db()) as db:
                db.execute(
                    """
                    INSERT INTO admins (username, password, license_number, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, hashed, license_number, datetime.utcnow().isoformat()),
                )
                db.commit()
            flash("Admin registered. Please log in.", "success")
            return redirect(url_for("admin_login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
            return redirect(url_for("admin_register"))

    return render_template("admin_register.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Both fields are required.", "warning")
            return redirect(url_for("admin_login"))

        with closing(get_db()) as db:
            admin = db.execute(
                "SELECT * FROM admins WHERE username = ?",
                (username,),
            ).fetchone()

        if not admin or not check_password_hash(admin["password"], password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("admin_login"))

        session.clear()
        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]
        session["role"] = "admin"
        flash("Welcome back, admin!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


@app.route("/admin/dashboard", methods=["GET", "POST"])
@admin_login_required
def admin_dashboard():
    if request.method == "POST":
        medicine_name = request.form.get("medicine_name", "").strip()
        manufacturing_date = request.form.get("manufacturing_date", "").strip()
        manufacturer = request.form.get("manufacturer", "").strip()
        batch_number = request.form.get("batch_number", "").strip()
        expiry_date = request.form.get("expiry_date", "").strip()

        if not all([medicine_name, manufacturing_date, manufacturer, batch_number, expiry_date]):
            flash("All fields are required.", "warning")
        else:
            token = str(uuid.uuid4())
            qr_filename = f"{token}.png"
            os.makedirs(QR_FOLDER, exist_ok=True)
            qr_image = qrcode.make(token)
            qr_image.save(os.path.join(QR_FOLDER, qr_filename))
            relative_path = f"qrcodes/{qr_filename}"

            try:
                with closing(get_db()) as db:
                    exists = db.execute(
                        "SELECT 1 FROM medicines WHERE admin_id = ? AND LOWER(batch_number) = LOWER(?)",
                        (session["admin_id"], batch_number),
                    ).fetchone()

                    if exists:
                        flash("This batch already exists under your account.", "danger")
                    else:
                        db.execute(
                            """
                            INSERT INTO medicines (
                                admin_id,
                                manufacturing_date,
                                medicine_name,
                                manufacturer,
                                batch_number,
                                expiry_date,
                                qr_code_data,
                                qr_image_path,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                session["admin_id"],
                                manufacturing_date,
                                medicine_name,
                                manufacturer,
                                batch_number,
                                expiry_date,
                                token,
                                relative_path,
                                datetime.utcnow().isoformat(),
                            ),
                        )
                        db.commit()
                        flash("Medicine added and QR generated.", "success")
            except sqlite3.IntegrityError:
                flash("Unable to save QR. Please try again.", "danger")

    with closing(get_db()) as db:
        medicines = db.execute(
            """
            SELECT id,
                   manufacturing_date,
                   medicine_name,
                   manufacturer,
                   batch_number,
                   expiry_date,
                   qr_image_path,
                   created_at
            FROM medicines
            WHERE admin_id = ?
            ORDER BY created_at DESC
            """,
            (session["admin_id"],),
        ).fetchall()

    return render_template(
        "admin_dashboard.html",
        medicines=medicines,
        admin_name=session.get("admin_username"),
    )


@app.route("/scanner")
@user_login_required
def scanner():
    return render_template(
        "scanner.html",
        user=session.get("user_username"),
    )


@app.route("/api/verify", methods=["POST"])
def api_verify():
    payload = request.get_json(silent=True) or {}
    qr_data = payload.get("qr_data", "").strip()

    if not qr_data:
        return jsonify(status="fake")

    with closing(get_db()) as db:
        record = db.execute(
            "SELECT medicine_name, manufacturing_date, manufacturer, batch_number, expiry_date FROM medicines WHERE qr_code_data = ?",
            (qr_data,),
        ).fetchone()

    if not record:
        return jsonify(status="fake")

    return jsonify(
        status="real",
        data={
            "name": record["medicine_name"],
            "manufacturing_date": record["manufacturing_date"],
            "manufacturer": record["manufacturer"],
            "batch_number": record["batch_number"],
            "expiry_date": record["expiry_date"],
        },
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
