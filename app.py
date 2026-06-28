#!/usr/bin/python3
from flask import Flask, render_template, request, redirect, session, flash
from models import db, User, Attendance, LeaveRequest
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, date
from functools import wraps
import calendar

import calendar

def calculate_leave_balance(user):

    today = date.today()
    year_start = date(today.year, 1, 1)

    joining_date = user.joining_date or year_start
    effective_start = max(joining_date, year_start)

    # =========================
    # ✅ CASUAL LEAVE (PRORATED YEARLY - NO ROUNDING)
    # =========================
    # =========================
    # ✅ CASUAL LEAVE (DAY-LEVEL PRORATED)
    # =========================

    year_end = date(today.year, 12, 31)

    total_days_in_year = (year_end - year_start).days + 1
    days_remaining = (year_end - effective_start).days + 1

    casual_total = (days_remaining / total_days_in_year) * 6
    # =========================
    # ✅ ANNUAL LEAVE (MONTHLY - NO ROUNDING)
    # =========================
    months_worked = (today.year - effective_start.year) * 12 + (today.month - effective_start.month)

    last_day = calendar.monthrange(today.year, today.month)[1]

    # Only count completed months
    if today.day < last_day:
        months_worked -= 1

    if months_worked < 0:
        months_worked = 0

    annual_total = months_worked

    # =========================
    # USED LEAVES
    # =========================
    casual_used = LeaveRequest.query.filter_by(
        user_id=user.id,
        leave_type="Casual",
        status="Approved"
    ).filter(LeaveRequest.date >= year_start).count()

    annual_used = LeaveRequest.query.filter_by(
        user_id=user.id,
        leave_type="Annual",
        status="Approved"
    ).filter(LeaveRequest.date >= year_start).count()

    return {
        "casual_total": round(casual_total, 2),
        "casual_used": casual_used,
        "casual_balance": round(casual_total - casual_used, 2),
        "annual_total": annual_total,
        "annual_used": annual_used,
        "annual_balance": annual_total - annual_used
    }
# ===========================
# ADMIN DECORATOR
# ===========================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        print("SESSION DATA:", session)

        if 'user_id' not in session:
            print("NO USER SESSION")
            return redirect('/')

        if not session.get('role') or session.get('role') != "admin":
            print("NOT ADMIN")
            return redirect('/')

        print("ADMIN ACCESS GRANTED")
        return f(*args, **kwargs)

    return decorated_function


# ===========================
# APP INIT
# ===========================
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = "attendance_secret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ===========================
# AUTO ABSENT FUNCTION
# ===========================
def mark_absent_for_today():
    today = date.today()
    cutoff_time = time(15, 0)

    now = datetime.now().time()

    if now < cutoff_time:
        return

    users = User.query.filter_by(role="employee").all()

    for user in users:

        # Skip if approved leave exists
        leave_exists = LeaveRequest.query.filter_by(
            user_id=user.id,
            date=today,
            status="Approved"
        ).first()

        if leave_exists:
            continue

        existing = Attendance.query.filter(
            Attendance.user_id == user.id,
            Attendance.date == today
        ).first()

        if not existing:
            absent = Attendance(
                user_id=user.id,
                login_time=None,
                status="Absent",
                date=today
            )
            db.session.add(absent)

    db.session.commit()


# ===========================
# LOGIN
# ===========================
@app.route('/', methods=['GET','POST'])
def login():

    if request.method == "POST":

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password,password):

            session['user_id'] = user.id
            session['role'] = user.role

            print("LOGIN ROLE:", user.role)

            if user.first_login:
                return redirect('/reset_password')

            if user.role == "admin":
                return redirect('/admin')

            return redirect('/dashboard')

        flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    response = redirect('/')
    response.headers["Cache-Control"] = "no-store"
    return response

# ===========================
# ADMIN DASHBOARD
# ===========================
@app.route('/admin')
@admin_required
def admin():

    mark_absent_for_today()

    users = User.query.filter_by(role="employee").all()

    user_balances = []

    for user in users:
        balance = calculate_leave_balance(user)
        user_balances.append((user, balance))

    attendance = db.session.query(
        Attendance,
        User.username
    ).join(User, Attendance.user_id == User.id).all()

    return render_template(
        "admin_dashboard.html",
        users=user_balances,
        attendance=attendance
    )

