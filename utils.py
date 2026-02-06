"""
Utility functions for Salon Shop Backend
- Password hashing
- Email sending (SMTP)
- Date/Time helpers
- Price calculation
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import bcrypt
from bson import ObjectId


# ==================== PASSWORD UTILITIES ====================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ==================== EMAIL UTILITIES ====================

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an email using SMTP
    Returns True if successful, False otherwise
    """
    try:
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        from_email = os.getenv('SMTP_FROM_EMAIL')
        from_name = os.getenv('SMTP_FROM_NAME', 'Salon Shop')

        if not all([smtp_server, smtp_username, smtp_password, from_email]):
            print("SMTP configuration incomplete")
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = to_email

        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        print(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


def send_booking_confirmation_email(customer_email: str, customer_name: str, 
                                     service_title: str, booking_date: str, 
                                     booking_time: str, final_price: float,
                                     booking_id: str) -> bool:
    """Send booking confirmation email to customer"""
    subject = "Booking Confirmation - Salon Shop"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .booking-details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Booking Confirmation</h1>
            </div>
            <div class="content">
                <p>Dear {customer_name},</p>
                <p>Thank you for booking with us! Your appointment has been successfully created.</p>
                
                <div class="booking-details">
                    <h3>Booking Details:</h3>
                    <p><strong>Booking ID:</strong> {booking_id}</p>
                    <p><strong>Service:</strong> {service_title}</p>
                    <p><strong>Date:</strong> {booking_date}</p>
                    <p><strong>Time:</strong> {booking_time}</p>
                    <p><strong>Total Price:</strong> ${final_price:.2f}</p>
                    <p><strong>Status:</strong> Pending (Awaiting Confirmation)</p>
                </div>
                
                <p>We will confirm your booking shortly. You will receive another email once confirmed.</p>
                <p>If you need to cancel, please do so before your appointment time.</p>
            </div>
            <div class="footer">
                <p>Salon Shop - Your Beauty Destination</p>
                <p>This is an automated message. Please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(customer_email, subject, html_content)


def send_booking_cancellation_email(customer_email: str, customer_name: str,
                                     service_title: str, booking_date: str,
                                     booking_time: str, booking_id: str,
                                     cancelled_by: str = "customer") -> bool:
    """Send booking cancellation email to customer"""
    subject = "Booking Cancelled - Salon Shop"
    
    if cancelled_by == "admin":
        cancel_message = "Your booking has been cancelled by the salon administrator."
    else:
        cancel_message = "Your booking has been successfully cancelled as per your request."
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #f44336; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .booking-details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Booking Cancelled</h1>
            </div>
            <div class="content">
                <p>Dear {customer_name},</p>
                <p>{cancel_message}</p>
                
                <div class="booking-details">
                    <h3>Cancelled Booking Details:</h3>
                    <p><strong>Booking ID:</strong> {booking_id}</p>
                    <p><strong>Service:</strong> {service_title}</p>
                    <p><strong>Date:</strong> {booking_date}</p>
                    <p><strong>Time:</strong> {booking_time}</p>
                </div>
                
                <p>We hope to see you again soon. Feel free to book another appointment at your convenience.</p>
            </div>
            <div class="footer">
                <p>Salon Shop - Your Beauty Destination</p>
                <p>This is an automated message. Please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(customer_email, subject, html_content)


def send_booking_status_update_email(customer_email: str, customer_name: str,
                                      service_title: str, booking_date: str,
                                      booking_time: str, booking_id: str,
                                      new_status: str) -> bool:
    """Send booking status update email to customer"""
    
    status_colors = {
        "Confirmed": "#4CAF50",
        "Completed": "#2196F3",
        "Cancelled": "#f44336",
        "Pending": "#FF9800"
    }
    
    status_messages = {
        "Confirmed": "Great news! Your booking has been confirmed by the salon.",
        "Completed": "Your service has been marked as completed. Thank you for visiting us!",
        "Cancelled": "Your booking has been cancelled by the salon administrator.",
        "Pending": "Your booking status has been updated to pending."
    }
    
    color = status_colors.get(new_status, "#333")
    message = status_messages.get(new_status, f"Your booking status has been updated to {new_status}.")
    
    subject = f"Booking {new_status} - Salon Shop"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .booking-details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .status-badge {{ display: inline-block; padding: 5px 15px; background-color: {color}; color: white; border-radius: 20px; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Booking Status Update</h1>
            </div>
            <div class="content">
                <p>Dear {customer_name},</p>
                <p>{message}</p>
                
                <div class="booking-details">
                    <h3>Booking Details:</h3>
                    <p><strong>Booking ID:</strong> {booking_id}</p>
                    <p><strong>Service:</strong> {service_title}</p>
                    <p><strong>Date:</strong> {booking_date}</p>
                    <p><strong>Time:</strong> {booking_time}</p>
                    <p><strong>New Status:</strong> <span class="status-badge">{new_status}</span></p>
                </div>
                
                <p>If you have any questions, please contact us.</p>
            </div>
            <div class="footer">
                <p>Salon Shop - Your Beauty Destination</p>
                <p>This is an automated message. Please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(customer_email, subject, html_content)


# ==================== DATE/TIME UTILITIES ====================

def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object (format: YYYY-MM-DD)"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def parse_time(time_str: str) -> datetime:
    """Parse time string to datetime object (format: HH:MM)"""
    return datetime.strptime(time_str, "%H:%M")


def combine_date_time(date_str: str, time_str: str) -> datetime:
    """Combine date and time strings into a single datetime object"""
    date_obj = parse_date(date_str)
    time_obj = parse_time(time_str)
    return datetime.combine(date_obj.date(), time_obj.time())


def is_future_datetime(date_str: str, time_str: str) -> bool:
    """Check if the given date and time is in the future"""
    booking_datetime = combine_date_time(date_str, time_str)
    return booking_datetime > datetime.now()


def format_date(date_obj: datetime) -> str:
    """Format datetime object to readable date string"""
    return date_obj.strftime("%B %d, %Y")


def format_time(time_str: str) -> str:
    """Format time string to 12-hour format"""
    time_obj = parse_time(time_str)
    return time_obj.strftime("%I:%M %p")


# ==================== PRICE CALCULATION UTILITIES ====================

def calculate_discounted_price(base_price: float, discount_type: str, 
                                discount_value: float) -> float:
    """
    Calculate the discounted price based on discount type
    - percentage: discount_value is the percentage off (e.g., 20 for 20% off)
    - flat: discount_value is the flat amount to subtract
    """
    if discount_type == "percentage":
        discount_amount = base_price * (discount_value / 100)
        final_price = base_price - discount_amount
    elif discount_type == "flat":
        final_price = base_price - discount_value
    else:
        final_price = base_price
    
    # Ensure price is not negative
    return max(0, round(final_price, 2))


def is_discount_active(start_date: str, end_date: str) -> bool:
    """Check if a discount is currently active based on dates"""
    today = datetime.now().date()
    start = parse_date(start_date).date()
    end = parse_date(end_date).date()
    return start <= today <= end


# ==================== MONGODB UTILITIES ====================

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [serialize_doc(item) if isinstance(item, dict) else 
                          str(item) if isinstance(item, ObjectId) else item 
                          for item in value]
        else:
            result[key] = value
    return result


def serialize_docs(docs: list) -> list:
    """Convert list of MongoDB documents to JSON-serializable format"""
    return [serialize_doc(doc) for doc in docs]


# ==================== VALIDATION UTILITIES ====================

def validate_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_required_fields(data: dict, required_fields: list) -> tuple:
    """
    Validate that all required fields are present in the data
    Returns (is_valid, missing_fields)
    """
    missing = [field for field in required_fields if field not in data or data[field] is None or data[field] == ""]
    return (len(missing) == 0, missing)


def validate_time_slot(time_str: str) -> bool:
    """Validate time slot format (HH:MM)"""
    import re
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return re.match(pattern, time_str) is not None


def validate_date_format(date_str: str) -> bool:
    """Validate date format (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
