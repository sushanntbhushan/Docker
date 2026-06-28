#!/usr/bin/python3
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():

    db.create_all()

    admin = User(
        username="admin",
        email="info@bytswave.com",
        password=generate_password_hash("admin123"),
        role="admin",
        first_login=False
    )

    db.session.add(admin)
    db.session.commit()

print("Admin created successfully")
