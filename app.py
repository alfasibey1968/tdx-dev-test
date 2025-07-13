import os, json, uuid, qrcode
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    send_from_directory, flash, send_file
)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators
import phonenumbers

app = Flask(__name__, static_folder='static')
app.secret_key = 'changeme'
ADMIN_PASSWORD = "changeme"
CONFIG_PATH = "config/bus_config.json"
PASSENGER_DB = "data/passengers.json"
LOYALTY_LOG  = "data/loyalty_logs.csv"
STAFF_DB     = "data/staff.json"
MOVIE_CATS   = ['action', 'african', 'romance', 'comedy']
MVIDEO_CATS  = ['afrobeat_videos', 'gospel', 'rnb', 'reggae', 'rap']
DOC_CATS     = ['doc1', 'doc2', 'doc3']
MUSIC_CATS   = ['afrobeat', 'reggae', 'hiphop', 'rnb', 'gospel']

os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('static/qr', exist_ok=True)

def get_bus_info():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"registration":"???", "route":"???", "estimated_arrival":"???"}

def save_passenger(data):
    db = {}
    if os.path.exists(PASSENGER_DB):
        with open(PASSENGER_DB) as f: db = json.load(f)
    db[data['id']] = data
    with open(PASSENGER_DB, "w") as f: json.dump(db, f, indent=2)

def get_passenger(pid):
    if os.path.exists(PASSENGER_DB):
        with open(PASSENGER_DB) as f:
            db = json.load(f)
            return db.get(pid)
    return None

def all_passengers():
    if os.path.exists(PASSENGER_DB):
        with open(PASSENGER_DB) as f: return json.load(f)
    return {}

def log_loyalty(pid, seat):
    with open(LOYALTY_LOG, "a") as f:
        f.write(f"{pid},{seat},{get_bus_info()['registration']}\n")

def is_valid_phone(phone):
    p = ''.join(phone.strip().split())
    if p.startswith("+"):
        try:
            z = phonenumbers.parse(p, None)
            return phonenumbers.is_valid_number(z)
        except: return False
    if len(p)==10 and p.isdigit():
        try:
            z = phonenumbers.parse("+233"+p[1:], "GH")
            return phonenumbers.is_valid_number(z)
        except: return False
    return False

def gen_passenger_qr(pid):
    if not os.path.exists(f"static/qr/{pid}.png"):
        img = qrcode.make(f"TDX:{pid}")
        img.save(f"static/qr/{pid}.png")

def list_games():
    gamesdir = os.path.join(app.root_path, 'templates', 'games')
    return [f[:-5] for f in os.listdir(gamesdir) if f.endswith('.html')]

def all_buses():
    if os.path.exists(STAFF_DB):
        try:
            with open(STAFF_DB) as f:
                db = json.load(f)
                if isinstance(db, dict):
                    return db
        except Exception:
            pass
    return {}

def save_bus_info(reg, staff_entry):
    db = all_buses()
    db[reg] = dict(staff_entry)
    with open(STAFF_DB, "w") as f:
        json.dump(db, f, indent=2)

def get_bus_info_by_reg(reg):
    db = all_buses()
    s = db.get(reg, {})
    if not isinstance(s, dict):
        return {}
    return s

def get_banner_message():
    try:
        with open("data/banner_message.txt") as f:
            return f.read().strip()
    except Exception:
        return " Welcome to TDX Bus Entertainment! Enjoy, relax, and stay golden. "

class GuestLoginForm(FlaskForm):
    seat = StringField('Seat', [validators.InputRequired()])
    credential = StringField('Phone or Loyalty ID', [validators.InputRequired()])

class RegisterForm(FlaskForm):
    name  = StringField('Name', [validators.InputRequired()])
    phone = StringField('Phone', [validators.InputRequired()])
    email = StringField('Email', [validators.Optional(), validators.Email()])

class AdminLoginForm(FlaskForm):
    password = PasswordField('Password', [validators.DataRequired()])

class StaffForm(FlaskForm):
    reg      = StringField('Bus Reg', [validators.InputRequired()])
    driver   = StringField('Driver Name', [validators.InputRequired()])
    dphone   = StringField('Driver Phone', [validators.InputRequired()])
    assistant= StringField('Assistant Name', [validators.Optional()])
    aphone   = StringField('Assistant Phone', [validators.Optional()])
    owner    = StringField('Owner Name',    [validators.Optional()])
    ophone   = StringField('Owner Phone', [validators.Optional()])