# ===========================
# ATTENDANCE REPORT
# ===========================
@app.route('/attendance_report', methods=['GET', 'POST'])
@admin_required
def attendance_report():

    users = User.query.filter_by(role="employee").all()
    records = []

    if request.method == "POST":
        user_id = request.form.get('user_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        query = db.session.query(Attendance, User.username).join(
            User, Attendance.user_id == User.id
        )

        if user_id:
            query = query.filter(Attendance.user_id == user_id)

        if start_date and end_date:
            query = query.filter(
                Attendance.date.between(start_date, end_date)
            )

        records = query.order_by(Attendance.date.desc()).all()

    return render_template(
        "attendance_report.html",
        users=users,
        records=records
    )


# ===========================
# ANALYTICS
# ===========================
@app.route('/analytics', methods=['GET', 'POST'])
@admin_required
def analytics():

    users = User.query.filter_by(role="employee").all()

    report = []

    start_date = None
    end_date = None

    if request.method == "POST":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

    for user in users:

        query = Attendance.query.filter_by(user_id=user.id)

        # ✅ Apply date filter if selected
        if start_date and end_date:
            query = query.filter(
                Attendance.date.between(start_date, end_date)
            )

        total = query.count()
        late = query.filter_by(status="Late").count()
        half = query.filter_by(status="Half Day").count()
        present = query.filter_by(status="Present").count()
        absent = query.filter_by(status="Absent").count()

        report.append({
            "username": user.username,
            "total": total,
            "present": present,
            "late": late,
            "half": half,
            "absent": absent
        })

    return render_template(
        "analytics.html",
        report=report,
        start_date=start_date,
        end_date=end_date
    )

# ===========================
# EMPLOYEE MANAGEMENT
# ===========================
@app.route('/create_employee', methods=['POST'])
@admin_required
def create_employee():

    username = request.form['username']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])

    joining_date = request.form.get('joining_date')

    user = User(
        username=username,
        email=email,
        password=password,
        role="employee",
        first_login=True,
        joining_date=datetime.strptime(joining_date, "%Y-%m-%d").date() if joining_date else None
    )

    db.session.add(user)
    db.session.commit()

    flash("Employee created successfully", "success")
    return redirect('/admin')

@app.route('/delete_employee/<int:user_id>')
@admin_required
def delete_employee(user_id):

    user = User.query.get(user_id)

    if user:
        db.session.delete(user)
        db.session.commit()

    flash("Employee deleted", "danger")
    return redirect('/admin')


# ===========================
# EMPLOYEE DASHBOARD
# ===========================
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/')

    attendance = Attendance.query.filter_by(user_id=session['user_id']).all()

    user = User.query.get(session['user_id'])
    balance = calculate_leave_balance(user)

    return render_template("dashboard.html", attendance=attendance, balance=balance)

# ===========================
# PASSWORD MANAGEMENT
# ===========================
@app.route('/change_password', methods=['GET','POST'])
def change_password():

    if 'user_id' not in session:
        return redirect('/')

    if request.method == "POST":

        user = User.query.get(session['user_id'])
        user.password = generate_password_hash(request.form['password'])
        db.session.commit()

        flash("Password updated successfully", "success")

        return redirect('/admin' if user.role == "admin" else '/dashboard')

    return render_template("reset_password.html")


@app.route('/admin_reset_password/<int:user_id>', methods=['GET','POST'])
@admin_required
def admin_reset_password(user_id):

    user = User.query.get(user_id)

    if request.method == "POST":
        user.password = generate_password_hash(request.form['password'])
        db.session.commit()

        flash("User password updated", "success")
        return redirect('/admin')

    return render_template("reset_password.html")


# ===========================
# ATTENDANCE
# ===========================
@app.route('/mark_attendance')
def mark_attendance():

    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    now = datetime.now()
    today = date.today()

    existing = Attendance.query.filter_by(
        user_id=user_id,
        date=today
    ).first()

    if existing:
        flash("You have already marked attendance today", "danger")
        return redirect('/dashboard')

    login_time = now.time()
    status = "Present"

    if login_time > time(15,0):
        flash("Attendance closed after 03:00 PM", "danger")
        return redirect('/dashboard')

    elif login_time >= time(12,0):
        status = "Half Day"

    elif login_time > time(9,15):
        status = "Late"

    attendance = Attendance(
        user_id=user_id,
        login_time=now,
        status=status,
        date=today
    )

    db.session.add(attendance)
    db.session.commit()

    flash("Attendance marked successfully", "success")
    return redirect('/dashboard')


