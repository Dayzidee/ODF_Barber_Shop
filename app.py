import os
import re
import enum
import json
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from sqlalchemy.orm import validates
from sqlalchemy import event, text, Enum, UniqueConstraint, CheckConstraint

from dotenv import load_dotenv

load_dotenv()

# --- Initialize Flask App ---
app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.config["SESSION_COOKIE_NAME"] = "odf_session"
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "odf_admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "odf_secure_password_123")

# --- Database Configuration ---
DATABASE_URL_FROM_ENV = os.environ.get("DATABASE_URL")
if DATABASE_URL_FROM_ENV and DATABASE_URL_FROM_ENV.startswith("postgresql://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL_FROM_ENV
elif DATABASE_URL_FROM_ENV and DATABASE_URL_FROM_ENV.startswith("postgres://"):
    corrected_db_url = DATABASE_URL_FROM_ENV.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = corrected_db_url
else:
    DB_NAME = "odf_barber_shop.db"
    DB_PATH = os.path.join(BASE_DIR, DB_NAME)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- ENUMS ---
class AppointmentStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"

class TimeSlotPeriod(enum.Enum):
    MORNING = "Morning (9AM-12PM)"
    AFTERNOON = "Afternoon (12PM-4PM)"
    EVENING = "Evening (4PM-8PM)"

# --- MODELS ---
appointment_services = db.Table(
    'odf_appointment_services',
    db.Column('appointment_id', db.Integer, db.ForeignKey('odf_appointments.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('odf_services.id'), primary_key=True)
)

class Barber(db.Model):
    __tablename__ = 'odf_barbers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    profile_image = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_master = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    appointments = db.relationship('Appointment', back_populates='barber')
    time_slots = db.relationship('TimeSlot', back_populates='barber')

    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email address")
        return email

    @validates('phone')
    def validate_phone(self, key, phone):
        if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
            raise ValueError("Invalid phone number format")
        return phone

class Service(db.Model):
    __tablename__ = 'odf_services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @validates('price')
    def validate_price(self, key, price):
        if float(price) < 0:
            raise ValueError("Price cannot be negative")
        return price

    @validates('duration_minutes')
    def validate_duration(self, key, duration):
        if duration < 15:
            raise ValueError("Service duration must be at least 15 minutes")
        return duration

class TimeSlot(db.Model):
    __tablename__ = 'odf_time_slots'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    period = db.Column(Enum(TimeSlotPeriod), nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    max_appointments = db.Column(db.Integer, default=1, nullable=False)
    current_appointments = db.Column(db.Integer, default=0, nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey('odf_barbers.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        UniqueConstraint('date', 'period', 'barber_id', name='_date_period_barber_uc'),
        CheckConstraint('current_appointments <= max_appointments', name='check_appointment_limit'),
    )
    barber = db.relationship('Barber', back_populates='time_slots')
    appointments = db.relationship('Appointment', back_populates='time_slot')

    @property
    def is_fully_booked(self):
        return self.current_appointments >= self.max_appointments

    @validates('date')
    def validate_date(self, key, date):
        if date < datetime.now(timezone.utc).date():
            raise ValueError("Cannot create time slots for past dates")
        return date

    @validates('current_appointments')
    def validate_current_appointments(self, key, value):
        if value > self.max_appointments:
            raise ValueError("Current appointments cannot exceed maximum allowed")
        return value

class Appointment(db.Model):
    __tablename__ = 'odf_appointments'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False, index=True)
    customer_email = db.Column(db.String(120), nullable=False, index=True)
    is_first_time_customer = db.Column(db.Boolean, default=True)
    time_slot_id = db.Column(db.Integer, db.ForeignKey('odf_time_slots.id'), nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey('odf_barbers.id'), nullable=False)
    status = db.Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False, index=True)
    address_street = db.Column(db.String(200), nullable=False)
    address_city = db.Column(db.String(100), nullable=False)
    address_postal_code = db.Column(db.String(20), nullable=False)
    address_gmaps_link = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    estimated_duration = db.Column(db.Integer, nullable=True)
    estimated_price = db.Column(db.Numeric(10, 2), nullable=True)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    confirmed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    time_slot = db.relationship('TimeSlot', back_populates='appointments')
    barber = db.relationship('Barber', back_populates='appointments')
    services = db.relationship('Service', secondary=appointment_services)

    @validates('customer_email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email address")
        return email

    @validates('customer_phone')
    def validate_phone(self, key, phone):
        if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
            raise ValueError("Invalid phone number format")
        return phone

    @validates('address_postal_code')
    def validate_postal_code(self, key, postal_code):
        if not re.match(r"^\d{6}$", postal_code):
            raise ValueError("Invalid postal code format")
        return postal_code

    def update_status(self, new_status):
        self.status = new_status
        if new_status == AppointmentStatus.CONFIRMED:
            self.confirmed_at = datetime.now(timezone.utc)
        elif new_status == AppointmentStatus.COMPLETED:
            self.completed_at = datetime.now(timezone.utc)
        elif new_status == AppointmentStatus.CANCELLED:
            self.cancelled_at = datetime.now(timezone.utc)
        return self

    def calculate_totals(self):
        total_duration = sum(service.duration_minutes for service in self.services)
        total_price = sum(float(service.price) for service in self.services)
        self.estimated_duration = total_duration
        self.estimated_price = total_price
        return self

class Feedback(db.Model):
    __tablename__ = 'odf_feedback'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Event listeners for Appointment ---
@event.listens_for(Appointment, 'before_insert')
def appointment_before_insert(mapper, connection, target):
    if target.services:
        target.calculate_totals()

@event.listens_for(Appointment, 'after_insert')
def appointment_after_insert(mapper, connection, target):
    stmt = text(
        "UPDATE odf_time_slots SET current_appointments = current_appointments + 1 "
        "WHERE id = :slot_id"
    )
    connection.execute(stmt, {"slot_id": target.time_slot_id})

@event.listens_for(Appointment, 'after_delete')
def appointment_after_delete(mapper, connection, target):
    stmt = text(
        "UPDATE odf_time_slots SET current_appointments = CASE WHEN current_appointments > 0 THEN current_appointments - 1 ELSE 0 END "
        "WHERE id = :slot_id"
    )
    connection.execute(stmt, {"slot_id": target.time_slot_id})

# --- Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        if name and email and message:
            feedback = Feedback(name=name, email=email, message=message)
            db.session.add(feedback)
            db.session.commit()
            flash("Thank you for your feedback!", "success")
            return redirect(url_for("home") + "#contact")
        else:
            flash("All fields are required.", "danger")
            return redirect(url_for("home") + "#contact")
    return render_template("index.html", title="ODF Barber Shop - Expert Barbers at Your Service")

@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html", title="ODF Barber Shop - Portfolio")

@app.route("/book", methods=["GET", "POST"])
def book_appointment():
    active_services = Service.query.filter_by(is_active=True).all()
    today = datetime.now(timezone.utc).date()
    five_days_later = today + timedelta(days=5)
    available_time_slots = (
        TimeSlot.query.filter(
            TimeSlot.date >= today,
            TimeSlot.date <= five_days_later,
            TimeSlot.is_available == True,
            TimeSlot.current_appointments < TimeSlot.max_appointments,
        )
        .order_by(TimeSlot.date, TimeSlot.period)
        .all()
    )
    time_slot_options = []
    for slot in available_time_slots:
        formatted_date = slot.date.strftime("%A, %B %d, %Y")
        time_slot_options.append(
            {
                "id": slot.id,
                "text": f"{formatted_date} - {slot.period.value}",
                "date": slot.date.isoformat(),
                "period": slot.period.value,
            }
        )
    active_barbers = Barber.query.filter_by(is_active=True).all()
    if request.method == "POST":
        required_fields = {
            "fullName": "Full Name",
            "phone": "Phone Number",
            "email": "Email Address",
            "timeSlot": "Time Slot",
            "streetAddress": "Street Address",
            "city": "City",
            "postalCode": "Postal Code",
            "barber": "Barber",
        }
        missing = []
        for key, display_name in required_fields.items():
            if not request.form.get(key):
                missing.append(display_name)
        service_ids = request.form.getlist("servicesNeeded[]")
        if not service_ids:
            missing.append("Service(s) Required")
        if missing:
            flash(
                f"Please fill out all required fields: {', '.join(missing)}.", "danger"
            )
            form_data_for_template = {
                key: request.form.get(key) for key in request.form
            }
            form_data_for_template["servicesNeeded"] = service_ids
            return render_template(
                "book_appointment.html",
                title="Book Appointment",
                form_data=form_data_for_template,
                services=active_services,
                time_slots=time_slot_options,
                barbers=active_barbers,
            )
        try:
            time_slot_id = int(request.form.get("timeSlot"))
            time_slot = TimeSlot.query.get_or_404(time_slot_id)
            if (
                time_slot.current_appointments >= time_slot.max_appointments
                or not time_slot.is_available
            ):
                flash(
                    "Sorry, this time slot is no longer available. Please select another time.",
                    "warning",
                )
                form_data_for_template = {
                    key: request.form.get(key) for key in request.form
                }
                form_data_for_template["servicesNeeded"] = service_ids
                return render_template(
                    "book_appointment.html",
                    title="Book Appointment",
                    form_data=form_data_for_template,
                    services=active_services,
                    time_slots=time_slot_options,
                    barbers=active_barbers,
                )
            selected_services = []
            for service_id in service_ids:
                service = Service.query.get(int(service_id))
                if service and service.is_active:
                    selected_services.append(service)
            if not selected_services:
                flash("Please select at least one valid service.", "danger")
                form_data_for_template = {
                    key: request.form.get(key) for key in request.form
                }
                return render_template(
                    "book_appointment.html",
                    title="Book Appointment",
                    form_data=form_data_for_template,
                    services=active_services,
                    time_slots=time_slot_options,
                    barbers=active_barbers,
                )
            barber_id = int(request.form.get("barber"))
            barber = Barber.query.get_or_404(barber_id)
            new_appointment = Appointment(
                customer_name=request.form.get("fullName"),
                customer_phone=request.form.get("phone"),
                customer_email=request.form.get("email"),
                address_street=request.form.get("streetAddress"),
                address_city=request.form.get("city"),
                address_postal_code=request.form.get("postalCode"),
                address_gmaps_link=request.form.get("locationLink"),
                notes=request.form.get("specialInstructions"),
                is_first_time_customer=request.form.get("isFirstTime") == "yes",
                time_slot_id=time_slot.id,
                barber_id=barber.id,
                status=AppointmentStatus.PENDING,
            )
            for service in selected_services:
                new_appointment.services.append(service)
            new_appointment.calculate_totals()
            db.session.add(new_appointment)
            db.session.commit()
            flash(
                "Your appointment request has been sent! ODF Barber Shop will contact you to confirm your appointment.",
                "success",
            )
            return redirect(url_for("thank_you"))
        except ValueError as ve:
            app.logger.error(
                f"Error processing appointment: Invalid data format - {ve}"
            )
            flash("Invalid data submitted. Please check your inputs.", "danger")
            form_data_for_template = {
                key: request.form.get(key) for key in request.form
            }
            form_data_for_template["servicesNeeded"] = service_ids
            return render_template(
                "book_appointment.html",
                title="Book Appointment",
                form_data=form_data_for_template,
                services=active_services,
                time_slots=time_slot_options,
                barbers=active_barbers,
            )
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error saving appointment: {e} - Data: {request.form}")
            flash(
                f"An error occurred while requesting your appointment. Please try again.",
                "danger",
            )
            form_data_for_template = {
                key: request.form.get(key) for key in request.form
            }
            form_data_for_template["servicesNeeded"] = service_ids
            return render_template(
                "book_appointment.html",
                title="Book Appointment",
                form_data=form_data_for_template,
                services=active_services,
                time_slots=time_slot_options,
                barbers=active_barbers,
            )
    return render_template(
        "book_appointment.html",
        title="Book Appointment",
        form_data={},
        services=active_services,
        time_slots=time_slot_options,
        barbers=active_barbers,
    )

@app.route("/thank-you")
def thank_you():
    return render_template(
        "thank_you.html",
        title="Thank You - ODF Barber Shop",
        message="Your appointment request has been received!",
        subtitle="ODF Barber Shop will contact you shortly to confirm your appointment.",
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.permanent = True
            session["admin_logged_in"] = True
            session["admin_name"] = "ODF Administrator"
            flash("Logged in successfully to ODF Barber Shop admin!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid username or password.", "danger")
    return render_template("admin_login.html", title="ODF Barber Shop - Admin Login")

@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_name", None)
    flash("You have been logged out of ODF Barber Shop admin.", "info")
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    pending_count = Appointment.query.filter_by(
        status=AppointmentStatus.PENDING
    ).count()
    today_date_obj = datetime.now(timezone.utc).date()
    today_count = Appointment.query.filter(
        Appointment.time_slot.has(TimeSlot.date == today_date_obj)
    ).count()
    week_later = today_date_obj + timedelta(days=7)
    upcoming_appointments = (
        Appointment.query.join(TimeSlot)
        .filter(TimeSlot.date >= today_date_obj, TimeSlot.date <= week_later)
        .order_by(TimeSlot.date.asc())
        .limit(5)
        .all()
    )
    service_counts_query = (
        db.session.query(
            Service.name,
            db.func.count(appointment_services.c.service_id).label("count"),
        )
        .join(appointment_services, Service.id == appointment_services.c.service_id)
        .group_by(Service.name)
        .all()
    )
    service_counts = service_counts_query if service_counts_query else []
    current_datetime_obj = datetime.now(timezone.utc)
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).limit(10).all()
    return render_template(
        "admin_dashboard.html",
        title="ODF Barber Shop - Admin Dashboard",
        pending_count=pending_count,
        today_count=today_count,
        upcoming_appointments=upcoming_appointments,
        service_counts=service_counts,
        admin_name=session.get("admin_name", "Administrator"),
        now=current_datetime_obj,
        feedbacks=feedbacks,
    )

@app.route("/admin/timeslots")
@login_required
def admin_timeslots():
    page = request.args.get("page", 1, type=int)
    per_page = 21
    date_filter_str = request.args.get("date_filter")
    query = TimeSlot.query.order_by(TimeSlot.date.asc(), TimeSlot.period.asc())
    if date_filter_str:
        try:
            date_filter = datetime.strptime(date_filter_str, '%Y-%m-%d').date()
            query = query.filter(TimeSlot.date == date_filter)
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "warning")
            date_filter_str = None
    else:
        today = datetime.now(timezone.utc).date()
        query = query.filter(TimeSlot.date >= today)
    timeslots_page = query.paginate(page=page, per_page=per_page, error_out=False)
    barbers = Barber.query.filter_by(is_active=True).all()
    current_datetime_obj = datetime.now(timezone.utc)
    return render_template(
        "admin_timeslots.html",
        title="Manage Time Slots",
        timeslots_page=timeslots_page,
        barbers=barbers,
        date_filter=date_filter_str,
        admin_name=session.get("admin_name", "Administrator"),
        now=current_datetime_obj
    )

@app.route("/admin/timeslot/<int:timeslot_id>/toggle", methods=["POST"])
@login_required
def toggle_timeslot_availability(timeslot_id):
    slot = TimeSlot.query.get_or_404(timeslot_id)
    if slot.is_available and slot.current_appointments > 0:
        flash(f"Warning: Slot for {slot.date.strftime('%b %d')} has {slot.current_appointments} appointment(s). They will remain but the slot will not be bookable.", "warning")
    try:
        slot.is_available = not slot.is_available
        db.session.commit()
        status = "Available" if slot.is_available else "Unavailable"
        flash(f"Time slot marked as {status}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating time slot: {str(e)}", "danger")
    return redirect(request.referrer or url_for('admin_timeslots'))

@app.route("/admin/timeslots/generate", methods=["POST"])
@login_required
def generate_new_timeslots():
    try:
        generate_time_slots(days_ahead=14)
        flash("Successfully generated new time slots for the next 14 days.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while generating time slots: {str(e)}", "danger")
    return redirect(url_for('admin_timeslots'))

@app.route("/admin/timeslot/add", methods=["POST"])
@login_required
def add_timeslot():
    try:
        date_str = request.form.get("date")
        period_str = request.form.get("period")
        barber_id = int(request.form.get("barber_id"))
        max_appointments = int(request.form.get("max_appointments", 2))
        
        # Validate date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Validate period
        try:
            period = TimeSlotPeriod[period_str]
        except KeyError:
            flash("Invalid time period.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Validate barber
        barber = Barber.query.get(barber_id)
        if not barber or not barber.is_active:
            flash("Invalid or inactive barber selected.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Check if timeslot already exists
        existing_slot = TimeSlot.query.filter_by(
            date=date, period=period, barber_id=barber_id
        ).first()
        if existing_slot:
            flash(f"A timeslot for {date.strftime('%B %d, %Y')} - {period.value} with {barber.name} already exists.", "warning")
            return redirect(url_for('admin_timeslots'))
        
        # Create new timeslot
        new_timeslot = TimeSlot(
            date=date,
            period=period,
            barber_id=barber_id,
            is_available=True,
            max_appointments=max_appointments,
            current_appointments=0
        )
        
        db.session.add(new_timeslot)
        db.session.commit()
        flash(f"Successfully added timeslot for {date.strftime('%B %d, %Y')} - {period.value}.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding timeslot: {str(e)}", "danger")
    
    return redirect(url_for('admin_timeslots'))

@app.route("/admin/timeslot/<int:timeslot_id>/edit", methods=["POST"])
@login_required
def edit_timeslot(timeslot_id):
    timeslot = TimeSlot.query.get_or_404(timeslot_id)
    
    try:
        date_str = request.form.get("date")
        period_str = request.form.get("period")
        barber_id = int(request.form.get("barber_id"))
        max_appointments = int(request.form.get("max_appointments", 2))
        
        # Validate date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Validate period
        try:
            period = TimeSlotPeriod[period_str]
        except KeyError:
            flash("Invalid time period.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Validate barber
        barber = Barber.query.get(barber_id)
        if not barber or not barber.is_active:
            flash("Invalid or inactive barber selected.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Validate max appointments
        if max_appointments < timeslot.current_appointments:
            flash(f"Cannot set max appointments to {max_appointments}. There are already {timeslot.current_appointments} appointments booked.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        # Check if another timeslot exists with the new values (unless it's the same timeslot)
        existing_slot = TimeSlot.query.filter_by(
            date=date, period=period, barber_id=barber_id
        ).filter(TimeSlot.id != timeslot_id).first()
        if existing_slot:
            flash(f"A timeslot for {date.strftime('%B %d, %Y')} - {period.value} with {barber.name} already exists.", "warning")
            return redirect(url_for('admin_timeslots'))
        
        # Update timeslot
        timeslot.date = date
        timeslot.period = period
        timeslot.barber_id = barber_id
        timeslot.max_appointments = max_appointments
        
        db.session.commit()
        flash(f"Successfully updated timeslot for {date.strftime('%B %d, %Y')} - {period.value}.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating timeslot: {str(e)}", "danger")
    
    return redirect(url_for('admin_timeslots'))

@app.route("/admin/timeslot/<int:timeslot_id>/delete", methods=["POST"])
@login_required
def delete_timeslot(timeslot_id):
    timeslot = TimeSlot.query.get_or_404(timeslot_id)
    
    try:
        # Check if there are any appointments
        if timeslot.current_appointments > 0:
            flash(f"Cannot delete timeslot. There are {timeslot.current_appointments} appointment(s) booked for this slot.", "danger")
            return redirect(url_for('admin_timeslots'))
        
        date_str = timeslot.date.strftime('%B %d, %Y')
        period_str = timeslot.period.value
        
        db.session.delete(timeslot)
        db.session.commit()
        flash(f"Successfully deleted timeslot for {date_str} - {period_str}.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting timeslot: {str(e)}", "danger")
    
    return redirect(url_for('admin_timeslots'))

@app.route("/admin/appointments")
@login_required
def admin_view_appointments():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    status_filter = request.args.get("status", "all")
    query = Appointment.query.join(TimeSlot).order_by(
        TimeSlot.date.asc(), Appointment.submitted_at.asc()
    )
    if status_filter != "all" and hasattr(AppointmentStatus, status_filter.upper()):
        status_enum = getattr(AppointmentStatus, status_filter.upper())
        query = query.filter(Appointment.status == status_enum)
    appointments_page = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "admin_appointments.html",
        title="ODF Barber Shop - Manage Appointments",
        appointments_page=appointments_page,
        current_status_filter=status_filter,
        status_options=AppointmentStatus,
        admin_name=session.get("admin_name", "Administrator"),
    )

@app.route("/admin/appointment/<int:appointment_id>/status", methods=["POST"])
@login_required
def update_appointment_status(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status_str = request.form.get("status")
    try:
        new_status = getattr(AppointmentStatus, new_status_str.upper())
        appointment.update_status(new_status)
        db.session.commit()
        flash(
            f"ODF Barber Shop appointment #{appointment.id} status updated to {new_status.value.capitalize()}.",
            "success",
        )
    except (AttributeError, ValueError) as e:
        flash("Invalid status update requested.", "warning")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating status for appointment {appointment_id}: {e}")
        flash(f"Error updating status: {str(e)}", "danger")
    return redirect(
        url_for(
            "admin_view_appointments",
            page=request.args.get("page", 1),
            status=request.args.get("filter_status", "all"),
        )
    )

@app.route("/admin/appointment/delete/<int:appointment_id>", methods=["POST"])
@login_required
def delete_appointment(appointment_id):
    appointment_to_delete = Appointment.query.get_or_404(appointment_id)
    try:
        db.session.delete(appointment_to_delete)
        db.session.commit()
        flash(
            f"ODF Barber Shop appointment #{appointment_id} deleted successfully.",
            "success",
        )
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting ODF appointment {appointment_id}: {e}")
        flash(f"Error deleting appointment: {str(e)}", "danger")
    return redirect(url_for("admin_view_appointments"))

@app.route("/admin/barbers")
@login_required
def admin_barbers():
    barbers = Barber.query.all()
    return render_template(
        "admin_barbers.html",
        title="ODF Barber Shop - Manage Barbers",
        barbers=barbers,
        admin_name=session.get("admin_name", "Administrator"),
    )

@app.route("/admin/services")
@login_required
def admin_services():
    services = Service.query.order_by(Service.name).all()
    return render_template(
        "admin_services.html",
        title="ODF Barber Shop - Manage Services",
        services=services,
        admin_name=session.get("admin_name", "Administrator"),
    )

@app.route("/admin/service/<int:service_id>", methods=["GET", "POST"])
@app.route("/admin/service/new", methods=["GET", "POST"])
@login_required
def admin_edit_service(service_id=None):
    if service_id:
        service = Service.query.get_or_404(service_id)
        form_title = "Edit Service"
    else:
        service = Service()
        form_title = "Add New Service"
    if request.method == "POST":
        try:
            service.name = request.form.get("name")
            service.description = request.form.get("description")
            service.price = float(request.form.get("price"))
            service.duration_minutes = int(request.form.get("duration_minutes"))
            service.is_active = "is_active" in request.form
            if not service_id:
                db.session.add(service)
            db.session.commit()
            flash(f'Service "{service.name}" has been saved successfully.', "success")
            return redirect(url_for("admin_services"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving service: {str(e)}", "danger")
    return render_template(
        "admin_edit_service.html",
        title=f"ODF Barber Shop - {form_title}",
        service=service,
        form_title=form_title,
        admin_name=session.get("admin_name", "Administrator"),
    )

@app.route("/admin/service/<int:service_id>/toggle", methods=["POST"])
@login_required
def toggle_service_status(service_id):
    service = Service.query.get_or_404(service_id)
    try:
        service.is_active = not service.is_active
        db.session.commit()
        status = "activated" if service.is_active else "deactivated"
        flash(f'Service "{service.name}" has been {status}.', "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error toggling service status: {str(e)}", "danger")
    return redirect(url_for("admin_services"))

@app.route("/admin/barber/<int:barber_id>", methods=["GET", "POST"])
@app.route("/admin/barber/new", methods=["GET", "POST"])
@login_required
def edit_barber(barber_id=None):
    if barber_id:
        barber = Barber.query.get_or_404(barber_id)
        form_title = "Edit Barber"
    else:
        barber = Barber()
        form_title = "Add New Barber"
    if request.method == "POST":
        barber.name = request.form.get("name")
        barber.email = request.form.get("email")
        barber.phone = request.form.get("phone")
        barber.is_master = bool(request.form.get("is_master"))
        barber.is_active = bool(request.form.get("is_active"))
        barber.bio = request.form.get("bio")
        file = request.files.get("profile_image")
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(app.root_path, "static", "images")
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            barber.profile_image = filename
        if not barber_id:
            db.session.add(barber)
        db.session.commit()
        flash(f'Barber "{barber.name}" has been saved.', "success")
        return redirect(url_for("admin_barbers"))
    return render_template(
        "admin_edit_barber.html",
        barber=barber,
        form_title=form_title,
        admin_name=session.get("admin_name", "Administrator"),
    )

@app.route("/admin/barber/<int:barber_id>/toggle", methods=["POST"])
@login_required
def toggle_barber(barber_id):
    barber = Barber.query.get_or_404(barber_id)
    try:
        barber.is_active = not barber.is_active
        db.session.commit()
        status = "activated" if barber.is_active else "deactivated"
        flash(f'Barber "{barber.name}" has been {status}.', "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error toggling barber status: {str(e)}", "danger")
    return redirect(url_for("admin_barbers"))

@app.route("/admin/barber/<int:barber_id>/delete", methods=["POST"])
@login_required
def delete_barber(barber_id):
    barber = Barber.query.get_or_404(barber_id)
    try:
        db.session.delete(barber)
        db.session.commit()
        flash(f'Barber "{barber.name}" has been deleted.', "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting barber: {str(e)}", "danger")
    return redirect(url_for("admin_barbers"))

@app.route("/admin/feedback")
@login_required
def admin_feedback():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template("admin_feedback.html", feedbacks=feedbacks)

@app.route("/admin/feedback/delete/<int:feedback_id>", methods=["POST"])
@login_required
def delete_feedback(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)
    try:
        db.session.delete(feedback)
        db.session.commit()
        flash("Feedback deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting feedback: {str(e)}", "danger")
    return redirect(url_for("admin_feedback"))

    # This goes in SECTION 4 of your app.py

def create_default_services():
    """Create default services if they don't exist."""
    print("--- Checking for and creating default services... ---")
    default_services = [
        {"name": "Classic Cut", "description": "A timeless haircut...", "price": 15000.00, "duration_minutes": 45},
        {"name": "Beard Sculpt & Trim", "description": "Precise beard shaping...", "price": 10000.00, "duration_minutes": 30},
        {"name": "Executive Fade", "description": "A precision fade...", "price": 20000.00, "duration_minutes": 60},
        {"name": "Braids & Locks", "description": "Professional styling...", "price": 35000.00, "duration_minutes": 90},
        {"name": "Senior Cut", "description": "Specialized haircuts...", "price": 12000.00, "duration_minutes": 30},
        {"name": "Facials", "description": "Rejuvenating facial treatments...", "price": 15000.00, "duration_minutes": 45},
    ]
    for service_data in default_services:
        if not Service.query.filter_by(name=service_data["name"]).first():
            service = Service(**service_data, is_active=True)
            db.session.add(service)
            print(f"Adding service: {service.name}")
    db.session.commit()

def create_default_barber():
    """Create default barber if no barbers exist."""
    print("--- Checking for and creating default barber... ---")
    if Barber.query.count() == 0:
        barber = Barber(name="ODF Master Barber", email="barber@example.com", phone="+1234567890", bio="Experienced master barber.", is_active=True)
        db.session.add(barber)
        db.session.commit()
        print("Default barber created.")
        return barber
    return Barber.query.filter_by(is_active=True).first()

def generate_time_slots(days_ahead=14):
    """Generate time slots for the specified number of days ahead."""
    print("--- Generating time slots... ---")
    barber = Barber.query.filter_by(is_active=True).first()
    if not barber:
        print("Cannot generate time slots: No active barber found.")
        return
    today = datetime.now(timezone.utc).date()
    for i in range(days_ahead):
        current_date = today + timedelta(days=i)
        for period in TimeSlotPeriod:
            if not TimeSlot.query.filter_by(date=current_date, period=period, barber_id=barber.id).first():
                time_slot = TimeSlot(date=current_date, period=period, is_available=True, max_appointments=2, barber_id=barber.id)
                db.session.add(time_slot)
    db.session.commit()
    print("Time slots generated.")
    # This also goes in SECTION 4 of your app.py

@app.cli.command("seed-db")
def seed_db_command():
    """Seeds the database with default data."""
    print("--- Seeding database with initial data... ---")
    create_default_services()
    default_barber = create_default_barber()
    if default_barber:
        generate_time_slots()
    print("--- Database seeding complete. ---")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Starting ODF Barber Shop System (Local Development) ---")
    with app.app_context():
        if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
            db_path_local_check = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
            if not os.path.exists(db_path_local_check):
                print(f"--- ODF SQLite database file not found at {db_path_local_check}. Creating tables... ---")
                db.create_all()
                # Optionally, call your default data creation functions here
                # create_default_services()
                # default_barber = create_default_barber()
                # if default_barber:
                #     generate_time_slots()
                print(f"--- ODF SQLite database and tables created with default data. ---")
            else:
                print(f"--- ODF SQLite database file already exists at {db_path_local_check}. ---")
                db.create_all()
    port = int(os.environ.get("PORT", 5050))
    print(f"--- Running ODF Barber Shop App locally on http://0.0.0.0:{port} ---")
    app.run(debug=True, host="0.0.0.0", port=port)
