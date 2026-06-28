#!/usr/bin/python3
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

### LEAVE APPLICATION ###
class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, nullable=False)

    date = db.Column(db.Date, nullable=False)

    reason = db.Column(db.String(200))

    status = db.Column(db.String(20), default="Pending")

    # ✅ NEW
    leave_type = db.Column(db.String(20), default="Casual")


class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(20), nullable=False)

    first_login = db.Column(db.Boolean, default=True)

    # ✅ NEW
    joining_date = db.Column(db.Date, nullable=True)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, nullable=False)

    login_time = db.Column(db.DateTime, nullable=True)

    logout_time = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20))

    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
