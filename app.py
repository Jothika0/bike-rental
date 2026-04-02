from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, Admin, Bike, Booking, Payment
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_strong_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bike_rental.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_choice'

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('admin_'):
        admin_id = int(user_id.split('_')[1])
        return Admin.query.get(admin_id)
    else:
        return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth_choice')
def auth_choice():
    return render_template('auth_choice.html')

# === Client Auth ===
@app.route('/client/register', methods=['GET', 'POST'])
def client_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        license_number = request.form.get('license_number')
        password = request.form.get('password')
        
        # Handle file upload
        license_image = request.files.get('license_image')
        image_filename = ''
        if license_image:
            filename = secure_filename(license_image.filename)
            image_filename = os.path.join('uploads', filename) # Save path relative to static/images
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploads')
            os.makedirs(upload_path, exist_ok=True)
            license_image.save(os.path.join(upload_path, filename))
            
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered', 'danger')
            return redirect(url_for('client_register'))
            
        new_user = User(
            name=name, email=email, phone=phone, address=address,
            license_number=license_number, license_image=image_filename
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('client_login'))
        
    return render_template('client/register.html')

@app.route('/client/login', methods=['GET', 'POST'])
def client_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('client_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            
    return render_template('client/login.html')

@app.route('/client/dashboard')
@login_required
def client_dashboard():
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.id.desc()).all()
    total_spent = sum(p.amount for p in Payment.query.join(Booking).filter(Booking.user_id==current_user.id, Payment.status=='Completed').all())
    return render_template('client/dashboard.html', bookings=bookings, total_spent=total_spent)

@app.route('/client/rentals')
@login_required
def client_rentals():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.booking_date.desc()).all()
    return render_template('client/rentals.html', bookings=bookings)

@app.route('/client/payments')
@login_required
def client_payments():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    payments = Payment.query.filter(Payment.booking_id.in_([b.id for b in bookings])).all() if bookings else []
    return render_template('client/payments_history.html', payments=payments)

@app.route('/client/profile')
@login_required
def client_profile():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    return render_template('client/profile.html', user=current_user)

@app.route('/client/catalog')
@login_required
def client_catalog():
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    bikes = Bike.query.filter_by(availability=True).all()
    return render_template('client/catalog.html', bikes=bikes)

@app.route('/client/book/<int:bike_id>', methods=['GET', 'POST'])
@login_required
def client_book(bike_id):
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    
    if not current_user.is_verified:
        flash('Your account is not verified yet. Please wait for admin approval before booking.', 'danger')
        return redirect(url_for('client_dashboard'))
        
    bike = Bike.query.get_or_404(bike_id)
    if not bike.availability:
        flash('This bike is currently unavailable.', 'danger')
        return redirect(url_for('client_catalog'))
        
    if request.method == 'POST':
        booking_date = request.form.get('booking_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        existing_bookings = Booking.query.filter_by(bike_id=bike.id, booking_date=booking_date, status='Accepted').all()
        conflict = False
        for eb in existing_bookings:
            if (start_time >= eb.start_time and start_time < eb.end_time) or \
               (end_time > eb.start_time and end_time <= eb.end_time) or \
               (start_time <= eb.start_time and end_time >= eb.end_time):
                conflict = True
                break
                
        if conflict:
            flash('Bike is already booked during this time slot.', 'danger')
            return redirect(url_for('client_book', bike_id=bike.id))
            
        try:
            sh = int(start_time.split(':')[0])
            eh = int(end_time.split(':')[0])
            hours = max(1, eh - sh)
        except:
            hours = 1
        amount = hours * bike.price
        
        new_booking = Booking(user_id=current_user.id, bike_id=bike.id, 
                              booking_date=booking_date, start_time=start_time, 
                              end_time=end_time, amount=amount, status='Pending')
        db.session.add(new_booking)
        db.session.commit()
        
        return redirect(url_for('client_payment', booking_id=new_booking.id))
        
    return render_template('client/book.html', bike=bike)

@app.route('/client/payment/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def client_payment(booking_id):
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        return redirect(url_for('client_dashboard'))

    if Payment.query.filter_by(booking_id=booking.id).first():
       flash('Payment already made for this booking.', 'info')
       return redirect(url_for('client_dashboard'))

    if request.method == 'POST':
        payment = Payment(booking_id=booking.id, amount=booking.amount, status='Completed')
        db.session.add(payment)
        db.session.commit()
        
        flash('Payment Successful! Booking request sent to admin.', 'success')
        return redirect(url_for('client_dashboard'))
        
    return render_template('client/payment.html', booking=booking)

# === Admin Auth ===
@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_exists = Admin.query.filter_by(username=username).first()
        if admin_exists:
            flash('Admin username already taken', 'danger')
            return redirect(url_for('admin_register'))
            
        new_admin = Admin(username=username)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()
        
        flash('Admin registration successful. Please login.', 'success')
        return redirect(url_for('admin_login'))
        
    return render_template('admin/register.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            flash('Admin logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    
    total_bookings = Booking.query.count()
    active_rentals = Booking.query.filter_by(status='Ongoing').count()
    total_earnings = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
    recent_bookings = Booking.query.order_by(Booking.id.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           earnings=total_earnings, 
                           bookings=total_bookings, 
                           active_rentals=active_rentals,
                           recent_bookings=recent_bookings)

@app.route('/admin/users')
@login_required
def admin_users():
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/verify_user/<int:user_id>/<action>')
@login_required
def admin_verify_user(user_id, action):
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    user = User.query.get_or_404(user_id)
    if action == 'verify':
        user.is_verified = True
        flash(f'User {user.name} verified.', 'success')
    elif action == 'reject':
        user.is_verified = False
        flash(f'User {user.name} rejected.', 'danger')
    db.session.commit()
    return redirect(url_for('admin_users'))

@app.route('/admin/bikes', methods=['GET', 'POST'])
@login_required
def admin_bikes():
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        bike_type = request.form.get('type')
        price = request.form.get('price')
        
        image = request.files.get('image')
        image_filename = ''
        if image:
            filename = secure_filename(image.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'bikes')
            os.makedirs(upload_path, exist_ok=True)
            image.save(os.path.join(upload_path, filename))
            image_filename = os.path.join('bikes', filename)
            
        new_bike = Bike(name=name, type=bike_type, price=float(price), image=image_filename)
        db.session.add(new_bike)
        db.session.commit()
        flash('Bike added successfully!', 'success')
        return redirect(url_for('admin_bikes'))
        
    bikes = Bike.query.all()
    return render_template('admin/bikes.html', bikes=bikes)

@app.route('/admin/delete_bike/<int:bike_id>')
@login_required
def admin_delete_bike(bike_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    bike = Bike.query.get_or_404(bike_id)
    db.session.delete(bike)
    db.session.commit()
    flash('Bike deleted successfully!', 'success')
    return redirect(url_for('admin_bikes'))

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    bookings = Booking.query.all()
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/admin/update_booking/<int:booking_id>/<status>')
@login_required
def admin_update_booking(booking_id, status):
    if not isinstance(current_user, Admin):
        return redirect(url_for('client_dashboard'))
    booking = Booking.query.get_or_404(booking_id)
    if status in ['Accepted', 'Rejected', 'Ongoing', 'Completed']:
        booking.status = status
        db.session.commit()
        flash(f'Booking status updated to {status}.', 'success')
    return redirect(url_for('admin_bookings'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, port=8080)
