from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from sqlalchemy import event, text, Enum, UniqueConstraint, CheckConstraint
import enum
import json
import re

db = SQLAlchemy()

# Define enum types for better data consistency
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

# Association table for many-to-many relationship between appointments and services
appointment_services = db.Table(
    'odf_appointment_services',
    db.Column('appointment_id', db.Integer, db.ForeignKey('odf_appointments.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('odf_services.id'), primary_key=True)
)

class Barber(db.Model):
    """Model for barbers who provide services."""
    __tablename__ = 'odf_barbers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    profile_image = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    appointments = db.relationship('Appointment', back_populates='barber')
    time_slots = db.relationship('TimeSlot', back_populates='barber')
    
    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email address")
        return email
        
    @validates('phone')
    def validate_phone(self, key, phone):
        # Basic phone validation - allow for international format
        if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
            raise ValueError("Invalid phone number format")
        return phone
    
    def __repr__(self):
        return f'<Barber {self.name}>'

class Service(db.Model):
    """Model for services offered by the barber shop."""
    __tablename__ = 'odf_services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Decimal for currency
    duration_minutes = db.Column(db.Integer, nullable=False)  # Duration in minutes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc))
    
    # Validates minimum price and duration
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
    
    def __repr__(self):
        return f'<Service {self.name} - ${self.price}>'

class TimeSlot(db.Model):
    """Model for available time slots for appointments."""
    __tablename__ = 'odf_time_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    period = db.Column(Enum(TimeSlotPeriod), nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    max_appointments = db.Column(db.Integer, default=1, nullable=False)
    current_appointments = db.Column(db.Integer, default=0, nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey('odf_barbers.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc))
    
    # Add a unique constraint to ensure a barber can't have duplicate slots
    __table_args__ = (
        UniqueConstraint('date', 'period', 'barber_id', name='_date_period_barber_uc'),
        CheckConstraint('current_appointments <= max_appointments', name='check_appointment_limit'),
    )
    
    # Relationships
    barber = db.relationship('Barber', back_populates='time_slots')
    appointments = db.relationship('Appointment', back_populates='time_slot')
    
    @property
    def is_fully_booked(self):
        return self.current_appointments >= self.max_appointments
    
    @validates('date')
    def validate_date(self, key, date):
        # Ensure date is not in the past
        if date < datetime.now(timezone.utc).date():
            raise ValueError("Cannot create time slots for past dates")
        return date
    
    @validates('current_appointments')
    def validate_current_appointments(self, key, value):
        if value > self.max_appointments:
            raise ValueError("Current appointments cannot exceed maximum allowed")
        return value
    
    def __repr__(self):
        return f'<TimeSlot {self.date} {self.period.value} - Barber: {self.barber_id}>'

class Appointment(db.Model):
    """Model for customer appointments."""
    __tablename__ = 'odf_appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    # Customer information
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False, index=True)
    customer_email = db.Column(db.String(120), nullable=False, index=True)
    is_first_time_customer = db.Column(db.Boolean, default=True)
    
    # Appointment details
    time_slot_id = db.Column(db.Integer, db.ForeignKey('odf_time_slots.id'), nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey('odf_barbers.id'), nullable=False)
    status = db.Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False, index=True)
    
    # Location information
    address_street = db.Column(db.String(200), nullable=False)
    address_city = db.Column(db.String(100), nullable=False)
    address_postal_code = db.Column(db.String(20), nullable=False)
    address_gmaps_link = db.Column(db.String(500), nullable=True)
    
    # Additional information
    notes = db.Column(db.Text, nullable=True)
    estimated_duration = db.Column(db.Integer, nullable=True)  # Total minutes based on services
    estimated_price = db.Column(db.Numeric(10, 2), nullable=True)  # Total price based on services
    
    # Tracking
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc))
    confirmed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
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
        # Basic phone validation - allow for international format
        if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
            raise ValueError("Invalid phone number format")
        return phone
    
    @validates('address_postal_code')
    def validate_postal_code(self, key, postal_code):
        # Basic postal code validation for Nigeria
        if not re.match(r"^\d{6}$", postal_code):
            # This is a simple validation - adjust based on your needs
            raise ValueError("Invalid postal code format")
        return postal_code
    
    def __repr__(self):
        return f'<Appointment {self.id} for {self.customer_name} on {self.time_slot.date} ({self.status.value})>'
    
    def update_status(self, new_status):
        """Update appointment status and set appropriate timestamp."""
        self.status = new_status
        
        # Set timestamp based on status
        if new_status == AppointmentStatus.CONFIRMED:
            self.confirmed_at = datetime.now(timezone.utc)
        elif new_status == AppointmentStatus.COMPLETED:
            self.completed_at = datetime.now(timezone.utc)
        elif new_status == AppointmentStatus.CANCELLED:
            self.cancelled_at = datetime.now(timezone.utc)
            
        return self
    
    def calculate_totals(self):
        """Calculate the estimated duration and price based on services."""
        total_duration = sum(service.duration_minutes for service in self.services)
        total_price = sum(float(service.price) for service in self.services)
        
        self.estimated_duration = total_duration
        self.estimated_price = total_price
        
        return self

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Event listeners


@event.listens_for(Appointment, 'after_insert')
def appointment_after_insert(mapper, connection, target):
    # Increment the current_appointments count for the time slot
    stmt = text(
        "UPDATE odf_time_slots SET current_appointments = current_appointments + 1 "
        "WHERE id = :slot_id"
    )
    connection.execute(stmt, {"slot_id": target.time_slot_id})
@event.listens_for(Appointment, 'after_delete')
def appointment_after_delete(mapper, connection, target):
    # This SQL statement is compatible with both PostgreSQL and SQLite.
    # It uses a CASE statement to ensure the value never drops below 0.
    stmt = text(
        "UPDATE odf_time_slots "
        "SET current_appointments = CASE "
        "    WHEN current_appointments > 0 THEN current_appointments - 1 "
        "    ELSE 0 "
        "END "
        "WHERE id = :slot_id"
    )
    connection.execute(stmt, {"slot_id": target.time_slot_id})