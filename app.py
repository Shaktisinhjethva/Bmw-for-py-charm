import json
import os
import random
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import mimetypes
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bmw-waste-mgmt-secret-2024")

# Use persistent storage path on Render, fallback to local for development
DATA_PATH = os.environ.get("DATA_PATH", os.path.dirname(__file__))
DATABASE = os.path.join(DATA_PATH, "bmw.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Upload folder for disposal videos and photos
UPLOAD_FOLDER = os.path.join(DATA_PATH, "uploads", "disposal_media")
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_IMAGE_SIZE = 50 * 1024 * 1024   # 50 MB per image

# Create upload folder if it doesn't exist
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_VIDEO_SIZE

WASTE_CATEGORIES = [
    {"id": "yellow", "name": "Yellow Bag", "desc": "Human anatomical, microbiological, soiled waste", "limit_kg": 50},
    {"id": "red", "name": "Red Bag", "desc": "Contaminated plastic, tubing, gloves, IV sets", "limit_kg": 40},
    {"id": "white", "name": "White Container", "desc": "Sharps — needles, blades, broken glass", "limit_kg": 15},
    {"id": "blue", "name": "Blue Container", "desc": "Glassware, metallic body implants", "limit_kg": 25},
    {"id": "black", "name": "Black Bag", "desc": "Discarded medicines, cytotoxic drugs", "limit_kg": 20},
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _ensure_column(cur, table, column, definition):
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            address TEXT,
            license_no TEXT,
            beds INTEGER DEFAULT 100,
            lat REAL DEFAULT 28.6289,
            lng REAL DEFAULT 77.2065,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS collectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            certification_id TEXT NOT NULL,
            certification_body TEXT DEFAULT 'CPCB / SPCB',
            is_certified INTEGER DEFAULT 1,
            cert_expiry TEXT,
            vehicle_no TEXT,
            phone TEXT,
            rating REAL DEFAULT 4.5,
            total_collections INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            lat REAL DEFAULT 28.6139,
            lng REAL DEFAULT 77.2090,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waste_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            quantity_kg REAL NOT NULL,
            logged_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        CREATE TABLE IF NOT EXISTS collection_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            collector_id INTEGER,
            status TEXT DEFAULT 'pending',
            waste_summary TEXT,
            total_kg REAL DEFAULT 0,
            priority TEXT DEFAULT 'normal',
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            assigned_at TEXT,
            picked_up_at TEXT,
            completed_at TEXT,
            vehicle_lat REAL,
            vehicle_lng REAL,
            eta_minutes INTEGER,
            response_deadline TEXT,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (collector_id) REFERENCES collectors(id)
        );

        CREATE TABLE IF NOT EXISTS pickup_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            scheduled_time TEXT NOT NULL,
            notes TEXT,
            alert_sent INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        CREATE TABLE IF NOT EXISTS collector_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector_id INTEGER NOT NULL,
            request_id INTEGER,
            message TEXT NOT NULL,
            requires_response INTEGER DEFAULT 1,
            response_deadline TEXT,
            responded_at TEXT,
            response_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (collector_id) REFERENCES collectors(id),
            FOREIGN KEY (request_id) REFERENCES collection_requests(id)
        );

        CREATE TABLE IF NOT EXISTS disposal_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector_id INTEGER NOT NULL,
            hospital_id INTEGER NOT NULL,
            request_id INTEGER,
            video_filename TEXT NOT NULL,
            photos_json TEXT,
            latitude REAL,
            longitude REAL,
            address TEXT,
            video_duration_sec INTEGER,
            file_size_mb REAL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewed_by_hospital INTEGER DEFAULT 0,
            hospital_notes TEXT,
            FOREIGN KEY (collector_id) REFERENCES collectors(id),
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (request_id) REFERENCES collection_requests(id)
        );
    """)

    _ensure_column(cur, "hospitals", "lat", "REAL DEFAULT 28.6289")
    _ensure_column(cur, "hospitals", "lng", "REAL DEFAULT 77.2065")
    _ensure_column(cur, "collectors", "is_certified", "INTEGER DEFAULT 1")
    _ensure_column(cur, "collectors", "cert_expiry", "TEXT")
    _ensure_column(cur, "waste_logs", "notes", "TEXT")
    _ensure_column(cur, "collection_requests", "response_deadline", "TEXT")

    if cur.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO hospitals (name, email, password_hash, address, license_no, beds, lat, lng) VALUES (?,?,?,?,?,?,?,?)",
            (
                "Apollo City Hospital",
                "apollo@hospital.com",
                generate_password_hash("hospital123"),
                "12 Medical District, New Delhi",
                "HOS-DL-2024-001",
                350,
                28.6289,
                77.2065,
            ),
        )
        cur.execute(
            "INSERT INTO hospitals (name, email, password_hash, address, license_no, beds, lat, lng) VALUES (?,?,?,?,?,?,?,?)",
            (
                "Max Healthcare Centre",
                "max@hospital.com",
                generate_password_hash("hospital123"),
                "45 Health Avenue, Gurugram",
                "HOS-HR-2024-002",
                220,
                28.4595,
                77.0266,
            ),
        )

    if cur.execute("SELECT COUNT(*) FROM collectors").fetchone()[0] == 0:
        collectors = [
            ("Rajesh Kumar", "rajesh@bmw.com", "CPCB-BMW-2019-4521", "DL-04-AB-7823", "9876543210", 4.9, 1240, 1),
            ("Priya Sharma", "priya@bmw.com", "CPCB-BMW-2020-8834", "HR-26-CD-4512", "9876543211", 4.8, 980, 1),
            ("Amit Patel", "amit@bmw.com", "CPCB-BMW-2018-3312", "DL-01-EF-9934", "9876543212", 4.7, 1560, 1),
            ("Sunita Devi", "sunita@bmw.com", "CPCB-BMW-2021-6678", "UP-16-GH-2234", "9876543213", 4.9, 720, 1),
            ("Vikram Singh", "vikram@bmw.com", "CPCB-BMW-2017-9901", "DL-08-IJ-5567", "9876543214", 4.6, 2100, 0),
        ]
        for name, email, cert, vehicle, phone, rating, total, certified in collectors:
            cur.execute(
                """INSERT INTO collectors
                (name, email, password_hash, certification_id, vehicle_no, phone, rating,
                 total_collections, lat, lng, is_certified, cert_expiry)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    name,
                    email,
                    generate_password_hash("collector123"),
                    cert,
                    vehicle,
                    phone,
                    rating,
                    total,
                    28.6139 + random.uniform(-0.05, 0.05),
                    77.2090 + random.uniform(-0.05, 0.05),
                    certified,
                    "2026-12-31",
                ),
            )

    hospital_id = 1
    if cur.execute("SELECT COUNT(*) FROM waste_logs").fetchone()[0] == 0:
        for day in range(30):
            date = datetime.now() - timedelta(days=29 - day)
            for cat in WASTE_CATEGORIES:
                qty = round(random.uniform(2, 18), 1)
                cur.execute(
                    "INSERT INTO waste_logs (hospital_id, category, quantity_kg, logged_at) VALUES (?,?,?,?)",
                    (hospital_id, cat["id"], qty, date.strftime("%Y-%m-%d %H:%M:%S")),
                )

    db.commit()
    db.close()


