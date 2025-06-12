# ODF Barber Shop - Flask Web Application

A modern web application for managing barber shop appointments, services, and customer interactions.

## Features

- **Appointment Booking System**: Customers can book appointments online
- **Service Management**: Manage different barber services and pricing
- **Barber Management**: Add and manage barber profiles
- **Admin Dashboard**: Administrative interface for managing the business
- **Time Slot Management**: Flexible scheduling system
- **Customer Feedback**: Collect and manage customer reviews

## Deployment on Render

This application is configured for easy deployment on Render.com.

### Prerequisites

- GitHub account
- Render account (free tier available)

### Deployment Steps

1. **Push to GitHub**: Ensure your code is pushed to your GitHub repository

2. **Connect to Render**:
   - Go to [Render.com](https://render.com)
   - Sign up/Login with your GitHub account
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file

3. **Environment Variables**:
   The following environment variables will be automatically configured:
   - `DATABASE_URL`: PostgreSQL connection string (auto-generated)
   - `FLASK_SECRET_KEY`: Secure secret key (auto-generated)
   - `ADMIN_USERNAME`: Admin login username (set to 'odf_admin')
   - `ADMIN_PASSWORD`: Admin login password (auto-generated)

4. **Database Setup**:
   - Render will automatically create a PostgreSQL database
   - Database tables will be created on first deployment
   - Default services, barbers, and time slots will be populated

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Dayzidee/[your-repo-name]
   cd [your-repo-name]
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

5. **Initialize database**:
   ```bash
   python init_db.py
   ```

6. **Run the application**:
   ```bash
   python app.py
   ```

## Project Structure

```
├── app.py              # Main Flask application
├── models.py           # Database models
├── init_db.py          # Database initialization script
├── requirements.txt    # Python dependencies
├── Procfile           # Render deployment configuration
├── render.yaml        # Render Blueprint configuration
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore file
├── static/            # Static files (CSS, JS, images)
├── templates/         # HTML templates
└── venv/              # Virtual environment (not in repo)
```

## Technologies Used

- **Backend**: Flask (Python)
- **Database**: PostgreSQL (production), SQLite (development)
- **ORM**: SQLAlchemy
- **Deployment**: Render.com
- **Frontend**: HTML, CSS, JavaScript

## Support

For issues or questions about deployment, please check the Render documentation or create an issue in this repository.

