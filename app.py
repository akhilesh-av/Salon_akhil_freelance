"""
Salon Shop Backend - Flask Application
Main application file containing all API endpoints
"""

import os
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote_plus

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, 
    get_jwt_identity, get_jwt
)
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from bson import ObjectId
from dotenv import load_dotenv

from utils import (
    hash_password, verify_password,
    # send_booking_confirmation_email, send_booking_cancellation_email,
    # send_booking_status_update_email,  # Email functionality commented out - will be added later
    calculate_discounted_price, is_discount_active,
    is_future_datetime, format_date, format_time,
    serialize_doc, serialize_docs,
    validate_email, validate_required_fields,
    validate_time_slot, validate_date_format
)

# Load environment variables
load_dotenv()

# ==================== APP CONFIGURATION ====================

app = Flask(__name__)

# CORS configuration - Allow all origins and ports (no CORS errors)
# This allows requests from any origin, any port (localhost, production, etc.)
CORS(
    app,
    origins="*",  # Allow all origins - no CORS errors
    allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    supports_credentials=False,  # Must be False when using wildcard * (browser security rule)
    expose_headers=['Content-Type', 'Authorization'],
    max_age=600
)

# Flask configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-jwt-secret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(
    seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))
)

# Initialize JWT
jwt = JWTManager(app)

# ==================== DATABASE CONNECTION ====================

mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/salon_db')
db_name = os.getenv('MONGO_DB_NAME', 'salon_db')

# Parse database name from URI if not explicitly set
# For MongoDB Atlas (mongodb+srv://), database name might be in the path
if not db_name or db_name == 'salon_db':
    # Try to extract from URI
    uri_parts = mongo_uri.split('//')
    if len(uri_parts) > 1:
        path_part = uri_parts[-1].split('@')[-1]  # Get part after @
        if '/' in path_part:
            db_from_uri = path_part.split('/')[1].split('?')[0]  # Get database name, remove query params
            if db_from_uri and db_from_uri not in ['', '?']:
                db_name = db_from_uri

# Ensure connection string has proper SSL/TLS parameters for Atlas
# Add retryWrites and other recommended parameters if not present
if 'mongodb+srv://' in mongo_uri:
    # Check if retryWrites is already in the URI
    if 'retryWrites' not in mongo_uri:
        separator = '&' if '?' in mongo_uri else '?'
        mongo_uri = f"{mongo_uri}{separator}retryWrites=true&w=majority"

# Create MongoDB client with connection options
try:
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=5000,  # 5 second timeout
        connectTimeoutMS=10000,  # 10 second connection timeout
        socketTimeoutMS=20000,  # 20 second socket timeout
        retryWrites=True
    )
except Exception as e:
    print(f"✗ Error creating MongoDB client: {e}")
    raise

# Get database
db = client.get_database(db_name)

# Test connection (non-blocking - app will start but DB operations will fail if connection fails)
try:
    client.admin.command('ping')
    print(f"✓ Successfully connected to MongoDB database: {db_name}")
except ServerSelectionTimeoutError as e:
    print(f"⚠ Warning: Failed to connect to MongoDB (Server Selection Timeout)")
    print("⚠ The application will start, but database operations will fail.")
    print("\n⚠ Troubleshooting steps:")
    print("   1. Check your MongoDB Atlas connection string in .env file")
    print("   2. Whitelist your IP address in MongoDB Atlas:")
    print("      - Go to MongoDB Atlas → Network Access → Add IP Address")
    print("      - Add '0.0.0.0/0' for testing (allow all IPs) or your specific IP")
    print("   3. Verify your database user credentials are correct")
    print("   4. Check if your password contains special characters that need URL encoding")
    print(f"\n   Connection string format: mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority")
    # Don't raise - let the app start, it will fail when trying to use DB
except Exception as e:
    error_msg = str(e)
    if 'SSL' in error_msg or 'TLS' in error_msg:
        print(f"⚠ Warning: SSL/TLS connection error")
        print("⚠ This usually means:")
        print("   1. Your IP address is not whitelisted in MongoDB Atlas Network Access")
        print("   2. Network/firewall is blocking the connection")
        print("   3. MongoDB Atlas cluster is not accessible")
    else:
        print(f"⚠ Warning: Failed to connect to MongoDB: {error_msg}")
    print("⚠ The application will start, but database operations will fail.")
    # Don't raise - let the app start, it will fail when trying to use DB

# Collections
users_collection = db['users']
services_collection = db['services']
discounts_collection = db['discounts']
bookings_collection = db['bookings']
staff_collection = db['staff']
attendance_collection = db['attendance']

# Create indexes
users_collection.create_index('email', unique=True, sparse=True)
users_collection.create_index('username', unique=True, sparse=True)
bookings_collection.create_index([('service_id', 1), ('date', 1), ('time_slot', 1)], unique=True)
# One attendance record per staff per day (prevents multiple check-ins same day)
attendance_collection.create_index([('staff_id', 1), ('date', 1)], unique=True)


# ==================== HELPER FUNCTIONS ====================