@app.route("/", methods=["GET", "POST"])
def index():
    form = GuestLoginForm()
    error = None
    if form.validate_on_submit():
        seat = form.seat.data.strip()
        cred = form.credential.data.strip()
        passengers = all_passengers()
        found_loyalty = next((pid for pid,p in passengers.items()
                             if p.get('phone')==cred or pid==cred or p.get('email','')==cred), None)
        if found_loyalty:
            session["seat"] = seat
            session["pid"] = found_loyalty
            session["phone"] = passengers[found_loyalty]["phone"]
            log_loyalty(found_loyalty, seat)
            return redirect(url_for("dashboard"))
        elif is_valid_phone(cred):
            session["seat"] = seat
            session["phone"] = cred
            session.pop("pid", None)
            return redirect(url_for("dashboard"))
        else:
            error = "Not registered for loyalty/rewards. Please check your ID/phone or join."
    bus = get_bus_info()
    return render_template("index.html", form=form, error=error, bus=bus)

@app.route("/register", methods=["GET","POST"])
def register():
    form = RegisterForm()
    error = None
    if form.validate_on_submit():
        name = form.name.data.strip()
        phone = form.phone.data.strip()
        email = form.email.data.strip()
        if not is_valid_phone(phone):
            error = "Enter a valid phone."
        else:
            pid = str(uuid.uuid4())
            save_passenger({
                "id": pid,
                "name": name,
                "phone": phone,
                "email": email or "",
                "points": 0
            })
            gen_passenger_qr(pid)
            return render_template("register_done.html", pid=pid, passenger={"name": name, "phone": phone, "email": email})
    return render_template("register.html", form=form, error=error, bus=get_bus_info())

@app.route("/dashboard")
def dashboard():
    if 'seat' not in session or 'phone' not in session:
        return redirect(url_for("index"))
    bus = get_bus_info()
    games = list_games()
    p = get_passenger(session.get('pid')) if session.get('pid') else None
    return render_template("dashboard.html", seat=session['seat'], bus=bus, games=games, passenger=p)

@app.route("/loyalty/<pid>")
def loyalty_profile(pid):
    p = get_passenger(pid)
    if not p: return "Passenger not found"
    rides = 0
    if os.path.exists(LOYALTY_LOG):
        with open(LOYALTY_LOG) as f:
            rides = sum(1 for line in f if line.startswith(pid+','))
    return render_template("loyalty_profile.html", p=p, pid=pid, rides=rides)

@app.route("/games/<gamename>")
def games_view(gamename):
    bus = get_bus_info()
    return render_template(f"games/{gamename}.html", bus=bus)

@app.route("/gps_map")
def gps_map():
    bus = get_bus_info()
    return render_template('gps_map.html', bus=bus)

@app.route("/movies/<subcat>")
def browse_movies(subcat):
    path = os.path.join('media/movies', subcat)
    files = os.listdir(path) if os.path.exists(path) else []
    bus = get_bus_info()
    return render_template("media_list.html", media_type='video', category=subcat, files=files, bus=bus)

@app.route("/musical_videos/<subcat>")
def browse_musical_videos(subcat):
    path = os.path.join('media/musical_videos', subcat)
    files = os.listdir(path) if os.path.exists(path) else []
    bus = get_bus_info()
    return render_template("media_list.html", media_type='video', category=subcat, files=files, bus=bus)

@app.route("/documentaries/<subcat>")
def browse_docs(subcat):
    path = os.path.join('media/documentaries', subcat)
    files = os.listdir(path) if os.path.exists(path) else []
    bus = get_bus_info()
    return render_template("media_list.html", media_type='video', category=subcat, files=files, bus=bus)

@app.route("/music/<subcat>")
def browse_music(subcat):
    path = os.path.join('media/musics', subcat)
    files = os.listdir(path) if os.path.exists(path) else []
    bus = get_bus_info()
    return render_template("media_list.html", media_type='audio', category=subcat, files=files, bus=bus)