@app.route('/logout_attendance', methods=['GET', 'POST'])
def logout_attendance():

    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    today = date.today()

    attendance = Attendance.query.filter_by(
        user_id=user_id,
        date=today
    ).first()

    if not attendance:
        flash("You must login attendance first", "danger")
        return redirect('/dashboard')

    if attendance.logout_time:
        flash("You already logged out today", "danger")
        return redirect('/dashboard')

    now = datetime.now()

    # ⏱ Calculate working hours
    if attendance.login_time:
        worked_hours = (now - attendance.login_time).total_seconds() / 3600
    else:
        worked_hours = 0

    # ⚠️ If less than 6 hours → confirmation required
    if worked_hours < 6:

        # If confirmation not given yet → show prompt
        if request.args.get("confirm") != "yes":
            flash("You are leaving before completing 6 hours. You will be marked Half Day. Click again to confirm.", "warning")
            return redirect('/dashboard')

        # ✅ User confirmed → mark half day
        attendance.status = "Half Day"

    attendance.logout_time = now
    db.session.commit()

    flash("Logout attendance marked", "success")
    return redirect('/dashboard')

    attendance.logout_time = datetime.now()
    db.session.commit()

    flash("Logout attendance marked", "success")
    return redirect('/dashboard')


# ===========================
# RESET PASSWORD
# ===========================
@app.route('/reset_password', methods=['GET','POST'])
def reset_password():

    if 'user_id' not in session:
        return redirect('/')

    if request.method == "POST":

        user = User.query.get(session['user_id'])
        user.password = generate_password_hash(request.form['password'])
        user.first_login = False

        db.session.commit()

        flash("Password updated successfully", "success")
        return redirect('/')

    return render_template("reset_password.html")


# ===========================
# LEAVE MANAGEMENT
# ===========================
@app.route('/apply_leave', methods=['GET', 'POST'])
def apply_leave():

    if 'user_id' not in session:
        return redirect('/')

    if request.method == "POST":
        leave_date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
        reason = request.form['reason']
        leave_type = request.form['leave_type']

        user = User.query.get(session['user_id'])
        balance = calculate_leave_balance(user)

        if leave_type == "Casual" and balance["casual_balance"] <= 0:
            flash("No Casual leaves remaining", "danger")
            return redirect('/dashboard')

        if leave_type == "Annual" and balance["annual_balance"] <= 0:
            flash("No Annual leaves remaining", "danger")
            return redirect('/dashboard')

        leave = LeaveRequest(
            user_id=session['user_id'],
            date=leave_date,
            reason=reason,
            leave_type=leave_type
        )

        db.session.add(leave)
        db.session.commit()

        flash("Leave request submitted", "success")
        return redirect('/dashboard')

    return render_template("apply_leave.html")

@app.route('/leave_requests')
@admin_required
def leave_requests():

    requests = db.session.query(LeaveRequest, User.username).join(
        User, LeaveRequest.user_id == User.id
    ).all()

    return render_template("leave_requests.html", requests=requests)


@app.route('/approve_leave/<int:leave_id>')
@admin_required
def approve_leave(leave_id):

    leave = LeaveRequest.query.get(leave_id)
    leave.status = "Approved"

    # Delete existing attendance
    Attendance.query.filter_by(
        user_id=leave.user_id,
        date=leave.date
    ).delete()

    attendance = Attendance(
        user_id=leave.user_id,
        status="Leave",
        date=leave.date
    )

    db.session.add(attendance)
    db.session.commit()

    return redirect('/leave_requests')


@app.route('/reject_leave/<int:leave_id>')
@admin_required
def reject_leave(leave_id):

    leave = LeaveRequest.query.get(leave_id)
    leave.status = "Rejected"

    db.session.commit()
    return redirect('/leave_requests')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
