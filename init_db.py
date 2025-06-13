#!/usr/bin/env python3
"""
Database initialization script for ODF Barber Shop
This script creates all database tables and populates them with default data.
"""

import os
from app import app, db
from models import Barber, Service, TimeSlot, AppointmentStatus, TimeSlotPeriod
from datetime import datetime, timezone

def init_database():
    """Initialize the database with tables and default data."""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created successfully!")
        
        # Import and run the default data creation functions from app.py
        from app import create_default_services, create_default_barber, generate_time_slots
        
        print("Creating default services...")
        create_default_services()
        
        print("Creating default barber...")
        default_barber = create_default_barber()
        
        print("Generating time slots...")
        if default_barber:
            generate_time_slots(days_ahead=30)  # Generate time slots for the next 30 days
        
        print("Database initialization completed successfully!")

if __name__ == "__main__":
    init_database()

# init_db.py
from app import app, db
with app.app_context():
    db.create_all()
print("Database tables created.")