@app.route("/media/<media_type>/<cat>/<fname>")
def serve_media(media_type, cat, fname):
    if media_type == 'video':
        if cat in MOVIE_CATS:
            base_dir = os.path.join('media/movies', cat)
        elif cat in MVIDEO_CATS:
            base_dir = os.path.join('media/musical_videos', cat)
        elif cat in DOC_CATS:
            base_dir = os.path.join('media/documentaries', cat)
        else:
            return "Invalid video category", 404
    elif media_type == 'audio':
        base_dir = os.path.join('media/musics', cat)
    else:
        return "Invalid media", 404
    return send_from_directory(base_dir, fname)

@app.route('/admin', methods=["GET", "POST"])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        if form.password.data == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Wrong password!")
    return render_template("admin_login.html", form=form, bus=get_bus_info())

@app.route('/admin/dashboard', methods=["GET","POST"])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    bus = get_bus_info()
    if request.method == "POST" and 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('admin_dashboard'))
        formtype = request.form.get('formtype')
        subcat = request.form.get('subcat')
        if formtype in ['movies','musical_videos','documentaries','musics']:
            dst = os.path.join('media', formtype, subcat, file.filename)
            file.save(dst)
            flash(f"Uploaded to {formtype}/{subcat}")
        elif formtype == 'game':
            dst = os.path.join('templates/games', file.filename)
            file.save(dst)
            flash("Game uploaded!")
        return redirect(url_for('admin_dashboard'))
    buses = all_buses()
    staff = get_bus_info_by_reg(bus.get("registration")) if bus.get("registration") else {}
    return render_template(
        'admin_dashboard.html', bus=bus, os=os, passengers=all_passengers(),
        staff=staff, buses=buses
    )

@app.route('/admin/banner', methods=["GET", "POST"])
def admin_banner():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    msg = get_banner_message()
    if request.method == "POST":
        if "clear" in request.form:
            open("data/banner_message.txt", "w").close()
            flash("Banner cleared!")
        else:
            newmsg = request.form.get("banner_message", "")
            with open("data/banner_message.txt","w") as f: f.write(newmsg.strip())
            flash("Banner updated!")
        return redirect(url_for('admin_banner'))
    return render_template("admin_banner.html", banner_message=msg)

@app.route('/admin/upload_thumbnail', methods=["POST"])
def admin_upload_thumbnail():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    thumbnail = request.files.get('thumbnail')
    if thumbnail and thumbnail.filename:
        fname = thumbnail.filename
       s3.upload_fileobj(
    thumbnail,
    S3_BUCKET,
    f"thumbnails/{fname}",
    ExtraArgs={"ContentType": thumbnail.content_type}
)

        flash(f"Thumbnail {fname} uploaded!")
    else:
        flash("No thumbnail uploaded.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/deletefile', methods=["POST"])
def admin_deletefile():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    filepath = request.form['filepath']
    try:
        os.remove(filepath)
        flash("File deleted.")
    except Exception as e:
        flash("Delete failed: " + str(e))
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin/download_log')
def admin_download_log():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return send_file(LOYALTY_LOG, as_attachment=True)

@app.route('/admin/staff', methods=["GET","POST"])
def staff_manage():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    reg = request.args.get("reg") or ""
    all_bus_info = all_buses()
    reg_list = list(all_bus_info.keys())
    staff = get_bus_info_by_reg(reg) if reg else {}
    if not isinstance(staff, dict):
        staff = {}
    form = StaffForm(request.form, **staff)
    if request.method == "POST" and form.validate():
        reg = form.reg.data.strip()
        staff_entry = {
            "reg": reg,
            "driver": form.driver.data,
            "dphone": form.dphone.data,
            "assistant": form.assistant.data,
            "aphone": form.aphone.data,
            "owner": form.owner.data,
            "ophone": form.ophone.data
        }
        save_bus_info(reg, staff_entry)
        flash(f"Bus info for {reg} updated.")
        return redirect(url_for('staff_manage', reg=reg))
    return render_template(
        "staff_manage.html",
        form=form,
        reg_list=reg_list,
        selected_reg=reg,
        staff=staff,
        bus=get_bus_info()
    )

app.jinja_env.globals['get_banner_message'] = get_banner_message

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