def hospital_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "hospital_id" not in session:
            flash("Please login to access the hospital dashboard.", "warning")
            return redirect(url_for("hospital_login"))
        return f(*args, **kwargs)

    return decorated


def collector_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "collector_id" not in session:
            flash("Please login to access the collector dashboard.", "warning")
            return redirect(url_for("collector_login"))
        db = get_db()
        collector = db.execute(
            "SELECT * FROM collectors WHERE id = ?", (session["collector_id"],)
        ).fetchone()
        if not collector or not collector["is_certified"]:
            session.clear()
            flash("Access denied. Only CPCB-certified collectors may use this portal.", "danger")
            return redirect(url_for("collector_login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated


def get_waste_summary(hospital_id):
    db = get_db()
    rows = db.execute(
        """SELECT category, SUM(quantity_kg) as total
        FROM waste_logs WHERE hospital_id = ? AND logged_at >= date('now', '-30 days')
        GROUP BY category""",
        (hospital_id,),
    ).fetchall()
    summary = {r["category"]: round(r["total"], 1) for r in rows}
    total = round(sum(summary.values()), 1)

    today = db.execute(
        """SELECT SUM(quantity_kg) as total FROM waste_logs
        WHERE hospital_id = ? AND date(logged_at) = date('now')""",
        (hospital_id,),
    ).fetchone()["total"] or 0

    week = db.execute(
        """SELECT SUM(quantity_kg) as total FROM waste_logs
        WHERE hospital_id = ? AND logged_at >= date('now', '-7 days')""",
        (hospital_id,),
    ).fetchone()["total"] or 0

    return {"by_category": summary, "total_month": total, "today": round(today, 1), "week": round(week, 1)}


def get_daily_trend(hospital_id, days=14):
    db = get_db()
    rows = db.execute(
        """SELECT date(logged_at) as day, SUM(quantity_kg) as total
        FROM waste_logs WHERE hospital_id = ? AND logged_at >= date('now', ?)
        GROUP BY date(logged_at) ORDER BY day""",
        (hospital_id, f"-{days} days"),
    ).fetchall()
    return [{"day": r["day"], "total": round(r["total"], 1)} for r in rows]


def get_recent_waste_logs(hospital_id, limit=15):
    db = get_db()
    rows = db.execute(
        """SELECT wl.*, c.name as category_name
        FROM waste_logs wl
        LEFT JOIN (SELECT 'yellow' as id, 'Yellow Bag' as name UNION ALL
                   SELECT 'red', 'Red Bag' UNION ALL SELECT 'white', 'White Container' UNION ALL
                   SELECT 'blue', 'Blue Container' UNION ALL SELECT 'black', 'Black Bag') c
        ON wl.category = c.id
        WHERE wl.hospital_id = ? ORDER BY wl.logged_at DESC LIMIT ?""",
        (hospital_id, limit),
    ).fetchall()
    cat_map = {c["id"]: c["name"] for c in WASTE_CATEGORIES}
    result = []
    for r in rows:
        d = dict(r)
        d["category_name"] = cat_map.get(d["category"], d["category"])
        result.append(d)
    return result


def get_alerts(hospital_id):
    summary = get_waste_summary(hospital_id)
    alerts = []
    for cat in WASTE_CATEGORIES:
        current = summary["by_category"].get(cat["id"], 0)
        pct = (current / cat["limit_kg"]) * 100 if cat["limit_kg"] else 0
        if pct >= 90:
            alerts.append({"level": "critical", "category": cat["name"], "current": current, "limit": cat["limit_kg"], "pct": round(pct)})
        elif pct >= 70:
            alerts.append({"level": "warning", "category": cat["name"], "current": current, "limit": cat["limit_kg"], "pct": round(pct)})
    return alerts


def get_pickup_alerts(hospital_id):
    db = get_db()
    now = datetime.now()
    schedules = db.execute(
        """SELECT * FROM pickup_schedules
        WHERE hospital_id = ? AND is_active = 1
        ORDER BY scheduled_time""",
        (hospital_id,),
    ).fetchall()
    alerts = []
    for s in schedules:
        sched = datetime.strptime(s["scheduled_time"], "%Y-%m-%d %H:%M:%S")
        diff = (sched - now).total_seconds() / 60
        if diff <= 0:
            level = "overdue"
            msg = f"Pickup was scheduled for {sched.strftime('%I:%M %p')} — request collection now!"
        elif diff <= 30:
            level = "urgent"
            msg = f"Pickup in {int(diff)} minutes at {sched.strftime('%I:%M %p')}"
        elif diff <= 120:
            level = "upcoming"
            msg = f"Pickup scheduled at {sched.strftime('%I:%M %p')} ({int(diff)} min)"
        else:
            level = "scheduled"
            msg = f"Pickup on {sched.strftime('%d %b, %I:%M %p')}"
        alerts.append({"id": s["id"], "level": level, "message": msg, "scheduled_time": s["scheduled_time"], "notes": s["notes"]})
    return alerts


def get_leaderboard(limit=10):
    db = get_db()
    rows = db.execute(
        """SELECT id, name, certification_id, vehicle_no, total_collections, rating, is_certified
        FROM collectors WHERE is_certified = 1
        ORDER BY total_collections DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def allowed_video_file(filename):
    """Check if the uploaded file is an allowed video format."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def allowed_image_file(filename):
    """Check if the uploaded file is an allowed image format."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def get_file_size_mb(file_obj):
    """Get file size in MB."""
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    return size / (1024 * 1024)


def save_disposal_media(video_file, photo_files, collector_id, hospital_id, latitude, longitude, address):
    """Save video and photos to disk, return paths."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        collector_folder = os.path.join(UPLOAD_FOLDER, f"collector_{collector_id}")
        Path(collector_folder).mkdir(parents=True, exist_ok=True)

        # Save video
        video_ext = video_file.filename.rsplit('.', 1)[1].lower()
        video_filename = secure_filename(f"disposal_{timestamp}.{video_ext}")
        video_path = os.path.join(collector_folder, video_filename)
        video_file.save(video_path)
        file_size_mb = get_file_size_mb(open(video_path, 'rb'))

        # Save photos
        photo_paths = []
        if photo_files:
            photos_folder = os.path.join(collector_folder, f"disposal_{timestamp}_photos")
            Path(photos_folder).mkdir(parents=True, exist_ok=True)

            for idx, photo in enumerate(photo_files):
                if photo and allowed_image_file(photo.filename):
                    photo_ext = photo.filename.rsplit('.', 1)[1].lower()
                    photo_filename = secure_filename(f"photo_{idx+1}.{photo_ext}")
                    photo_path = os.path.join(photos_folder, photo_filename)
                    photo.save(photo_path)
                    # Store relative path for easy access
                    photo_paths.append(f"disposal_{timestamp}_photos/{photo_filename}")

        return {
            'video_filename': video_filename,
            'video_path': video_path,
            'photos': photo_paths,
            'file_size_mb': file_size_mb,
            'latitude': latitude,
            'longitude': longitude,
            'address': address
        }
    except Exception as e:
        print(f"Error saving media: {e}")
        return None


def get_disposal_videos(hospital_id):
    """Get all disposal videos for a hospital."""
    db = get_db()
    rows = db.execute(
        """SELECT dv.*, c.name as collector_name, c.certification_id, c.vehicle_no, c.phone
        FROM disposal_videos dv
        JOIN collectors c ON dv.collector_id = c.id
        WHERE dv.hospital_id = ?
        ORDER BY dv.uploaded_at DESC""",
        (hospital_id,),
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        if d['photos_json']:
            d['photos'] = json.loads(d['photos_json'])
        else:
            d['photos'] = []
        result.append(d)
    return result


def notify_collector(collector_id, request_id, message, deadline_minutes=5):
    db = get_db()
    deadline = (datetime.now() + timedelta(minutes=deadline_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """INSERT INTO collector_messages (collector_id, request_id, message, requires_response, response_deadline)
        VALUES (?,?,?,?,?)""",
        (collector_id, request_id, message, 1, deadline),
    )
    db.commit()


def assign_nearest_certified_collector(hospital):
    db = get_db()
    collectors = db.execute(
        """SELECT * FROM collectors
        WHERE is_available = 1 AND is_certified = 1
        ORDER BY rating DESC"""
    ).fetchall()
    if not collectors:
        return None
    return collectors[0]


@app.route("/")
def index():
    db = get_db()
    stats = {
        "hospitals": db.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0],
        "collectors": db.execute("SELECT COUNT(*) FROM collectors WHERE is_certified = 1").fetchone()[0],
        "collections": db.execute("SELECT COALESCE(SUM(total_collections),0) FROM collectors").fetchone()[0],
        "compliance": 98.7,
    }
    leaderboard = get_leaderboard(5)
    return render_template("index.html", stats=stats, categories=WASTE_CATEGORIES, leaderboard=leaderboard)


@app.route("/collectors")
def collectors_page():
    db = get_db()
    collectors = db.execute(
        "SELECT * FROM collectors WHERE is_certified = 1 ORDER BY total_collections DESC"
    ).fetchall()
    leaderboard = get_leaderboard()
    return render_template("collectors.html", collectors=collectors, leaderboard=leaderboard)


@app.route("/hospital/login", methods=["GET", "POST"])
def hospital_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        hospital = db.execute("SELECT * FROM hospitals WHERE email = ?", (email,)).fetchone()
        if hospital and check_password_hash(hospital["password_hash"], password):
            session.clear()
            session["hospital_id"] = hospital["id"]
            session["hospital_name"] = hospital["name"]
            flash(f"Welcome back, {hospital['name']}!", "success")
            return redirect(url_for("hospital_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("hospital_login.html")


@app.route("/hospital/register", methods=["GET", "POST"])
def hospital_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        address = request.form.get("address", "").strip()
        license_no = request.form.get("license_no", "").strip()
        beds = request.form.get("beds", "100")

        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            try:
                beds_int = int(beds) if beds else 100
                db.execute(
                    """INSERT INTO hospitals (name, email, password_hash, address, license_no, beds)
                    VALUES (?,?,?,?,?,?)""",
                    (name, email, generate_password_hash(password), address, license_no, beds_int),
                )
                db.commit()
                flash("Registration successful! Please sign in.", "success")
                return redirect(url_for("hospital_login"))
            except sqlite3.IntegrityError:
                flash("An account with this email already exists.", "danger")
    return render_template("hospital_register.html")


@app.route("/hospital/logout")
def hospital_logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/hospital/dashboard")
@hospital_required
def hospital_dashboard():
    hospital_id = session["hospital_id"]
    db = get_db()
    hospital = db.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    summary = get_waste_summary(hospital_id)
    alerts = get_alerts(hospital_id)
    pickup_alerts = get_pickup_alerts(hospital_id)
    trend = get_daily_trend(hospital_id)
    recent_logs = get_recent_waste_logs(hospital_id)
    active_request = db.execute(
        """SELECT cr.*, c.name as collector_name, c.certification_id, c.vehicle_no, c.phone
        FROM collection_requests cr
        LEFT JOIN collectors c ON cr.collector_id = c.id
        WHERE cr.hospital_id = ? AND cr.status IN ('pending','assigned','in_transit','picked_up')
        ORDER BY cr.id DESC LIMIT 1""",
        (hospital_id,),
    ).fetchone()
    history = db.execute(
        """SELECT cr.*, c.name as collector_name FROM collection_requests cr
        LEFT JOIN collectors c ON cr.collector_id = c.id
        WHERE cr.hospital_id = ? ORDER BY cr.id DESC LIMIT 10""",
        (hospital_id,),
    ).fetchall()
    schedules = db.execute(
        "SELECT * FROM pickup_schedules WHERE hospital_id = ? AND is_active = 1 ORDER BY scheduled_time",
        (hospital_id,),
    ).fetchall()
    available_collectors = db.execute(
        "SELECT id, name, certification_id, vehicle_no, rating, is_available FROM collectors WHERE is_available = 1 AND is_certified = 1"
    ).fetchall()
    return render_template(
        "hospital_dashboard.html",
        hospital=dict(hospital),
        summary=summary,
        alerts=alerts,
        pickup_alerts=pickup_alerts,
        trend=trend,
        recent_logs=recent_logs,
        categories=WASTE_CATEGORIES,
        active_request=dict(active_request) if active_request else None,
        history=[dict(h) for h in history],
        schedules=[dict(s) for s in schedules],
        available_collectors=[dict(c) for c in available_collectors],
    )


@app.route("/api/waste/log", methods=["POST"])
@hospital_required
def log_waste():
    data = request.get_json() or {}
    category = data.get("category")
    quantity = float(data.get("quantity", 0))
    notes = data.get("notes", "")
    if category not in [c["id"] for c in WASTE_CATEGORIES] or quantity <= 0:
        return jsonify({"error": "Invalid data"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO waste_logs (hospital_id, category, quantity_kg, notes) VALUES (?,?,?,?)",
        (session["hospital_id"], category, quantity, notes),
    )
    db.commit()
    return jsonify({"success": True, "summary": get_waste_summary(session["hospital_id"])})


@app.route("/api/waste/delete/<int:log_id>", methods=["POST"])
@hospital_required
def delete_waste_log(log_id):
    db = get_db()
    row = db.execute(
        "SELECT id FROM waste_logs WHERE id = ? AND hospital_id = ?",
        (log_id, session["hospital_id"]),
    ).fetchone()
    if not row:
        return jsonify({"error": "Entry not found"}), 404
    db.execute("DELETE FROM waste_logs WHERE id = ?", (log_id,))
    db.commit()
    return jsonify({"success": True, "summary": get_waste_summary(session["hospital_id"])})


@app.route("/api/waste/correct/<int:log_id>", methods=["POST"])
@hospital_required
def correct_waste_log(log_id):
    data = request.get_json() or {}
    quantity = float(data.get("quantity", 0))
    category = data.get("category")
    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400
    db = get_db()
    row = db.execute(
        "SELECT * FROM waste_logs WHERE id = ? AND hospital_id = ?",
        (log_id, session["hospital_id"]),
    ).fetchone()
    if not row:
        return jsonify({"error": "Entry not found"}), 404
    if category and category in [c["id"] for c in WASTE_CATEGORIES]:
        db.execute(
            "UPDATE waste_logs SET quantity_kg = ?, category = ?, notes = COALESCE(notes,'') || ' [corrected]' WHERE id = ?",
            (quantity, category, log_id),
        )
    else:
        db.execute(
            "UPDATE waste_logs SET quantity_kg = ?, notes = COALESCE(notes,'') || ' [corrected]' WHERE id = ?",
            (quantity, log_id),
        )
    db.commit()
    return jsonify({"success": True, "summary": get_waste_summary(session["hospital_id"])})


@app.route("/api/pickup/schedule", methods=["POST"])
@hospital_required
def schedule_pickup():
    data = request.get_json() or {}
    scheduled = data.get("scheduled_time", "").strip()
    notes = data.get("notes", "")
    if not scheduled:
        return jsonify({"error": "Scheduled time required"}), 400
    try:
        datetime.strptime(scheduled, "%Y-%m-%dT%H:%M")
        formatted = datetime.strptime(scheduled, "%Y-%m-%dT%H:%M").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"error": "Invalid datetime format"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO pickup_schedules (hospital_id, scheduled_time, notes) VALUES (?,?,?)",
        (session["hospital_id"], formatted, notes),
    )
    db.commit()
    return jsonify({"success": True, "alerts": get_pickup_alerts(session["hospital_id"])})


@app.route("/api/pickup/cancel/<int:schedule_id>", methods=["POST"])
@hospital_required
def cancel_pickup(schedule_id):
    db = get_db()
    db.execute(
        "UPDATE pickup_schedules SET is_active = 0 WHERE id = ? AND hospital_id = ?",
        (schedule_id, session["hospital_id"]),
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/collection/request", methods=["POST"])
@hospital_required
def request_collection():
    hospital_id = session["hospital_id"]
    db = get_db()
    existing = db.execute(
        "SELECT id FROM collection_requests WHERE hospital_id = ? AND status IN ('pending','assigned','in_transit','picked_up')",
        (hospital_id,),
    ).fetchone()
    if existing:
        return jsonify({"error": "Active collection request already exists"}), 400

    hospital = db.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    summary = get_waste_summary(hospital_id)
    priority = "urgent" if any(a["level"] == "critical" for a in get_alerts(hospital_id)) else "normal"
    collector = assign_nearest_certified_collector(hospital)

    if collector:
        eta = random.randint(18, 45)
        deadline = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute(
            """INSERT INTO collection_requests
            (hospital_id, collector_id, status, waste_summary, total_kg, priority, assigned_at,
             vehicle_lat, vehicle_lng, eta_minutes, response_deadline)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                hospital_id,
                collector["id"],
                "assigned",
                json.dumps(summary["by_category"]),
                summary["total_month"],
                priority,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                collector["lat"],
                collector["lng"],
                eta,
                deadline,
            ),
        )
        request_id = cur.lastrowid
        notify_collector(
            collector["id"],
            request_id,
            f"New BMW pickup at {hospital['name']}! {summary['total_month']} kg waste. Accept within 5 minutes.",
            5,
        )
    else:
        db.execute(
            """INSERT INTO collection_requests (hospital_id, status, waste_summary, total_kg, priority)
            VALUES (?,?,?,?,?)""",
            (hospital_id, "pending", json.dumps(summary["by_category"]), summary["total_month"], priority),
        )

    db.commit()
    return jsonify({"success": True})


@app.route("/api/collection/track/<int:request_id>")
@hospital_required
def track_collection(request_id):
    db = get_db()
    req = db.execute(
        """SELECT cr.*, c.name as collector_name, c.certification_id, c.vehicle_no, c.phone
        FROM collection_requests cr LEFT JOIN collectors c ON cr.collector_id = c.id
        WHERE cr.id = ? AND cr.hospital_id = ?""",
        (request_id, session["hospital_id"]),
    ).fetchone()
    if not req:
        return jsonify({"error": "Not found"}), 404

    if req["status"] in ("in_transit", "assigned") and req["vehicle_lat"] and req["vehicle_lng"]:
        new_lat = req["vehicle_lat"] + random.uniform(0.0005, 0.003)
        new_lng = req["vehicle_lng"] + random.uniform(0.0005, 0.003)
        eta = max(3, (req["eta_minutes"] or 30) - random.randint(1, 4))
        db.execute(
            "UPDATE collection_requests SET vehicle_lat=?, vehicle_lng=?, eta_minutes=? WHERE id=?",
            (new_lat, new_lng, eta, request_id),
        )
        db.commit()
        req = dict(req)
        req["vehicle_lat"] = new_lat
        req["vehicle_lng"] = new_lng
        req["eta_minutes"] = eta
    else:
        req = dict(req)

    return jsonify(req)


@app.route("/api/collection/complete/<int:request_id>", methods=["POST"])
@hospital_required
def complete_collection(request_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM collection_requests WHERE id = ? AND hospital_id = ?",
        (request_id, session["hospital_id"]),
    ).fetchone()
    if not req:
        return jsonify({"error": "Not found"}), 404

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE collection_requests SET status='completed', completed_at=? WHERE id=?",
        (now, request_id),
    )
    if req["collector_id"]:
        db.execute(
            "UPDATE collectors SET is_available=1, total_collections=total_collections+1 WHERE id=?",
            (req["collector_id"],),
        )
        db.execute("DELETE FROM waste_logs WHERE hospital_id=?", (session["hospital_id"],))
    db.commit()
    return jsonify({"success": True})


# ── Collector Portal ──────────────────────────────────────────────────────────

@app.route("/collector/login", methods=["GET", "POST"])
def collector_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        collector = db.execute("SELECT * FROM collectors WHERE email = ?", (email,)).fetchone()
        if not collector:
            flash("Invalid email or password.", "danger")
        elif not collector["is_certified"]:
            flash("Your certification is not active. Contact admin for renewal.", "danger")
        elif check_password_hash(collector["password_hash"], password):
            session.clear()
            session["collector_id"] = collector["id"]
            session["collector_name"] = collector["name"]
            flash(f"Welcome, {collector['name']}!", "success")
            return redirect(url_for("collector_dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("collector_login.html")


@app.route("/collector/register", methods=["GET", "POST"])
def collector_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        certification_id = request.form.get("certification_id", "").strip()
        vehicle_no = request.form.get("vehicle_no", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or not email or not password or not certification_id:
            flash("Please fill in all required fields.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    """INSERT INTO collectors
                    (name, email, password_hash, certification_id, vehicle_no, phone, is_certified)
                    VALUES (?,?,?,?,?,?,0)""",
                    (name, email, generate_password_hash(password), certification_id, vehicle_no, phone),
                )
                db.commit()
                flash("Registration submitted! Admin will verify your certification. You can sign in once approved.", "success")
                return redirect(url_for("collector_login"))
            except sqlite3.IntegrityError:
                flash("An account with this email already exists.", "danger")
    return render_template("collector_register.html")


@app.route("/collector/logout")
def collector_logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/collector/dashboard")
@collector_required
def collector_dashboard():
    collector_id = session["collector_id"]
    db = get_db()
    collector = db.execute("SELECT * FROM collectors WHERE id = ?", (collector_id,)).fetchone()
    active_job = db.execute(
        """SELECT cr.*, h.name as hospital_name, h.address, h.lat as hospital_lat, h.lng as hospital_lng
        FROM collection_requests cr
        JOIN hospitals h ON cr.hospital_id = h.id
        WHERE cr.collector_id = ? AND cr.status IN ('assigned','in_transit','picked_up')
        ORDER BY cr.id DESC LIMIT 1""",
        (collector_id,),
    ).fetchone()
    pending_messages = db.execute(
        """SELECT cm.*, cr.status as request_status, h.name as hospital_name
        FROM collector_messages cm
        LEFT JOIN collection_requests cr ON cm.request_id = cr.id
        LEFT JOIN hospitals h ON cr.hospital_id = h.id
        WHERE cm.collector_id = ? AND cm.response_status = 'pending'
        ORDER BY cm.created_at DESC""",
        (collector_id,),
    ).fetchall()
    leaderboard = get_leaderboard()
    rank = next((i + 1 for i, c in enumerate(leaderboard) if c["id"] == collector_id), None)
    history = db.execute(
        """SELECT cr.*, h.name as hospital_name FROM collection_requests cr
        JOIN hospitals h ON cr.hospital_id = h.id
        WHERE cr.collector_id = ? AND cr.status = 'completed'
        ORDER BY cr.completed_at DESC LIMIT 10""",
        (collector_id,),
    ).fetchall()
    return render_template(
        "collector_dashboard.html",
        collector=dict(collector),
        active_job=dict(active_job) if active_job else None,
        messages=[dict(m) for m in pending_messages],
        leaderboard=leaderboard,
        rank=rank,
        history=[dict(h) for h in history],
    )


@app.route("/api/collector/accept/<int:request_id>", methods=["POST"])
@collector_required
def collector_accept(request_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM collection_requests WHERE id = ? AND collector_id = ?",
        (request_id, session["collector_id"]),
    ).fetchone()
    if not req:
        return jsonify({"error": "Job not found"}), 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    eta = random.randint(12, 35)
    db.execute(
        "UPDATE collection_requests SET status='in_transit', picked_up_at=?, eta_minutes=? WHERE id=?",
        (now, eta, request_id),
    )
    db.execute(
        "UPDATE collectors SET is_available=0 WHERE id=?",
        (session["collector_id"],),
    )
    db.execute(
        "UPDATE collector_messages SET response_status='accepted', responded_at=? WHERE request_id=? AND collector_id=?",
        (now, request_id, session["collector_id"]),
    )
    db.commit()
    return jsonify({"success": True, "eta_minutes": eta})


@app.route("/api/collector/reject/<int:request_id>", methods=["POST"])
@collector_required
def collector_reject(request_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM collection_requests WHERE id = ? AND collector_id = ?",
        (request_id, session["collector_id"]),
    ).fetchone()
    if not req:
        return jsonify({"error": "Job not found"}), 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hospital = db.execute("SELECT * FROM hospitals WHERE id = ?", (req["hospital_id"],)).fetchone()
    new_collector = db.execute(
        """SELECT * FROM collectors
        WHERE is_available = 1 AND is_certified = 1 AND id != ?
        ORDER BY rating DESC LIMIT 1""",
        (session["collector_id"],),
    ).fetchone()
    db.execute(
        "UPDATE collector_messages SET response_status='rejected', responded_at=? WHERE request_id=? AND collector_id=?",
        (now, request_id, session["collector_id"]),
    )
    if new_collector:
        deadline = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """UPDATE collection_requests SET collector_id=?, status='assigned',
            vehicle_lat=?, vehicle_lng=?, response_deadline=?, assigned_at=? WHERE id=?""",
            (new_collector["id"], new_collector["lat"], new_collector["lng"], deadline, now, request_id),
        )
        notify_collector(
            new_collector["id"],
            request_id,
            f"Reassigned BMW pickup at {hospital['name']}! Accept within 5 minutes.",
            5,
        )
    else:
        db.execute(
            "UPDATE collection_requests SET collector_id=NULL, status='pending' WHERE id=?",
            (request_id,),
        )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/collector/location", methods=["POST"])
@collector_required
def update_collector_location():
    data = request.get_json() or {}
    lat = float(data.get("lat", 0))
    lng = float(data.get("lng", 0))
    db = get_db()
    db.execute("UPDATE collectors SET lat=?, lng=? WHERE id=?", (lat, lng, session["collector_id"]))
    active = db.execute(
        "SELECT id FROM collection_requests WHERE collector_id=? AND status IN ('assigned','in_transit')",
        (session["collector_id"],),
    ).fetchone()
    if active:
        db.execute(
            "UPDATE collection_requests SET vehicle_lat=?, vehicle_lng=? WHERE id=?",
            (lat, lng, active["id"]),
        )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/collector/complete/<int:request_id>", methods=["POST"])
@collector_required
def collector_complete(request_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM collection_requests WHERE id = ? AND collector_id = ?",
        (request_id, session["collector_id"]),
    ).fetchone()
    if not req:
        return jsonify({"error": "Job not found"}), 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE collection_requests SET status='completed', completed_at=? WHERE id=?",
        (now, request_id),
    )
    db.execute(
        "UPDATE collectors SET is_available=1, total_collections=total_collections+1 WHERE id=?",
        (session["collector_id"],),
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/collector/messages")
@collector_required
def collector_messages_api():
    db = get_db()
    rows = db.execute(
        """SELECT cm.*, h.name as hospital_name FROM collector_messages cm
        LEFT JOIN collection_requests cr ON cm.request_id = cr.id
        LEFT JOIN hospitals h ON cr.hospital_id = h.id
        WHERE cm.collector_id = ? AND cm.response_status = 'pending'
        ORDER BY cm.created_at DESC""",
        (session["collector_id"],),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Disposal Video Upload Routes ──────────────────────────────────────────

@app.route("/api/disposal/upload", methods=["POST"])
@collector_required
def upload_disposal_video():
    """Upload disposal video and geotag photos."""
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['video']
    photo_files = request.files.getlist('photos[]')
    latitude = request.form.get('latitude', type=float)
    longitude = request.form.get('longitude', type=float)
    address = request.form.get('address', '').strip()
    hospital_id = request.form.get('hospital_id', type=int)
    request_id = request.form.get('request_id', type=int)

    if not video_file or video_file.filename == '':
        return jsonify({"error": "No video file selected"}), 400

    if not allowed_video_file(video_file.filename):
        return jsonify({"error": "Invalid video format. Allowed: mp4, avi, mov, mkv, webm, flv"}), 400

    if not hospital_id:
        return jsonify({"error": "Hospital ID required"}), 400

    # Check file size
    if get_file_size_mb(video_file) > MAX_VIDEO_SIZE / (1024 * 1024):
        return jsonify({"error": f"Video file too large. Max: 500MB"}), 400

    db = get_db()

    # Verify collector is assigned to this request
    if request_id:
        req = db.execute(
            "SELECT * FROM collection_requests WHERE id = ? AND collector_id = ?",
            (request_id, session["collector_id"]),
        ).fetchone()
        if not req:
            return jsonify({"error": "Invalid collection request"}), 403

    # Verify hospital exists
    hospital = db.execute(
        "SELECT * FROM hospitals WHERE id = ?", (hospital_id,)
    ).fetchone()
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    # Save media files
    media_data = save_disposal_media(
        video_file, photo_files,
        session["collector_id"], hospital_id,
        latitude, longitude, address
    )

    if not media_data:
        return jsonify({"error": "Failed to save video"}), 500

    # Save to database
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photos_json = json.dumps(media_data['photos']) if media_data['photos'] else None

    try:
        cur = db.execute(
            """INSERT INTO disposal_videos
            (collector_id, hospital_id, request_id, video_filename, photos_json,
             latitude, longitude, address, file_size_mb, status, uploaded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session["collector_id"],
                hospital_id,
                request_id,
                media_data['video_filename'],
                photos_json,
                latitude,
                longitude,
                address,
                media_data['file_size_mb'],
                'pending',
                now,
            ),
        )
        db.commit()
        video_id = cur.lastrowid

        return jsonify({
            "success": True,
            "video_id": video_id,
            "message": "Disposal video uploaded successfully and sent to hospital"
        })
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Failed to save video metadata"}), 500


@app.route("/api/disposal/videos")
@hospital_required
def get_hospital_disposal_videos():
    """Get all disposal videos for current hospital."""
    videos = get_disposal_videos(session["hospital_id"])
    return jsonify([dict(v) for v in videos])


@app.route("/api/disposal/video/<int:video_id>")
@hospital_required
def get_disposal_video_detail(video_id):
    """Get detailed info about a disposal video."""
    db = get_db()
    video = db.execute(
        """SELECT dv.*, c.name as collector_name, c.certification_id, c.vehicle_no, c.phone
        FROM disposal_videos dv
        JOIN collectors c ON dv.collector_id = c.id
        WHERE dv.id = ? AND dv.hospital_id = ?""",
        (video_id, session["hospital_id"]),
    ).fetchone()

    if not video:
        return jsonify({"error": "Video not found"}), 404

    d = dict(video)
    if d['photos_json']:
        d['photos'] = json.loads(d['photos_json'])
    else:
        d['photos'] = []

    return jsonify(d)


@app.route("/api/disposal/video/<int:video_id>/review", methods=["POST"])
@hospital_required
def review_disposal_video(video_id):
    """Hospital reviews disposal video."""
    data = request.get_json() or {}
    status = data.get('status', '').strip()  # 'approved' or 'rejected'
    notes = data.get('notes', '').strip()

    if status not in ['approved', 'rejected']:
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    video = db.execute(
        "SELECT * FROM disposal_videos WHERE id = ? AND hospital_id = ?",
        (video_id, session["hospital_id"]),
    ).fetchone()

    if not video:
        return jsonify({"error": "Video not found"}), 404

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """UPDATE disposal_videos
        SET status=?, reviewed_at=?, reviewed_by_hospital=1, hospital_notes=?
        WHERE id=?""",
        (status, now, notes, video_id),
    )
    db.commit()

    return jsonify({"success": True, "message": f"Video {status}"})


@app.route("/upload/disposal/<int:video_id>/video")
@hospital_required
def serve_disposal_video(video_id):
    """Serve disposal video file."""
    db = get_db()
    video = db.execute(
        "SELECT * FROM disposal_videos WHERE id = ? AND hospital_id = ?",
        (video_id, session["hospital_id"]),
    ).fetchone()

    if not video:
        return jsonify({"error": "Video not found"}), 404

    try:
        video_path = os.path.join(UPLOAD_FOLDER, f"collector_{video['collector_id']}", video['video_filename'])
        if not os.path.exists(video_path):
            return jsonify({"error": "Video file not found"}), 404

        return send_file(video_path, as_attachment=False, mimetype='video/mp4')
    except Exception as e:
        print(f"Error serving video: {e}")
        return jsonify({"error": "Failed to serve video"}), 500


@app.route("/upload/disposal/<int:video_id>/photo/<photo_name>")
@hospital_required
def serve_disposal_photo(video_id, photo_name):
    """Serve disposal photo."""
    db = get_db()
    video = db.execute(
        "SELECT * FROM disposal_videos WHERE id = ? AND hospital_id = ?",
        (video_id, session["hospital_id"]),
    ).fetchone()

    if not video:
        return jsonify({"error": "Video not found"}), 404

    try:
        photo_path = os.path.join(UPLOAD_FOLDER, f"collector_{video['collector_id']}", photo_name)
        if not os.path.exists(photo_path):
            return jsonify({"error": "Photo not found"}), 404

        return send_file(photo_path, as_attachment=False)
    except Exception as e:
        print(f"Error serving photo: {e}")
        return jsonify({"error": "Failed to serve photo"}), 500


@app.route("/api/leaderboard")
def leaderboard_api():
    return jsonify(get_leaderboard())


# ── Admin Portal ────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            flash("Admin access granted.", "success")
            return redirect(url_for("admin_collectors"))
        flash("Invalid admin password.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))


@app.route("/admin/collectors")
@admin_required
def admin_collectors():
    db = get_db()
    collectors = db.execute("SELECT * FROM collectors ORDER BY name").fetchall()
    return render_template("admin_collectors.html", collectors=[dict(c) for c in collectors])


@app.route("/api/admin/collector", methods=["POST"])
@admin_required
def admin_add_collector():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    cert_id = data.get("certification_id", "").strip()
    if not name or not email or not cert_id:
        return jsonify({"error": "Name, email, and certification ID required"}), 400
    db = get_db()
    try:
        db.execute(
            """INSERT INTO collectors (name, email, password_hash, certification_id, vehicle_no, phone,
            is_certified, cert_expiry) VALUES (?,?,?,?,?,?,?,?)""",
            (
                name,
                email,
                generate_password_hash(data.get("password", "collector123")),
                cert_id,
                data.get("vehicle_no", ""),
                data.get("phone", ""),
                1 if data.get("is_certified", True) else 0,
                data.get("cert_expiry", "2026-12-31"),
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400
    return jsonify({"success": True})


@app.route("/api/admin/collector/<int:collector_id>", methods=["PUT"])
@admin_required
def admin_update_collector(collector_id):
    data = request.get_json() or {}
    db = get_db()
    collector = db.execute("SELECT id FROM collectors WHERE id = ?", (collector_id,)).fetchone()
    if not collector:
        return jsonify({"error": "Not found"}), 404
    db.execute(
        """UPDATE collectors SET name=?, email=?, certification_id=?, vehicle_no=?, phone=?,
        is_certified=?, cert_expiry=? WHERE id=?""",
        (
            data.get("name"),
            data.get("email"),
            data.get("certification_id"),
            data.get("vehicle_no"),
            data.get("phone"),
            1 if data.get("is_certified") else 0,
            data.get("cert_expiry"),
            collector_id,
        ),
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/admin/collector/<int:collector_id>", methods=["DELETE"])
@admin_required
def admin_delete_collector(collector_id):
    db = get_db()
    db.execute("DELETE FROM collectors WHERE id = ?", (collector_id,))
    db.commit()
    return jsonify({"success": True})


@app.route("/about")
def about():
    return render_template("about.html", categories=WASTE_CATEGORIES)


init_db()  # Ensure DB exists when launched under gunicorn

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
