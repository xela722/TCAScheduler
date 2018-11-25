from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
import sqlite3
from tempfile import gettempdir
import hashlib

app = Flask(__name__)

app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def getDbCur(db):
    db = sqlite3.connect(db)
    return db.cursor()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def userExists(user_name):
    cur = getDbCur("data.db")
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_name,))
    if cur.fetchone():
        return True
    else:
        return False

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/portal")
@login_required
def portal():
    return render_template("welcome.html", schedule=getSchedule())

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method =='GET':
        return render_template("login.html")

    if request.method == "POST":
        cur = getDbCur("data.db")
        cur.execute("SELECT oid, user_id, user_hash FROM users WHERE user_id=? AND user_hash=?", (request.form.get("username"), hashlib.sha256(request.form.get("password")).hexdigest()))
        pHash = cur.fetchone()


        if not pHash:
            #fail login
            return render_template("login.html", fail=True)
        else:
            #success
            session['id']=pHash[0]
            return redirect(url_for("portal"))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not userExists(request.form.get("username")) and request.form.get("password") == request.form.get("repPassword"):
            db = sqlite3.connect("data.db")
            cur = db.cursor()
            pHash = hashlib.sha256(request.form.get('password')).hexdigest()
            cur.execute("INSERT INTO users (user_id, user_email, user_hash, role) VALUES (?, ?, ?, ?)", (request.form.get("username"), request.form.get('email'), pHash, "user"))
            db.commit()

            return redirect(url_for("login"))
        else:
            return render_template("register.html", userExists=True)
    else:
        return render_template("register.html")

@app.route("/addEvent", methods=['GET', 'POST'])
def addEvent():
    if request.method == 'GET':
        return render_template("addEvent.html", cleaners=getCleaners())
    if request.method=='POST':
        db=sqlite3.connect("data.db")
        cur = db.cursor()
        cur.execute("SELECT oid, name FROM employees WHERE name=?", (request.form.get("cleaner"),))

        tempEvent = event(
            request.form.get("name"),
            request.form.get("address"),
            cur.fetchone()[0],
            request.form.get("wkDay"),
            request.form.get("timeSlot"),
            request.form.get("repeat"),
            -1
        )

        cur.execute("INSERT INTO cleanings (name, address, cleanerId, dow, time, repeatId) VALUES (?,?,?,?,?,?)", (
            tempEvent.name,
            tempEvent.address,
            tempEvent.cleanerId,
            tempEvent.dow,
            tempEvent.timeSlot,
            tempEvent.repetitionId))
        db.commit()
        return redirect(url_for("portal"))

@app.route("/cleaning/<int:id>")
def eventView(id):
    db=sqlite3.connect("data.db")
    cur = db.cursor()
    cur.execute("SELECT name, address, notes FROM cleanings WHERE oid=?", (id,))

    return render_template("eventView.html")

def getCleaners():
    db=sqlite3.connect("data.db")
    cur=db.cursor()
    cur.execute("SELECT * FROM employees")
    return cur.fetchall()

def getSchedule():
    db=sqlite3.connect("data.db")
    cur=db.cursor()
    cur.execute("SELECT cleanings.name, cleanings.address, cleanings.cleanerID, cleanings.dow, cleanings.time, cleanings.repeatId, employees.name, cleanings.oid FROM cleanings INNER JOIN employees ON employees.oid = cleanings.cleanerID")
    return [event(cleaning[0], cleaning[1], cleaning[6], cleaning[3], cleaning[4], cleaning[5], cleaning[7]) for cleaning in cur.fetchall() ]

class event:
    def __init__(self, name, address, cleanerId, dow, timeSlot, repetitionId, oid=None):
        self.name = name
        self.address = address
        self.cleanerId = cleanerId
        self.dow = dow
        self.timeSlot = timeSlot
        self.repetitionId = repetitionId
        self.oid = oid
        self.url = url_for("eventView", id=oid)