def admin_required(fn):
    """Decorator to check if user is admin"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def customer_required(fn):
    """Decorator to check if user is customer"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'customer':
            return jsonify({'error': 'Customer access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def get_active_discount(service_id: str) -> dict:
    """Get active discount for a service"""
    today = datetime.now().strftime("%Y-%m-%d")
    discount = discounts_collection.find_one({
        'service_id': service_id,
        'is_active': True,
        'start_date': {'$lte': today},
        'end_date': {'$gte': today}
    })
    return discount


def calculate_booking_price(service: dict) -> tuple:
    """Calculate final price for a booking, returns (final_price, discount_applied)"""
    base_price = service['base_price']
    service_id = str(service['_id'])
    
    discount = get_active_discount(service_id)
    if discount:
        final_price = calculate_discounted_price(
            base_price, 
            discount['discount_type'], 
            discount['discount_value']
        )
        return (final_price, True)
    
    return (base_price, False)


def init_admin():
    """Initialize default admin user if not exists"""
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@salonshop.com')
    
    existing_admin = users_collection.find_one({'role': 'admin'})
    if not existing_admin:
        admin_user = {
            'username': admin_username,
            'email': admin_email,
            'password': hash_password(admin_password),
            'role': 'admin',
            'created_at': datetime.utcnow()
        }
        users_collection.insert_one(admin_user)
        print(f"Admin user created: {admin_username}")


# ==================== AUTHENTICATION APIS ====================

@app.route('/api/auth/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    data = request.get_json()
    
    is_valid, missing = validate_required_fields(data, ['username', 'password'])
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    admin = users_collection.find_one({
        'username': data['username'],
        'role': 'admin'
    })
    
    if not admin or not verify_password(data['password'], admin['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    access_token = create_access_token(
        identity=str(admin['_id']),
        additional_claims={'role': 'admin', 'username': admin['username']}
    )
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'user': {
            'id': str(admin['_id']),
            'username': admin['username'],
            'email': admin['email'],
            'role': 'admin'
        }
    }), 200


@app.route('/api/auth/customer/register', methods=['POST'])
def customer_register():
    """Customer registration endpoint"""
    data = request.get_json()
    
    is_valid, missing = validate_required_fields(data, ['name', 'email', 'password'])
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    if not validate_email(data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    if len(data['password']) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if email already exists
    existing_user = users_collection.find_one({'email': data['email']})
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 409
    
    customer = {
        'name': data['name'],
        'email': data['email'].lower(),
        'password': hash_password(data['password']),
        'phone': data.get('phone', ''),
        'role': 'customer',
        'created_at': datetime.utcnow()
    }
    
    try:
        result = users_collection.insert_one(customer)
        
        access_token = create_access_token(
            identity=str(result.inserted_id),
            additional_claims={'role': 'customer', 'email': customer['email']}
        )
        
        return jsonify({
            'message': 'Registration successful',
            'access_token': access_token,
            'user': {
                'id': str(result.inserted_id),
                'name': customer['name'],
                'email': customer['email'],
                'role': 'customer'
            }
        }), 201
        
    except DuplicateKeyError:
        return jsonify({'error': 'Email already registered'}), 409


@app.route('/api/auth/customer/login', methods=['POST'])
def customer_login():
    """Customer login endpoint"""
    data = request.get_json()
    
    is_valid, missing = validate_required_fields(data, ['email', 'password'])
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    customer = users_collection.find_one({
        'email': data['email'].lower(),
        'role': 'customer'
    })
    
    if not customer or not verify_password(data['password'], customer['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    access_token = create_access_token(
        identity=str(customer['_id']),
        additional_claims={'role': 'customer', 'email': customer['email']}
    )
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'user': {
            'id': str(customer['_id']),
            'name': customer['name'],
            'email': customer['email'],
            'role': 'customer'
        }
    }), 200


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current authenticated user"""
    user_id = get_jwt_identity()
    claims = get_jwt()
    
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user_data = {
        'id': str(user['_id']),
        'email': user.get('email'),
        'role': claims.get('role')
    }
    
    if claims.get('role') == 'admin':
        user_data['username'] = user.get('username')
    else:
        user_data['name'] = user.get('name')
        user_data['phone'] = user.get('phone', '')
    
    return jsonify({'user': user_data}), 200


# ==================== SERVICE MANAGEMENT APIS (Admin) ====================

@app.route('/api/services', methods=['POST'])
@admin_required
def create_service():
    """Create a new service (Admin only)"""
    data = request.get_json()
    
    required_fields = ['title', 'description', 'base_price', 'duration']
    is_valid, missing = validate_required_fields(data, required_fields)
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    if data['base_price'] <= 0:
        return jsonify({'error': 'Base price must be greater than 0'}), 400
    
    if data['duration'] <= 0:
        return jsonify({'error': 'Duration must be greater than 0'}), 400
    
    service = {
        'title': data['title'],
        'description': data['description'],
        'base_price': float(data['base_price']),
        'discounted_price': data.get('discounted_price'),
        'duration': int(data['duration']),
        'status': data.get('status', 'Active'),
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    result = services_collection.insert_one(service)
    service['_id'] = result.inserted_id
    
    return jsonify({
        'message': 'Service created successfully',
        'service': serialize_doc(service)
    }), 201


@app.route('/api/services', methods=['GET'])
def get_all_services():
    """Get all services (Public)"""
    status_filter = request.args.get('status')
    
    query = {}
    if status_filter:
        query['status'] = status_filter
    
    services = list(services_collection.find(query).sort('created_at', -1))
    
    # Add discount information to each service
    for service in services:
        discount = get_active_discount(str(service['_id']))
        if discount:
            service['has_discount'] = True
            service['discount_type'] = discount['discount_type']
            service['discount_value'] = discount['discount_value']
            service['final_price'] = calculate_discounted_price(
                service['base_price'],
                discount['discount_type'],
                discount['discount_value']
            )
        else:
            service['has_discount'] = False
            service['final_price'] = service['base_price']
    
    return jsonify({
        'services': serialize_docs(services),
        'total': len(services)
    }), 200


@app.route('/api/services/<service_id>', methods=['GET'])
def get_service(service_id):
    """Get a single service by ID (Public)"""
    try:
        service = services_collection.find_one({'_id': ObjectId(service_id)})
    except:
        return jsonify({'error': 'Invalid service ID'}), 400
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    # Add discount information
    discount = get_active_discount(service_id)
    if discount:
        service['has_discount'] = True
        service['discount_type'] = discount['discount_type']
        service['discount_value'] = discount['discount_value']
        service['final_price'] = calculate_discounted_price(
            service['base_price'],
            discount['discount_type'],
            discount['discount_value']
        )
    else:
        service['has_discount'] = False
        service['final_price'] = service['base_price']
    
    return jsonify({'service': serialize_doc(service)}), 200


@app.route('/api/services/<service_id>', methods=['PUT'])
@admin_required
def update_service(service_id):
    """Update a service (Admin only)"""
    data = request.get_json()
    
    try:
        service = services_collection.find_one({'_id': ObjectId(service_id)})
    except:
        return jsonify({'error': 'Invalid service ID'}), 400
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    update_data = {'updated_at': datetime.utcnow()}
    
    allowed_fields = ['title', 'description', 'base_price', 'discounted_price', 'duration', 'status']
    for field in allowed_fields:
        if field in data:
            if field == 'base_price' and data[field] <= 0:
                return jsonify({'error': 'Base price must be greater than 0'}), 400
            if field == 'duration' and data[field] <= 0:
                return jsonify({'error': 'Duration must be greater than 0'}), 400
            update_data[field] = data[field]
    
    services_collection.update_one(
        {'_id': ObjectId(service_id)},
        {'$set': update_data}
    )
    
    updated_service = services_collection.find_one({'_id': ObjectId(service_id)})
    
    return jsonify({
        'message': 'Service updated successfully',
        'service': serialize_doc(updated_service)
    }), 200


@app.route('/api/services/<service_id>', methods=['DELETE'])
@admin_required
def delete_service(service_id):
    """Delete or deactivate a service (Admin only)"""
    try:
        service = services_collection.find_one({'_id': ObjectId(service_id)})
    except:
        return jsonify({'error': 'Invalid service ID'}), 400
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    # Check if service has any pending/confirmed bookings
    active_bookings = bookings_collection.count_documents({
        'service_id': service_id,
        'status': {'$in': ['Pending', 'Confirmed']}
    })
    
    if active_bookings > 0:
        # Deactivate instead of delete
        services_collection.update_one(
            {'_id': ObjectId(service_id)},
            {'$set': {'status': 'Inactive', 'updated_at': datetime.utcnow()}}
        )
        return jsonify({
            'message': 'Service deactivated (has active bookings)',
            'deactivated': True
        }), 200
    
    # Delete the service
    services_collection.delete_one({'_id': ObjectId(service_id)})
    
    # Also delete associated discounts
    discounts_collection.delete_many({'service_id': service_id})
    
    return jsonify({'message': 'Service deleted successfully'}), 200


# ==================== DISCOUNT MANAGEMENT APIS (Admin) ====================

@app.route('/api/discounts', methods=['POST'])
@admin_required
def create_discount():
    """Create a discount for a service (Admin only)"""
    data = request.get_json()
    
    required_fields = ['service_id', 'discount_type', 'discount_value', 'start_date', 'end_date']
    is_valid, missing = validate_required_fields(data, required_fields)
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    # Validate service exists
    try:
        service = services_collection.find_one({'_id': ObjectId(data['service_id'])})
    except:
        return jsonify({'error': 'Invalid service ID'}), 400
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    # Validate discount type
    if data['discount_type'] not in ['percentage', 'flat']:
        return jsonify({'error': 'Discount type must be "percentage" or "flat"'}), 400
    
    # Validate discount value
    if data['discount_value'] <= 0:
        return jsonify({'error': 'Discount value must be greater than 0'}), 400
    
    if data['discount_type'] == 'percentage' and data['discount_value'] > 100:
        return jsonify({'error': 'Percentage discount cannot exceed 100%'}), 400
    
    # Validate dates
    if not validate_date_format(data['start_date']) or not validate_date_format(data['end_date']):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    if data['start_date'] > data['end_date']:
        return jsonify({'error': 'Start date must be before end date'}), 400
    
    # Check for existing active discount on the same service with overlapping dates
    existing_discount = discounts_collection.find_one({
        'service_id': data['service_id'],
        'is_active': True,
        '$or': [
            {'start_date': {'$lte': data['end_date']}, 'end_date': {'$gte': data['start_date']}}
        ]
    })
    
    if existing_discount:
        return jsonify({'error': 'An active discount already exists for this service in the specified date range'}), 409
    
    discount = {
        'service_id': data['service_id'],
        'discount_type': data['discount_type'],
        'discount_value': float(data['discount_value']),
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'is_active': True,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    result = discounts_collection.insert_one(discount)
    discount['_id'] = result.inserted_id
    
    return jsonify({
        'message': 'Discount created successfully',
        'discount': serialize_doc(discount)
    }), 201


@app.route('/api/discounts', methods=['GET'])
@admin_required
def get_all_discounts():
    """Get all discounts (Admin only)"""
    service_id = request.args.get('service_id')
    is_active = request.args.get('is_active')
    
    query = {}
    if service_id:
        query['service_id'] = service_id
    if is_active is not None:
        query['is_active'] = is_active.lower() == 'true'
    
    discounts = list(discounts_collection.find(query).sort('created_at', -1))
    
    # Add service information to each discount
    for discount in discounts:
        service = services_collection.find_one({'_id': ObjectId(discount['service_id'])})
        if service:
            discount['service_title'] = service['title']
    
    return jsonify({
        'discounts': serialize_docs(discounts),
        'total': len(discounts)
    }), 200


@app.route('/api/discounts/<discount_id>', methods=['GET'])
@admin_required
def get_discount(discount_id):
    """Get a single discount by ID (Admin only)"""
    try:
        discount = discounts_collection.find_one({'_id': ObjectId(discount_id)})
    except:
        return jsonify({'error': 'Invalid discount ID'}), 400
    
    if not discount:
        return jsonify({'error': 'Discount not found'}), 404
    
    # Add service information
    service = services_collection.find_one({'_id': ObjectId(discount['service_id'])})
    if service:
        discount['service_title'] = service['title']
    
    return jsonify({'discount': serialize_doc(discount)}), 200


@app.route('/api/discounts/<discount_id>', methods=['PUT'])
@admin_required
def update_discount(discount_id):
    """Update a discount (Admin only)"""
    data = request.get_json()
    
    try:
        discount = discounts_collection.find_one({'_id': ObjectId(discount_id)})
    except:
        return jsonify({'error': 'Invalid discount ID'}), 400
    
    if not discount:
        return jsonify({'error': 'Discount not found'}), 404
    
    update_data = {'updated_at': datetime.utcnow()}
    
    if 'discount_type' in data:
        if data['discount_type'] not in ['percentage', 'flat']:
            return jsonify({'error': 'Discount type must be "percentage" or "flat"'}), 400
        update_data['discount_type'] = data['discount_type']
    
    if 'discount_value' in data:
        if data['discount_value'] <= 0:
            return jsonify({'error': 'Discount value must be greater than 0'}), 400
        discount_type = data.get('discount_type', discount['discount_type'])
        if discount_type == 'percentage' and data['discount_value'] > 100:
            return jsonify({'error': 'Percentage discount cannot exceed 100%'}), 400
        update_data['discount_value'] = float(data['discount_value'])
    
    if 'start_date' in data:
        if not validate_date_format(data['start_date']):
            return jsonify({'error': 'Invalid start date format. Use YYYY-MM-DD'}), 400
        update_data['start_date'] = data['start_date']
    
    if 'end_date' in data:
        if not validate_date_format(data['end_date']):
            return jsonify({'error': 'Invalid end date format. Use YYYY-MM-DD'}), 400
        update_data['end_date'] = data['end_date']
    
    if 'is_active' in data:
        update_data['is_active'] = bool(data['is_active'])
    
    # Validate date range if both dates are being updated or present
    start_date = update_data.get('start_date', discount['start_date'])
    end_date = update_data.get('end_date', discount['end_date'])
    if start_date > end_date:
        return jsonify({'error': 'Start date must be before end date'}), 400
    
    discounts_collection.update_one(
        {'_id': ObjectId(discount_id)},
        {'$set': update_data}
    )
    
    updated_discount = discounts_collection.find_one({'_id': ObjectId(discount_id)})
    
    return jsonify({
        'message': 'Discount updated successfully',
        'discount': serialize_doc(updated_discount)
    }), 200


@app.route('/api/discounts/<discount_id>', methods=['DELETE'])
@admin_required
def delete_discount(discount_id):
    """Delete or disable a discount (Admin only)"""
    try:
        discount = discounts_collection.find_one({'_id': ObjectId(discount_id)})
    except:
        return jsonify({'error': 'Invalid discount ID'}), 400
    
    if not discount:
        return jsonify({'error': 'Discount not found'}), 404
    
    # Disable the discount instead of deleting
    discounts_collection.update_one(
        {'_id': ObjectId(discount_id)},
        {'$set': {'is_active': False, 'updated_at': datetime.utcnow()}}
    )
    
    return jsonify({'message': 'Discount disabled successfully'}), 200


# ==================== STAFF MANAGEMENT APIS (Admin) ====================

@app.route('/api/admin/staff', methods=['POST'])
@admin_required
def create_staff():
    """Create a new staff member (Admin only)"""
    data = request.get_json()
    
    required_fields = ['full_name', 'phone', 'role']
    is_valid, missing = validate_required_fields(data, required_fields)
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    if data['role'] not in ['stylist', 'receptionist', 'manager', 'therapist']:
        return jsonify({'error': 'Invalid role. Use: stylist, receptionist, manager, therapist'}), 400
    
    staff = {
        'full_name': data['full_name'],
        'email': data.get('email', ''),
        'phone': data['phone'],
        'role': data['role'],
        'working_days': data.get('working_days', []),  # e.g. ["Monday", "Tuesday", ...]
        'shift_timings': data.get('shift_timings', {}),  # e.g. {"start": "09:00", "end": "17:00"}
        'status': data.get('status', 'Active'),
        'is_deleted': False,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    if staff['status'] not in ['Active', 'Inactive']:
        return jsonify({'error': 'Status must be Active or Inactive'}), 400
    
    result = staff_collection.insert_one(staff)
    staff['_id'] = result.inserted_id
    staff['staff_id'] = str(result.inserted_id)
    
    return jsonify({
        'message': 'Staff created successfully',
        'staff': serialize_doc(staff)
    }), 201


@app.route('/api/admin/staff', methods=['GET'])
@admin_required
def get_all_staff():
    """Get all staff members (Admin only). Excludes soft-deleted by default."""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
    status_filter = request.args.get('status')
    
    query = {'is_deleted': False} if not include_deleted else {}
    if status_filter:
        query['status'] = status_filter
    if not include_deleted and not status_filter and not include_inactive:
        query['status'] = 'Active'
    
    staff_list = list(staff_collection.find(query).sort('created_at', -1))
    
    for s in staff_list:
        s['staff_id'] = str(s['_id'])
    
    return jsonify({
        'staff': serialize_docs(staff_list),
        'total': len(staff_list)
    }), 200


@app.route('/api/admin/staff/<staff_id>', methods=['GET'])
@admin_required
def get_staff(staff_id):
    """Get a single staff member by ID (Admin only)"""
    try:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id), 'is_deleted': False})
    except:
        return jsonify({'error': 'Invalid staff ID'}), 400
    
    if not staff:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
        if not staff:
            return jsonify({'error': 'Staff not found'}), 404
        if staff.get('is_deleted'):
            return jsonify({'error': 'Staff record has been deactivated'}), 410
    
    staff['staff_id'] = str(staff['_id'])
    
    return jsonify({'staff': serialize_doc(staff)}), 200


@app.route('/api/admin/staff/<staff_id>', methods=['PUT'])
@admin_required
def update_staff(staff_id):
    """Update a staff member (Admin only)"""
    data = request.get_json()
    
    try:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id), 'is_deleted': False})
    except:
        return jsonify({'error': 'Invalid staff ID'}), 400
    
    if not staff:
        return jsonify({'error': 'Staff not found'}), 404
    
    update_data = {'updated_at': datetime.utcnow()}
    
    allowed_fields = ['full_name', 'email', 'phone', 'role', 'working_days', 'shift_timings', 'status']
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if 'role' in data and data['role'] not in ['stylist', 'receptionist', 'manager', 'therapist']:
        return jsonify({'error': 'Invalid role'}), 400
    if 'status' in data and data['status'] not in ['Active', 'Inactive']:
        return jsonify({'error': 'Status must be Active or Inactive'}), 400
    
    staff_collection.update_one(
        {'_id': ObjectId(staff_id)},
        {'$set': update_data}
    )
    
    updated_staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
    updated_staff['staff_id'] = str(updated_staff['_id'])
    
    return jsonify({
        'message': 'Staff updated successfully',
        'staff': serialize_doc(updated_staff)
    }), 200


@app.route('/api/admin/staff/<staff_id>/deactivate', methods=['PUT'])
@admin_required
def deactivate_staff(staff_id):
    """Soft delete / deactivate a staff member (Admin only)"""
    try:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
    except:
        return jsonify({'error': 'Invalid staff ID'}), 400
    
    if not staff:
        return jsonify({'error': 'Staff not found'}), 404
    
    if staff.get('is_deleted'):
        return jsonify({'message': 'Staff is already deactivated'}), 200
    
    staff_collection.update_one(
        {'_id': ObjectId(staff_id)},
        {'$set': {'is_deleted': True, 'status': 'Inactive', 'updated_at': datetime.utcnow()}}
    )
    
    return jsonify({'message': 'Staff deactivated successfully (soft delete)'}), 200


# ==================== ATTENDANCE MANAGEMENT APIS (Admin) ====================

@app.route('/api/admin/attendance/check-in', methods=['POST'])
@admin_required
def attendance_checkin():
    """Mark check-in for a staff member (Admin only). One check-in per staff per day."""
    data = request.get_json()
    
    is_valid, missing = validate_required_fields(data, ['staff_id', 'date'])
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    if not validate_date_format(data['date']):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    try:
        staff = staff_collection.find_one({'_id': ObjectId(data['staff_id']), 'is_deleted': False})
    except:
        return jsonify({'error': 'Invalid staff ID'}), 400
    
    if not staff:
        return jsonify({'error': 'Staff not found or inactive'}), 404
    
    # Prevent multiple check-ins for same staff on same day
    existing = attendance_collection.find_one({
        'staff_id': data['staff_id'],
        'date': data['date']
    })
    
    if existing:
        return jsonify({'error': 'Check-in already recorded for this staff on this date'}), 409
    
    check_in_time = data.get('check_in_time') or datetime.now().strftime("%H:%M")
    if not validate_time_slot(check_in_time):
        return jsonify({'error': 'Invalid check_in_time format. Use HH:MM'}), 400
    
    attendance = {
        'staff_id': data['staff_id'],
        'staff_name': staff['full_name'],
        'date': data['date'],
        'check_in_time': check_in_time,
        'check_out_time': None,
        'attendance_status': 'Present',
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    result = attendance_collection.insert_one(attendance)
    attendance['_id'] = result.inserted_id
    
    return jsonify({
        'message': 'Check-in recorded successfully',
        'attendance': serialize_doc(attendance)
    }), 201


@app.route('/api/admin/attendance/check-out', methods=['PUT'])
@admin_required
def attendance_checkout():
    """Mark check-out for a staff member (Admin only)"""
    data = request.get_json()
    
    is_valid, missing = validate_required_fields(data, ['staff_id', 'date'])
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    if not validate_date_format(data['date']):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    attendance = attendance_collection.find_one({
        'staff_id': data['staff_id'],
        'date': data['date']
    })
    
    if not attendance:
        return jsonify({'error': 'No check-in record found for this staff on this date'}), 404
    
    check_out_time = data.get('check_out_time') or datetime.now().strftime("%H:%M")
    if not validate_time_slot(check_out_time):
        return jsonify({'error': 'Invalid check_out_time format. Use HH:MM'}), 400
    
    attendance_status = data.get('attendance_status', attendance.get('attendance_status', 'Present'))
    if attendance_status not in ['Present', 'Absent', 'Half-day']:
        return jsonify({'error': 'attendance_status must be Present, Absent, or Half-day'}), 400
    
    attendance_collection.update_one(
        {'_id': attendance['_id']},
        {'$set': {
            'check_out_time': check_out_time,
            'attendance_status': attendance_status,
            'updated_at': datetime.utcnow()
        }}
    )
    
    updated = attendance_collection.find_one({'_id': attendance['_id']})
    
    return jsonify({
        'message': 'Check-out recorded successfully',
        'attendance': serialize_doc(updated)
    }), 200


@app.route('/api/admin/attendance', methods=['GET'])
@admin_required
def get_attendance_list():
    """Get attendance records (Admin only). Filter by date, staff_id, or date range."""
    date_filter = request.args.get('date')
    staff_id = request.args.get('staff_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = {}
    if date_filter:
        query['date'] = date_filter
    if staff_id:
        query['staff_id'] = staff_id
    if start_date and end_date:
        if validate_date_format(start_date) and validate_date_format(end_date):
            query['date'] = {'$gte': start_date, '$lte': end_date}
    
    records = list(attendance_collection.find(query).sort('date', -1))
    
    return jsonify({
        'attendance': serialize_docs(records),
        'total': len(records)
    }), 200


@app.route('/api/admin/attendance/<attendance_id>', methods=['PUT'])
@admin_required
def update_attendance(attendance_id):
    """Update an attendance record (Admin only)"""
    data = request.get_json()
    
    try:
        attendance = attendance_collection.find_one({'_id': ObjectId(attendance_id)})
    except:
        return jsonify({'error': 'Invalid attendance ID'}), 400
    
    if not attendance:
        return jsonify({'error': 'Attendance record not found'}), 404
    
    update_data = {'updated_at': datetime.utcnow()}
    
    if 'check_in_time' in data:
        if not validate_time_slot(data['check_in_time']):
            return jsonify({'error': 'Invalid check_in_time format. Use HH:MM'}), 400
        update_data['check_in_time'] = data['check_in_time']
    
    if 'check_out_time' in data:
        if data['check_out_time'] is not None and not validate_time_slot(data['check_out_time']):
            return jsonify({'error': 'Invalid check_out_time format. Use HH:MM'}), 400
        update_data['check_out_time'] = data['check_out_time']
    
    if 'attendance_status' in data:
        if data['attendance_status'] not in ['Present', 'Absent', 'Half-day']:
            return jsonify({'error': 'attendance_status must be Present, Absent, or Half-day'}), 400
        update_data['attendance_status'] = data['attendance_status']
    
    attendance_collection.update_one(
        {'_id': ObjectId(attendance_id)},
        {'$set': update_data}
    )
    
    updated = attendance_collection.find_one({'_id': ObjectId(attendance_id)})
    
    return jsonify({
        'message': 'Attendance updated successfully',
        'attendance': serialize_doc(updated)
    }), 200


# ==================== BOOKING MANAGEMENT APIS ====================

@app.route('/api/bookings', methods=['POST'])
@customer_required
def create_booking():
    """Create a new booking (Customer only)"""
    data = request.get_json()
    customer_id = get_jwt_identity()
    
    required_fields = ['service_id', 'date', 'time_slot']
    is_valid, missing = validate_required_fields(data, required_fields)
    if not is_valid:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    # Validate date format
    if not validate_date_format(data['date']):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    # Validate time slot format
    if not validate_time_slot(data['time_slot']):
        return jsonify({'error': 'Invalid time slot format. Use HH:MM'}), 400
    
    # Check if booking is for future date/time
    if not is_future_datetime(data['date'], data['time_slot']):
        return jsonify({'error': 'Booking must be for a future date and time'}), 400
    
    # Validate service exists and is active
    try:
        service = services_collection.find_one({'_id': ObjectId(data['service_id'])})
    except:
        return jsonify({'error': 'Invalid service ID'}), 400
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    if service.get('status') != 'Active':
        return jsonify({'error': 'Service is not available'}), 400
    
    # Check for duplicate booking (same service, date, time slot)
    existing_booking = bookings_collection.find_one({
        'service_id': data['service_id'],
        'date': data['date'],
        'time_slot': data['time_slot'],
        'status': {'$nin': ['Cancelled']}
    })
    
    if existing_booking:
        return jsonify({'error': 'This time slot is already booked'}), 409
    
    # Get customer details
    customer = users_collection.find_one({'_id': ObjectId(customer_id)})
    
    # Calculate price
    final_price, discount_applied = calculate_booking_price(service)
    
    booking = {
        'customer_id': customer_id,
        'customer_name': customer['name'],
        'customer_email': customer['email'],
        'service_id': data['service_id'],
        'service_title': service['title'],
        'date': data['date'],
        'time_slot': data['time_slot'],
        'base_price': service['base_price'],
        'final_price': final_price,
        'discount_applied': discount_applied,
        'status': 'Pending',
        'notes': data.get('notes', ''),
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    try:
        result = bookings_collection.insert_one(booking)
        booking['_id'] = result.inserted_id
        
        # Send confirmation email - COMMENTED OUT (will be added later)
        # send_booking_confirmation_email(
        #     customer_email=customer['email'],
        #     customer_name=customer['name'],
        #     service_title=service['title'],
        #     booking_date=format_date(datetime.strptime(data['date'], "%Y-%m-%d")),
        #     booking_time=format_time(data['time_slot']),
        #     final_price=final_price,
        #     booking_id=str(result.inserted_id)
        # )
        
        return jsonify({
            'message': 'Booking created successfully',
            'booking': serialize_doc(booking)
        }), 201
        
    except DuplicateKeyError:
        return jsonify({'error': 'This time slot is already booked'}), 409


@app.route('/api/bookings/my-bookings', methods=['GET'])
@customer_required
def get_customer_bookings():
    """Get all bookings for the logged-in customer"""
    customer_id = get_jwt_identity()
    
    status_filter = request.args.get('status')
    
    query = {'customer_id': customer_id}
    if status_filter:
        query['status'] = status_filter
    
    bookings = list(bookings_collection.find(query).sort('date', -1))
    
    return jsonify({
        'bookings': serialize_docs(bookings),
        'total': len(bookings)
    }), 200


@app.route('/api/bookings/<booking_id>/cancel', methods=['PUT'])
@customer_required
def cancel_booking(booking_id):
    """Cancel a booking (Customer only)"""
    customer_id = get_jwt_identity()
    
    try:
        booking = bookings_collection.find_one({'_id': ObjectId(booking_id)})
    except:
        return jsonify({'error': 'Invalid booking ID'}), 400
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    # Verify booking belongs to the customer
    if booking['customer_id'] != customer_id:
        return jsonify({'error': 'Unauthorized to cancel this booking'}), 403
    
    # Check if booking can be cancelled
    if booking['status'] in ['Cancelled', 'Completed']:
        return jsonify({'error': f'Cannot cancel a {booking["status"].lower()} booking'}), 400
    
    # Check if cancellation is before service time
    if not is_future_datetime(booking['date'], booking['time_slot']):
        return jsonify({'error': 'Cannot cancel past bookings'}), 400
    
    # Update booking status
    bookings_collection.update_one(
        {'_id': ObjectId(booking_id)},
        {'$set': {'status': 'Cancelled', 'updated_at': datetime.utcnow()}}
    )
    
    # Send cancellation email - COMMENTED OUT (will be added later)
    # send_booking_cancellation_email(
    #     customer_email=booking['customer_email'],
    #     customer_name=booking['customer_name'],
    #     service_title=booking['service_title'],
    #     booking_date=format_date(datetime.strptime(booking['date'], "%Y-%m-%d")),
    #     booking_time=format_time(booking['time_slot']),
    #     booking_id=str(booking['_id']),
    #     cancelled_by='customer'
    # )
    
    return jsonify({'message': 'Booking cancelled successfully'}), 200


@app.route('/api/admin/bookings', methods=['GET'])
@admin_required
def get_all_bookings():
    """Get all bookings (Admin only)"""
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    service_id = request.args.get('service_id')
    
    query = {}
    if status_filter:
        query['status'] = status_filter
    if date_filter:
        query['date'] = date_filter
    if service_id:
        query['service_id'] = service_id
    
    bookings = list(bookings_collection.find(query).sort('created_at', -1))
    
    return jsonify({
        'bookings': serialize_docs(bookings),
        'total': len(bookings)
    }), 200


@app.route('/api/admin/bookings/<booking_id>', methods=['GET'])
@admin_required
def get_booking_details(booking_id):
    """Get booking details (Admin only)"""
    try:
        booking = bookings_collection.find_one({'_id': ObjectId(booking_id)})
    except:
        return jsonify({'error': 'Invalid booking ID'}), 400
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    return jsonify({'booking': serialize_doc(booking)}), 200


@app.route('/api/admin/bookings/<booking_id>/status', methods=['PUT'])
@admin_required
def update_booking_status(booking_id):
    """Update booking status (Admin only)"""
    data = request.get_json()
    
    if 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
    
    valid_statuses = ['Pending', 'Confirmed', 'Completed', 'Cancelled']
    if data['status'] not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    try:
        booking = bookings_collection.find_one({'_id': ObjectId(booking_id)})
    except:
        return jsonify({'error': 'Invalid booking ID'}), 400
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    old_status = booking['status']
    new_status = data['status']
    
    # Update booking status
    bookings_collection.update_one(
        {'_id': ObjectId(booking_id)},
        {'$set': {'status': new_status, 'updated_at': datetime.utcnow()}}
    )
    
    # Send status update email if status changed - COMMENTED OUT (will be added later)
    # if old_status != new_status:
    #     send_booking_status_update_email(
    #         customer_email=booking['customer_email'],
    #         customer_name=booking['customer_name'],
    #         service_title=booking['service_title'],
    #         booking_date=format_date(datetime.strptime(booking['date'], "%Y-%m-%d")),
    #         booking_time=format_time(booking['time_slot']),
    #         booking_id=str(booking['_id']),
    #         new_status=new_status
    #     )
    
    return jsonify({
        'message': f'Booking status updated to {new_status}',
        'old_status': old_status,
        'new_status': new_status
    }), 200


# ==================== DASHBOARD APIS (Admin) ====================

@app.route('/api/admin/dashboard/summary', methods=['GET'])
@admin_required
def get_dashboard_summary():
    """
    Single Admin Dashboard Summary API (per requirement 10.1).
    Returns: total bookings, today's bookings, confirmed, completed, cancelled,
             active services count, active staff count.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_bookings = bookings_collection.count_documents({})
    todays_bookings = bookings_collection.count_documents({'date': today})
    confirmed_bookings = bookings_collection.count_documents({'status': 'Confirmed'})
    completed_bookings = bookings_collection.count_documents({'status': 'Completed'})
    cancelled_bookings = bookings_collection.count_documents({'status': 'Cancelled'})
    active_services_count = services_collection.count_documents({'status': 'Active'})
    active_staff_count = staff_collection.count_documents({
        'status': 'Active',
        '$or': [{'is_deleted': False}, {'is_deleted': {'$exists': False}}]
    })
    
    return jsonify({
        'total_bookings': total_bookings,
        'todays_bookings': todays_bookings,
        'confirmed_bookings': confirmed_bookings,
        'completed_bookings': completed_bookings,
        'cancelled_bookings': cancelled_bookings,
        'active_services_count': active_services_count,
        'active_staff_count': active_staff_count
    }), 200


@app.route('/api/admin/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    """Get extended dashboard statistics (Admin only)"""
    # Total counts
    total_customers = users_collection.count_documents({'role': 'customer'})
    total_services = services_collection.count_documents({})
    total_active_services = services_collection.count_documents({'status': 'Active'})
    total_bookings = bookings_collection.count_documents({})
    active_staff_count = staff_collection.count_documents({
        'status': 'Active',
        '$or': [{'is_deleted': False}, {'is_deleted': {'$exists': False}}]
    })
    
    # Booking status breakdown
    pending_bookings = bookings_collection.count_documents({'status': 'Pending'})
    confirmed_bookings = bookings_collection.count_documents({'status': 'Confirmed'})
    completed_bookings = bookings_collection.count_documents({'status': 'Completed'})
    cancelled_bookings = bookings_collection.count_documents({'status': 'Cancelled'})
    
    # Today's bookings
    today = datetime.now().strftime("%Y-%m-%d")
    todays_bookings = bookings_collection.count_documents({'date': today})
    
    # Revenue calculations
    total_revenue_pipeline = [
        {'$match': {'status': 'Completed'}},
        {'$group': {'_id': None, 'total': {'$sum': '$final_price'}}}
    ]
    total_revenue_result = list(bookings_collection.aggregate(total_revenue_pipeline))
    total_revenue = total_revenue_result[0]['total'] if total_revenue_result else 0
    
    # This month's revenue
    first_day_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    monthly_revenue_pipeline = [
        {'$match': {'status': 'Completed', 'date': {'$gte': first_day_of_month}}},
        {'$group': {'_id': None, 'total': {'$sum': '$final_price'}}}
    ]
    monthly_revenue_result = list(bookings_collection.aggregate(monthly_revenue_pipeline))
    monthly_revenue = monthly_revenue_result[0]['total'] if monthly_revenue_result else 0
    
    # Active discounts count
    active_discounts = discounts_collection.count_documents({
        'is_active': True,
        'start_date': {'$lte': today},
        'end_date': {'$gte': today}
    })
    
    return jsonify({
        'customers': {
            'total': total_customers
        },
        'services': {
            'total': total_services,
            'active': total_active_services
        },
        'staff': {
            'active': active_staff_count
        },
        'bookings': {
            'total': total_bookings,
            'pending': pending_bookings,
            'confirmed': confirmed_bookings,
            'completed': completed_bookings,
            'cancelled': cancelled_bookings,
            'today': todays_bookings
        },
        'revenue': {
            'total': round(total_revenue, 2),
            'this_month': round(monthly_revenue, 2)
        },
        'discounts': {
            'active': active_discounts
        }
    }), 200


@app.route('/api/admin/dashboard/recent-bookings', methods=['GET'])
@admin_required
def get_recent_bookings():
    """Get recent bookings for dashboard (Admin only)"""
    limit = int(request.args.get('limit', 10))
    
    bookings = list(
        bookings_collection.find()
        .sort('created_at', -1)
        .limit(limit)
    )
    
    return jsonify({
        'bookings': serialize_docs(bookings),
        'total': len(bookings)
    }), 200


@app.route('/api/admin/dashboard/revenue-by-service', methods=['GET'])
@admin_required
def get_revenue_by_service():
    """Get revenue breakdown by service (Admin only)"""
    pipeline = [
        {'$match': {'status': 'Completed'}},
        {'$group': {
            '_id': '$service_id',
            'service_title': {'$first': '$service_title'},
            'total_revenue': {'$sum': '$final_price'},
            'booking_count': {'$sum': 1}
        }},
        {'$sort': {'total_revenue': -1}}
    ]
    
    revenue_data = list(bookings_collection.aggregate(pipeline))
    
    return jsonify({
        'revenue_by_service': [{
            'service_id': str(item['_id']),
            'service_title': item['service_title'],
            'total_revenue': round(item['total_revenue'], 2),
            'booking_count': item['booking_count']
        } for item in revenue_data]
    }), 200


@app.route('/api/admin/dashboard/bookings-by-date', methods=['GET'])
@admin_required
def get_bookings_by_date():
    """Get bookings count by date for the last 30 days (Admin only)"""
    days = int(request.args.get('days', 30))
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    pipeline = [
        {'$match': {'date': {'$gte': start_date}}},
        {'$group': {
            '_id': '$date',
            'count': {'$sum': 1},
            'revenue': {'$sum': {'$cond': [{'$eq': ['$status', 'Completed']}, '$final_price', 0]}}
        }},
        {'$sort': {'_id': 1}}
    ]
    
    bookings_data = list(bookings_collection.aggregate(pipeline))
    
    return jsonify({
        'bookings_by_date': [{
            'date': item['_id'],
            'count': item['count'],
            'revenue': round(item['revenue'], 2)
        } for item in bookings_data]
    }), 200


@app.route('/api/admin/dashboard/top-services', methods=['GET'])
@admin_required
def get_top_services():
    """Get top services by booking count (Admin only)"""
    limit = int(request.args.get('limit', 5))
    
    pipeline = [
        {'$group': {
            '_id': '$service_id',
            'service_title': {'$first': '$service_title'},
            'booking_count': {'$sum': 1}
        }},
        {'$sort': {'booking_count': -1}},
        {'$limit': limit}
    ]
    
    top_services = list(bookings_collection.aggregate(pipeline))
    
    return jsonify({
        'top_services': [{
            'service_id': str(item['_id']),
            'service_title': item['service_title'],
            'booking_count': item['booking_count']
        } for item in top_services]
    }), 200


# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        client.admin.command('ping')
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


# ==================== CORS ERROR HANDLING ====================

@app.after_request
def add_cors_headers_to_response(response):
    """Ensure CORS headers are on every response - Allow all origins and ports."""
    origin = request.headers.get('Origin')
    
    # Always allow all origins - no CORS errors
    if 'Access-Control-Allow-Origin' not in response.headers:
        if origin:
            # Allow the requesting origin
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            # If no origin header, allow all
            response.headers['Access-Control-Allow-Origin'] = '*'
    
    # Set other CORS headers
    if 'Access-Control-Allow-Headers' not in response.headers:
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept'
    if 'Access-Control-Allow-Methods' not in response.headers:
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    if 'Access-Control-Max-Age' not in response.headers:
        response.headers['Access-Control-Max-Age'] = '600'
    # Note: Access-Control-Allow-Credentials is not set when using wildcard (browser security)
    
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
@app.route('/api', methods=['OPTIONS'])
def cors_preflight(path=None):
    """Handle CORS preflight OPTIONS so preflight always gets 200 + CORS headers."""
    return '', 204


# ==================== ERROR HANDLERS ====================

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'Authorization token required'}), 401


# ==================== MAIN ====================

if __name__ == '__main__':
    # Initialize admin user
    init_admin()
    
    # Run the app
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=8000, debug=debug)
