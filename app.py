from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta, date as DDate  # For date objects
# In app.py
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
# ... other imports ...
from models import (
    db,
    Appointment,
    Service,
    TimeSlot,
    Barber,
    AppointmentStatus,
    TimeSlotPeriod,
    appointment_services,
    Feedback,
)  # <-- ADD appointment_services HERE


# ... rest of your app.py ...
import os

from functools import wraps
import json  # For storing multiple services
import logging
from models import (
    db,
    Appointment,
    Service,
    TimeSlot,
    Barber,
    AppointmentStatus,
    TimeSlotPeriod,
)
from dotenv import load_dotenv

load_dotenv()

# --- Initialize Flask App ---
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Optional: silence a deprecation warning
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY' , 'default-dev-key')
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)  # Session timeout')

db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialize migrate

# --- Configuration ---
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY", "odf_barber_shop_secret_key_CHANGE_ME_IN_PROD"
)
app.config["SESSION_COOKIE_NAME"] = "odf_session"  # ODF-specific session cookie name

# --- DEFINE BASE_DIR AT THE TOP ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Define the path for file uploads
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME", "odf_admin"
)  # ODF-specific admin username
ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD", "odf_secure_password_123"
)  # ODF-specific admin password


# Session timeout (30 minutes)
app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # in seconds

# --- Database Configuration (Your existing logic is good) ---
print("--- STARTING DATABASE CONFIGURATION ---")
DATABASE_URL_FROM_ENV = os.environ.get("DATABASE_URL")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

print(f"DATABASE_URL_FROM_ENV raw value: '{DATABASE_URL_FROM_ENV}'")

if DATABASE_URL_FROM_ENV and DATABASE_URL_FROM_ENV.startswith("postgresql://"):
    print("--- Condition for PostgreSQL (postgresql://) MET ---")
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL_FROM_ENV
    print(
        f"--- USING POSTGRESQL DATABASE. Configured URI (partial): {app.config['SQLALCHEMY_DATABASE_URI'][:40]}... ---"
    )
elif DATABASE_URL_FROM_ENV and DATABASE_URL_FROM_ENV.startswith("postgres://"):
    print(
        "--- Condition for PostgreSQL (postgres://) MET, will correct to postgresql:// ---"
    )
    corrected_db_url = DATABASE_URL_FROM_ENV.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = corrected_db_url
    print(
        f"--- USING POSTGRESQL DATABASE (corrected). Configured URI (partial): {app.config['SQLALCHEMY_DATABASE_URI'][:40]}... ---"
    )
else:
    print(
        f"--- Condition for PostgreSQL NOT MET. Falling back to SQLite. DATABASE_URL_FROM_ENV was: '{DATABASE_URL_FROM_ENV}' ---"
    )
    DB_NAME = "odf_barber_shop.db"  # ODF-specific database name
    DB_PATH = os.path.join(BASE_DIR, DB_NAME)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    print(f"--- Using local SQLite database (fallback): {DB_PATH} ---")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Initialize SQLAlchemy ---
db.init_app(app)
print("--- FINISHED DATABASE CONFIGURATION & EXTENSIONS INIT ---")


# --- Service and Barber Default Data ---
def create_default_services():
    """Create default services if they don't exist."""
    default_services = [
        {
            "name": "Classic Cut",
            "description": "A timeless haircut tailored to your preference, finished with a sharp lineup and style.",
            "price": 15000.00,  # 15,000 Naira
            "duration_minutes": 45,
        },
        {
            "name": "Beard Sculpt & Trim",
            "description": "Precise beard shaping and maintenance for a well-groomed appearance.",
            "price": 10000.00,  # 10,000 Naira
            "duration_minutes": 30,
        },
        {
            "name": "Executive Fade",
            "description": "A precision fade blended seamlessly, combined with expert styling on top for a modern look.",
            "price": 20000.00,  # 20,000 Naira
            "duration_minutes": 60,
        },
        {
            "name": "Braids & Locks",
            "description": "Professional styling and maintenance for braids and locks.",
            "price": 35000.00,  # 35,000 Naira
            "duration_minutes": 90,
        },
        {
            "name": "Senior Cut",
            "description": "Specialized haircuts for senior clients.",
            "price": 12000.00,  # 12,000 Naira
            "duration_minutes": 30,
        },
        {
            "name": "Facials",
            "description": "Rejuvenating facial treatments for skin health and appearance.",
            "price": 15000.00,  # 15,000 Naira
            "duration_minutes": 45,
        },
    ]

    for service_data in default_services:
        # Check if service already exists
        existing_service = Service.query.filter_by(name=service_data["name"]).first()
        if not existing_service:
            try:
                service = Service(
                    name=service_data["name"],
                    description=service_data["description"],
                    price=service_data["price"],
                    duration_minutes=service_data["duration_minutes"],
                    is_active=True,
                )
                db.session.add(service)
                print(f"Created default service: {service_data['name']}")
            except Exception as e:
                db.session.rollback()
                print(
                    f"Error creating default service {service_data['name']}: {str(e)}"
                )

    try:
        db.session.commit()
        print("All default services committed to database")
    except Exception as e:
        db.session.rollback()
        print(f"Error committing default services: {str(e)}")


