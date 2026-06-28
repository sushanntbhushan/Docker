#!/usr/bin/python3

from app import app
from models import db, User
from werkzeug.security import generate_password_hash
from sqlalchemy import or_

with app.app_context():

    # Create tables if they don't already exist
    db.create_all()

    # Check if an admin user already exists by username or email
    existing_user = User.query.filter(
        or_(
            User.username == "admin",
            User.email == "info@bytswave.com"
        )
    ).first()

    if existing_user:
        print("Admin user already exists. Skipping creation.")
    else:
        admin = User(
            username="admin",
            email="info@bytswave.com",
            password=generate_password_hash("admin123"),
            role="admin",
            first_login=False
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin created successfully.")
