from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    license_number = db.Column(db.String(50))
    license_image = db.Column(db.String(200)) # path to uploaded image
    is_verified = db.Column(db.Boolean, default=False)
    total_spent = db.Column(db.Float, default=0.0)
    bookings = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, pwd):
        self.password = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password, pwd)


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, pwd):
        self.password = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password, pwd)

    def get_id(self):
        # We prefix admin ID to separate them from user IDs in flask_login
        return f"admin_{self.id}"


class Bike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50)) # e.g., Scooter, Sports, Cruiser
    price = db.Column(db.Float, nullable=False)
    availability = db.Column(db.Boolean, default=True)
    image = db.Column(db.String(200))
    bookings = db.relationship('Booking', backref='bike', lazy=True)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bike_id = db.Column(db.Integer, db.ForeignKey('bike.id'), nullable=False)
    booking_date = db.Column(db.String(20), nullable=False) # e.g., "YYYY-MM-DD"
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Accepted, Rejected, Ongoing, Completed
    amount = db.Column(db.Float, nullable=False)
    payments = db.relationship('Payment', backref='booking', lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Completed')