def create_default_barber():
    """Create default barber if no barbers exist."""
    if Barber.query.count() == 0:
        try:
            barber = Barber(
                name="ODF Master Barber",
                email="williamskent25@gmail.com",
                phone="+234 911 468 3483",
                bio="With over 7 years of experience in crafting sharp looks and providing top-notch grooming services.",
                profile_image="default_barber.jpg",
                is_active=True,
            )
            db.session.add(barber)
            db.session.commit()
            print(f"Created default barber: ODF Master Barber")
            return barber
        except Exception as e:
            db.session.rollback()
            print(f"Error creating default barber: {str(e)}")
            return None
    else:
        # Return the first active barber
        return Barber.query.filter_by(is_active=True).first()


def generate_time_slots(days_ahead=14):
    """Generate time slots for the specified number of days ahead."""
    barber = Barber.query.filter_by(is_active=True).first()
    if not barber:
        print("Cannot generate time slots: No active barber found")
        return

    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=days_ahead)

    # Get existing time slots to avoid duplicates
    existing_slots = {}
    for slot in TimeSlot.query.filter(
        TimeSlot.date >= today,
        TimeSlot.date <= end_date,
        TimeSlot.barber_id == barber.id,
    ).all():
        key = f"{slot.date}_{slot.period.value}_{slot.barber_id}"
        existing_slots[key] = True

    # Generate slots for each day
    slots_added = 0
    current_date = today
    while current_date <= end_date:
        # Skip generating slots for past dates
        if current_date < today:
            current_date += timedelta(days=1)
            continue

        # Generate slots for all periods (morning, afternoon, evening)
        for period in TimeSlotPeriod:
            slot_key = f"{current_date}_{period.value}_{barber.id}"

            # Skip if slot already exists
            if slot_key in existing_slots:
                continue

            # Create the time slot
            try:
                time_slot = TimeSlot(
                    date=current_date,
                    period=period,
                    is_available=True,
                    max_appointments=2,  # Allow 2 appointments per slot
                    current_appointments=0,
                    barber_id=barber.id,
                )
                db.session.add(time_slot)
                slots_added += 1

                # Commit in batches to avoid excessive database load
                if slots_added % 20 == 0:
                    db.session.commit()

            except Exception as e:
                db.session.rollback()
                print(
                    f"Error creating time slot for {current_date}, {period.value}: {str(e)}"
                )

        # Move to next day
        current_date += timedelta(days=1)

    # Commit any remaining slots
    if slots_added % 20 != 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error committing time slots: {str(e)}")

    print(f"Generated {slots_added} new time slots")


