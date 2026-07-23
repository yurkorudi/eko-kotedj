from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    check_in = db.Column(db.Date, nullable=False, index=True)
    check_out = db.Column(db.Date, nullable=False, index=True)
    comment = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    source = db.Column(db.String(20), default="guest", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def guest_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class GalleryImage(db.Model):
    __tablename__ = "gallery"

    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(160), nullable=False, default="Фото галереї")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CabinImage(db.Model):
    __tablename__ = "cabin_images"

    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(160), nullable=False, default="Фото хатинки")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class HeroImage(db.Model):
    __tablename__ = "hero_images"

    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(160), nullable=False, default="Гори біля хатинки")
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