# --- Flask CLI command to initialize DB ---
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and initializes with default data."""
    print(
        "--- Attempting to initialize ODF Barber Shop database via 'flask init-db' command ---"
    )
    print(
        f"--- 'init-db' using DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')[:40]}... ---"
    )
    with app.app_context():
        db.create_all()  # This will create tables for ALL models defined

        # Initialize with default data
        create_default_services()
        default_barber = create_default_barber()

        # Generate time slots if barber exists
        if default_barber:
            generate_time_slots()

    print(
        "--- 'init-db' command: Initialized the ODF Barber Shop database with tables and default data. ---"
    )


# --- Admin Authentication Decorator (remains the same) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated_function


# --- Routes ---

# OLD Feedback Form Route (Comment out or remove)
# @app.route('/', methods=['GET', 'POST'])
# def feedback_form():
# ... old feedback logic ...
#     return render_template('index.html') # This was your feedback form


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
    # Return the index.html file for the homepage
    return render_template(
        "index.html", title="ODF Barber Shop - Expert Barbers at Your Service"
    )


@app.route("/portfolio")
def portfolio():
    # OLD WAY (if portfolio.html was in the root or static):
    # return send_file("portfolio.html", mimetype="text/html")

    # NEW WAY (since portfolio.html is now in the 'templates' folder):
    return render_template("portfolio.html", title="ODF Barber Shop - Portfolio")

    return send_file("portfolio.html", mimetype="text/html")


# NEW Appointment Booking Route
@app.route("/book", methods=["GET", "POST"])
def book_appointment():
    # Get available services and time slots for the form
    active_services = Service.query.filter_by(is_active=True).all()

    # Get available time slots for the next 30 days
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

    # Format time slots for display
    time_slot_options = []
    for slot in available_time_slots:
        # Format date as "Day, Month Date, Year"
        formatted_date = slot.date.strftime("%A, %B %d, %Y")
        time_slot_options.append(
            {
                "id": slot.id,
                "text": f"{formatted_date} - {slot.period.value}",
                "date": slot.date.isoformat(),
                "period": slot.period.value,
            }
        )

    # Get active barbers
    active_barbers = Barber.query.filter_by(is_active=True).all()

    if request.method == "POST":
        # Validate required fields
        required_fields = {
            "fullName": "Full Name",
            "phone": "Phone Number",
            "email": "Email Address",
            # 'servicesNeeded[]': "Service(s) Required", # Handled by getlist
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

        service_ids = request.form.getlist(
            "servicesNeeded[]"
        )  # Get selected service IDs
        if not service_ids:
            missing.append("Service(s) Required")

        if missing:
            flash(
                f"Please fill out all required fields: {', '.join(missing)}.", "danger"
            )
            # Pass existing form data back to template to pre-fill
            form_data_for_template = {
                key: request.form.get(key) for key in request.form
            }
            form_data_for_template["servicesNeeded"] = (
                service_ids  # Pass list for multi-select
            )
            return render_template(
                "book_appointment.html",
                title="Book Appointment",
                form_data=form_data_for_template,
                services=active_services,
                time_slots=time_slot_options,
                barbers=active_barbers,
            )

        try:
            # Get the selected time slot
            time_slot_id = int(request.form.get("timeSlot"))
            time_slot = TimeSlot.query.get_or_404(time_slot_id)

            # Verify time slot is still available
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

            # Get selected services
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

            # Get selected barber
            barber_id = int(request.form.get("barber"))
            barber = Barber.query.get_or_404(barber_id)

            # Create new appointment
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

            # Add selected services to the appointment
            for service in selected_services:
                new_appointment.services.append(service)

            # Calculate estimated duration and price
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

    # GET request - show the form
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
    """Thank you page after successful appointment booking."""
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
            session.permanent = True  # Use the permanent session lifetime
            session["admin_logged_in"] = True
            session["admin_name"] = (
                "ODF Administrator"  # Store admin name for templates
            )
            flash("Logged in successfully to ODF Barber Shop admin!", "success")
            return redirect(url_for("admin_dashboard"))  # Changed redirect
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


# Admin Dashboard
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    pending_count = Appointment.query.filter_by(
        status=AppointmentStatus.PENDING
    ).count()
    today_date_obj = datetime.now(timezone.utc).date()  # Use a more descriptive name
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

    service_counts_query = (  # Renamed for clarity before assignment
        db.session.query(
            Service.name,
            db.func.count(appointment_services.c.service_id).label("count"),
        )
        .join(appointment_services, Service.id == appointment_services.c.service_id)
        .group_by(Service.name)
        .all()
    )
    service_counts = (
        service_counts_query if service_counts_query else []
    )  # Ensure it's a list

    # --- THIS IS THE CRUCIAL PART FOR THE 'now' VARIABLE ---
    current_datetime_obj = datetime.now(timezone.utc)  # Create the datetime object

    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).limit(10).all()
    return render_template(
        "admin_dashboard.html",
        title="ODF Barber Shop - Admin Dashboard",  # Restored original title
        pending_count=pending_count,
        today_count=today_count,
        upcoming_appointments=upcoming_appointments,
        service_counts=service_counts,
        admin_name=session.get("admin_name", "Administrator"),  # Restored default
        now=current_datetime_obj,  # Pass the datetime object as 'now'
        feedbacks=feedbacks,
    )


# In app.py

# ... (other routes) ...

# In app.py

# ... (other imports) ...

# Find your old admin_timeslots function and replace it with this new one.
# It now handles filtering and pagination.

@app.route("/admin/timeslots")
@login_required
def admin_timeslots():
    page = request.args.get("page", 1, type=int)
    per_page = 21  # Show 21 slots, which fits nicely in a 3-column grid
    
    # Get the date from the filter form
    date_filter_str = request.args.get("date_filter")
    
    query = TimeSlot.query.order_by(TimeSlot.date.asc(), TimeSlot.period.asc())

    if date_filter_str:
        try:
            date_filter = datetime.strptime(date_filter_str, '%Y-%m-%d').date()
            query = query.filter(TimeSlot.date == date_filter)
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "warning")
            date_filter_str = None # Reset on error
    else:
        # By default, show slots from today onwards
        today = datetime.now(timezone.utc).date()
        query = query.filter(TimeSlot.date >= today)


    timeslots_page = query.paginate(page=page, per_page=per_page, error_out=False)

    current_datetime_obj = datetime.now(timezone.utc)
    
    return render_template(
        "admin_timeslots.html",
        title="Manage Time Slots",
        timeslots_page=timeslots_page,
        date_filter=date_filter_str, # Pass the filter string back to the template
        admin_name=session.get("admin_name", "Administrator"),
        now=current_datetime_obj
    )


# ADD THIS NEW ROUTE for toggling a slot's availability
@app.route("/admin/timeslot/<int:timeslot_id>/toggle", methods=["POST"])
@login_required
def toggle_timeslot_availability(timeslot_id):
    slot = TimeSlot.query.get_or_404(timeslot_id)
    
    # Safety check: warn if making a slot with appointments unavailable
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

    # Redirect back to the page the user was on
    return redirect(request.referrer or url_for('admin_timeslots'))

# ADD THIS NEW ROUTE for generating slots from the UI
@app.route("/admin/timeslots/generate", methods=["POST"])
@login_required
def generate_new_timeslots():
    try:
        # You can customize the days_ahead value if you want
        generate_time_slots(days_ahead=14)
        flash("Successfully generated new time slots for the next 14 days.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while generating time slots: {str(e)}", "danger")
        
    return redirect(url_for('admin_timeslots'))

# ... (rest of your app.py) ...

# ... (rest of your app.py) ...


# Admin Appointments
@app.route("/admin/appointments")  # Renamed route
@login_required
def admin_view_appointments():
    page = request.args.get("page", 1, type=int)
    per_page = 10  # Or however many you want per page

    # Filter by status
    status_filter = request.args.get(
        "status", "all"
    )  # e.g., /admin/appointments?status=pending

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


# Route to update appointment status
@app.route("/admin/appointment/<int:appointment_id>/status", methods=["POST"])
@login_required
def update_appointment_status(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status_str = request.form.get("status")

    try:
        # Convert string status to enum
        new_status = getattr(AppointmentStatus, new_status_str.upper())

        # Use the update_status method to properly set timestamps
        appointment.update_status(new_status)

        db.session.commit()
        flash(
            f"ODF Barber Shop appointment #{appointment.id} status updated to {new_status.value.capitalize()}.",
            "success",
        )
        # TODO: Implement email notification to customer with ODF branding
        # send_status_notification(appointment, new_status)
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


# Delete appointment
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


# Manage Barbers
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


# Manage Services
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


# Add/Edit Service
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

            if not service_id:  # New service
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


# Toggle Service Status
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


# Add/Edit Barber
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

        # Handle profile image upload
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


# Toggle Barber Status
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


# Delete barber
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


# Admin Feedback
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


# --- Main Execution (for local development only) ---
if __name__ == "__main__":
    print("--- Starting ODF Barber Shop System (Local Development) ---")
    with app.app_context():
        if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
            db_path_local_check = app.config["SQLALCHEMY_DATABASE_URI"].replace(
                "sqlite:///", ""
            )
            if not os.path.exists(db_path_local_check):
                print(
                    f"--- ODF SQLite database file not found at {db_path_local_check}. Creating tables... ---"
                )
                db.create_all()
                # Initialize with default data
                create_default_services()
                default_barber = create_default_barber()

                # Generate time slots if barber exists
                if default_barber:
                    generate_time_slots()
                print(
                    f"--- ODF SQLite database and tables created with default data. ---"
                )
            else:
                print(
                    f"--- ODF SQLite database file already exists at {db_path_local_check}. ---"
                )
                # If you added new tables/columns and the DB file exists,
                # db.create_all() won't modify existing tables.
                # You might need migrations (e.g., Flask-Migrate) for complex changes,
                # or for dev, delete the .db file and let it recreate.
                db.create_all()  # This will add any new tables/columns without affecting existing data

    port = int(os.environ.get("PORT", 5050))  # ODF-specific port
    print(f"--- Running ODF Barber Shop App locally on http://0.0.0.0:{port} ---")
    app.run(debug=True, host="0.0.0.0", port=port)
