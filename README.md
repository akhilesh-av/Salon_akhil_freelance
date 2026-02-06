# Salon Shop Backend

A Flask-based REST API for Salon Shop Management System with MongoDB integration.

## Features

- **Authentication**: JWT-based authentication for Admin and Customer
- **Service Management**: CRUD operations for salon services
- **Discount Management**: Service-specific discounts with date ranges
- **Booking Management**: Create, cancel, and manage bookings
- **Email Notifications**: SMTP-based booking confirmation and status updates
- **Staff Management**: Create, update, view, and deactivate staff (soft delete)
- **Attendance Management**: Daily check-in/check-out and attendance status
- **Admin Dashboard**: Summary API, statistics, revenue reports, and analytics

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Update the following variables:
- `SECRET_KEY`: Flask secret key
- `JWT_SECRET_KEY`: JWT secret key
- `MONGO_URI`: MongoDB connection string
- `SMTP_*`: SMTP email configuration
- `CORS_ORIGINS`: Comma-separated allowed origins (e.g. `http://localhost:3000,http://127.0.0.1:5173`). Default includes common dev ports.

### 3. CORS (Cross-Origin Requests)

CORS is configured so frontends on other origins can call the API without browser errors:

- **Allowed origins**: Set `CORS_ORIGINS` in `.env` (comma-separated). Default: `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, `http://127.0.0.1:5173`.
- **Headers**: All responses (including errors) get `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods`. Preflight `OPTIONS` requests to `/api` and `/api/*` return `204` with CORS headers.
- **Credentials**: Supported when using specific origins (not when using `*`).

Example `.env`:
```env
CORS_ORIGINS=http://localhost:3000,https://myapp.example.com
```

### 4. Run MongoDB

Make sure MongoDB is running on your system.

### 5. Start the Server

```bash
python app.py
```

Server will start at `http://localhost:5000`

## API Endpoints

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/auth/admin/login` | Admin login | - |
| POST | `/api/auth/customer/register` | Customer registration | - |
| POST | `/api/auth/customer/login` | Customer login | - |
| GET | `/api/auth/me` | Get current user | JWT |

### Services (Public + Admin)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/services` | Get all services | - |
| GET | `/api/services/:id` | Get service by ID | - |
| POST | `/api/services` | Create service | Admin |
| PUT | `/api/services/:id` | Update service | Admin |
| DELETE | `/api/services/:id` | Delete/deactivate service | Admin |

### Discounts (Admin Only)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/discounts` | Get all discounts | Admin |
| GET | `/api/discounts/:id` | Get discount by ID | Admin |
| POST | `/api/discounts` | Create discount | Admin |
| PUT | `/api/discounts/:id` | Update discount | Admin |
| DELETE | `/api/discounts/:id` | Disable discount | Admin |

### Staff Management (Admin Only)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/admin/staff` | Create staff | Admin |
| GET | `/api/admin/staff` | Get all staff | Admin |
| GET | `/api/admin/staff/:id` | Get staff by ID | Admin |
| PUT | `/api/admin/staff/:id` | Update staff | Admin |
| PUT | `/api/admin/staff/:id/deactivate` | Soft delete / deactivate staff | Admin |

### Attendance (Admin Only)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/admin/attendance/check-in` | Mark check-in (one per staff per day) | Admin |
| PUT | `/api/admin/attendance/check-out` | Mark check-out | Admin |
| GET | `/api/admin/attendance` | Get attendance (filter by date, staff_id, range) | Admin |
| PUT | `/api/admin/attendance/:id` | Update attendance record | Admin |

### Bookings

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/bookings` | Create booking | Customer |
| GET | `/api/bookings/my-bookings` | Get customer's bookings | Customer |
| PUT | `/api/bookings/:id/cancel` | Cancel booking | Customer |
| GET | `/api/admin/bookings` | Get all bookings | Admin |
| GET | `/api/admin/bookings/:id` | Get booking details | Admin |
| PUT | `/api/admin/bookings/:id/status` | Update booking status | Admin |

### Dashboard (Admin Only)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/admin/dashboard/summary` | **Single summary API**: total/today/confirmed/completed/cancelled bookings, active services, active staff | Admin |
| GET | `/api/admin/dashboard/stats` | Extended dashboard statistics | Admin |
| GET | `/api/admin/dashboard/recent-bookings` | Get recent bookings | Admin |
| GET | `/api/admin/dashboard/revenue-by-service` | Revenue by service | Admin |
| GET | `/api/admin/dashboard/bookings-by-date` | Bookings by date | Admin |
| GET | `/api/admin/dashboard/top-services` | Top booked services | Admin |

### Health Check

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/health` | Health check | - |

---

## API Request & Response Reference

All request bodies are JSON. Include `Authorization: Bearer <token>` for protected routes.

---

### Authentication

#### POST `/api/auth/admin/login`

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "username": "admin",
    "email": "admin@salonshop.com",
    "role": "admin"
  }
}
```

**Error (401):** `{"error": "Invalid credentials"}`

---

#### POST `/api/auth/customer/register`

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "phone": "+1234567890"
}
```
`phone` is optional.

**Response (201):**
```json
{
  "message": "Registration successful",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "507f1f77bcf86cd799439012",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "customer"
  }
}
```

**Error (409):** `{"error": "Email already registered"}`  
**Error (400):** `{"error": "Invalid email format"}` or `{"error": "Password must be at least 6 characters"}`

---

#### POST `/api/auth/customer/login`

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "507f1f77bcf86cd799439012",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "customer"
  }
}
```

**Error (401):** `{"error": "Invalid credentials"}`

---

#### GET `/api/auth/me`

**Headers:** `Authorization: Bearer <token>`

**Request Body:** None

**Response (200):**
```json
{
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "admin@salonshop.com",
    "role": "admin",
    "username": "admin"
  }
}
```
For customer: `name`, `phone` instead of `username`.

**Error (401):** `{"error": "Authorization token required"}` or `{"error": "Token has expired"}`

---

### Services

#### POST `/api/services` (Admin)

**Request Body:**
```json
{
  "title": "Haircut",
  "description": "Professional haircut service",
  "base_price": 25.00,
  "duration": 30,
  "discounted_price": 20.00,
  "status": "Active"
}
```
Required: `title`, `description`, `base_price`, `duration`. Optional: `discounted_price`, `status` (default `"Active"`).

**Response (201):**
```json
{
  "message": "Service created successfully",
  "service": {
    "_id": "507f1f77bcf86cd799439013",
    "title": "Haircut",
    "description": "Professional haircut service",
    "base_price": 25.0,
    "discounted_price": 20.0,
    "duration": 30,
    "status": "Active",
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

---

#### GET `/api/services`

**Query Params:** `status` (optional) – e.g. `Active`, `Inactive`

**Request Body:** None

**Response (200):**
```json
{
  "services": [
    {
      "_id": "507f1f77bcf86cd799439013",
      "title": "Haircut",
      "description": "Professional haircut service",
      "base_price": 25.0,
      "duration": 30,
      "status": "Active",
      "has_discount": true,
      "discount_type": "percentage",
      "discount_value": 20,
      "final_price": 20.0,
      "created_at": "2026-02-04T10:00:00.000Z",
      "updated_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### GET `/api/services/<service_id>`

**Request Body:** None

**Response (200):**
```json
{
  "service": {
    "_id": "507f1f77bcf86cd799439013",
    "title": "Haircut",
    "description": "Professional haircut service",
    "base_price": 25.0,
    "duration": 30,
    "status": "Active",
    "has_discount": false,
    "final_price": 25.0,
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (404):** `{"error": "Service not found"}`

---

#### PUT `/api/services/<service_id>` (Admin)

**Request Body:** (all fields optional)
```json
{
  "title": "Premium Haircut",
  "description": "Updated description",
  "base_price": 30.00,
  "discounted_price": 25.00,
  "duration": 45,
  "status": "Active"
}
```

**Response (200):**
```json
{
  "message": "Service updated successfully",
  "service": {
    "_id": "507f1f77bcf86cd799439013",
    "title": "Premium Haircut",
    "description": "Updated description",
    "base_price": 30.0,
    "duration": 45,
    "status": "Active",
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:30:00.000Z"
  }
}
```

---

#### DELETE `/api/services/<service_id>` (Admin)

**Request Body:** None

**Response (200):**
```json
{
  "message": "Service deleted successfully"
}
```
If the service has active bookings, it is deactivated instead: `{"message": "Service deactivated (has active bookings)", "deactivated": true}`

**Error (404):** `{"error": "Service not found"}`

---

### Discounts (Admin)

#### POST `/api/discounts`

**Request Body:**
```json
{
  "service_id": "507f1f77bcf86cd799439013",
  "discount_type": "percentage",
  "discount_value": 20,
  "start_date": "2026-02-01",
  "end_date": "2026-02-28"
}
```
`discount_type`: `"percentage"` or `"flat"`. Dates in `YYYY-MM-DD`.

**Response (201):**
```json
{
  "message": "Discount created successfully",
  "discount": {
    "_id": "507f1f77bcf86cd799439014",
    "service_id": "507f1f77bcf86cd799439013",
    "discount_type": "percentage",
    "discount_value": 20.0,
    "start_date": "2026-02-01",
    "end_date": "2026-02-28",
    "is_active": true,
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (409):** `{"error": "An active discount already exists for this service in the specified date range"}`

---

#### GET `/api/discounts`

**Query Params:** `service_id`, `is_active` (optional)

**Request Body:** None

**Response (200):**
```json
{
  "discounts": [
    {
      "_id": "507f1f77bcf86cd799439014",
      "service_id": "507f1f77bcf86cd799439013",
      "service_title": "Haircut",
      "discount_type": "percentage",
      "discount_value": 20.0,
      "start_date": "2026-02-01",
      "end_date": "2026-02-28",
      "is_active": true,
      "created_at": "2026-02-04T10:00:00.000Z",
      "updated_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### GET `/api/discounts/<discount_id>`

**Request Body:** None

**Response (200):**
```json
{
  "discount": {
    "_id": "507f1f77bcf86cd799439014",
    "service_id": "507f1f77bcf86cd799439013",
    "service_title": "Haircut",
    "discount_type": "percentage",
    "discount_value": 20.0,
    "start_date": "2026-02-01",
    "end_date": "2026-02-28",
    "is_active": true,
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (404):** `{"error": "Discount not found"}`

---

#### PUT `/api/discounts/<discount_id>`

**Request Body:** (all optional)
```json
{
  "discount_type": "flat",
  "discount_value": 5.00,
  "start_date": "2026-02-01",
  "end_date": "2026-02-28",
  "is_active": true
}
```

**Response (200):**
```json
{
  "message": "Discount updated successfully",
  "discount": { ... }
}
```

---

#### DELETE `/api/discounts/<discount_id>`

**Request Body:** None

**Response (200):**
```json
{
  "message": "Discount disabled successfully"
}
```

---

### Staff Management (Admin)

#### POST `/api/admin/staff`

**Request Body:**
```json
{
  "full_name": "Jane Smith",
  "email": "jane@salon.com",
  "phone": "+1234567890",
  "role": "stylist",
  "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "shift_timings": { "start": "09:00", "end": "17:00" },
  "status": "Active"
}
```
Required: `full_name`, `phone`, `role`. Optional: `email`, `working_days`, `shift_timings`, `status` (default `"Active"`).  
`role`: `stylist`, `receptionist`, `manager`, or `therapist`.

**Response (201):**
```json
{
  "message": "Staff created successfully",
  "staff": {
    "_id": "507f1f77bcf86cd799439015",
    "staff_id": "507f1f77bcf86cd799439015",
    "full_name": "Jane Smith",
    "email": "jane@salon.com",
    "phone": "+1234567890",
    "role": "stylist",
    "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "shift_timings": { "start": "09:00", "end": "17:00" },
    "status": "Active",
    "is_deleted": false,
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

---

#### GET `/api/admin/staff`

**Query Params:** `include_inactive` (true/false), `include_deleted` (true/false), `status` (Active/Inactive)

**Request Body:** None

**Response (200):**
```json
{
  "staff": [
    {
      "_id": "507f1f77bcf86cd799439015",
      "staff_id": "507f1f77bcf86cd799439015",
      "full_name": "Jane Smith",
      "email": "jane@salon.com",
      "phone": "+1234567890",
      "role": "stylist",
      "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "shift_timings": { "start": "09:00", "end": "17:00" },
      "status": "Active",
      "is_deleted": false,
      "created_at": "2026-02-04T10:00:00.000Z",
      "updated_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### GET `/api/admin/staff/<staff_id>`

**Request Body:** None

**Response (200):**
```json
{
  "staff": {
    "_id": "507f1f77bcf86cd799439015",
    "staff_id": "507f1f77bcf86cd799439015",
    "full_name": "Jane Smith",
    "email": "jane@salon.com",
    "phone": "+1234567890",
    "role": "stylist",
    "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "shift_timings": { "start": "09:00", "end": "17:00" },
    "status": "Active",
    "is_deleted": false,
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (404):** `{"error": "Staff not found"}`  
**Error (410):** `{"error": "Staff record has been deactivated"}`

---

#### PUT `/api/admin/staff/<staff_id>`

**Request Body:** (all optional)
```json
{
  "full_name": "Jane Smith",
  "email": "jane@salon.com",
  "phone": "+1234567890",
  "role": "stylist",
  "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "shift_timings": { "start": "09:00", "end": "18:00" },
  "status": "Inactive"
}
```

**Response (200):**
```json
{
  "message": "Staff updated successfully",
  "staff": { ... }
}
```

---

#### PUT `/api/admin/staff/<staff_id>/deactivate`

**Request Body:** None

**Response (200):**
```json
{
  "message": "Staff deactivated successfully (soft delete)"
}
```

---

### Attendance (Admin)

#### POST `/api/admin/attendance/check-in`

**Request Body:**
```json
{
  "staff_id": "507f1f77bcf86cd799439015",
  "date": "2026-02-04",
  "check_in_time": "09:00"
}
```
Required: `staff_id`, `date` (YYYY-MM-DD). Optional: `check_in_time` (HH:MM; default current time).

**Response (201):**
```json
{
  "message": "Check-in recorded successfully",
  "attendance": {
    "_id": "507f1f77bcf86cd799439016",
    "staff_id": "507f1f77bcf86cd799439015",
    "staff_name": "Jane Smith",
    "date": "2026-02-04",
    "check_in_time": "09:00",
    "check_out_time": null,
    "attendance_status": "Present",
    "created_at": "2026-02-04T09:00:00.000Z",
    "updated_at": "2026-02-04T09:00:00.000Z"
  }
}
```

**Error (409):** `{"error": "Check-in already recorded for this staff on this date"}`  
**Error (404):** `{"error": "Staff not found or inactive"}`

---

#### PUT `/api/admin/attendance/check-out`

**Request Body:**
```json
{
  "staff_id": "507f1f77bcf86cd799439015",
  "date": "2026-02-04",
  "check_out_time": "17:00",
  "attendance_status": "Present"
}
```
Required: `staff_id`, `date`. Optional: `check_out_time` (default current time), `attendance_status`: `Present`, `Absent`, or `Half-day`.

**Response (200):**
```json
{
  "message": "Check-out recorded successfully",
  "attendance": {
    "_id": "507f1f77bcf86cd799439016",
    "staff_id": "507f1f77bcf86cd799439015",
    "staff_name": "Jane Smith",
    "date": "2026-02-04",
    "check_in_time": "09:00",
    "check_out_time": "17:00",
    "attendance_status": "Present",
    "created_at": "2026-02-04T09:00:00.000Z",
    "updated_at": "2026-02-04T17:00:00.000Z"
  }
}
```

**Error (404):** `{"error": "No check-in record found for this staff on this date"}`

---

#### GET `/api/admin/attendance`

**Query Params:** `date`, `staff_id`, `start_date`, `end_date` (optional)

**Request Body:** None

**Response (200):**
```json
{
  "attendance": [
    {
      "_id": "507f1f77bcf86cd799439016",
      "staff_id": "507f1f77bcf86cd799439015",
      "staff_name": "Jane Smith",
      "date": "2026-02-04",
      "check_in_time": "09:00",
      "check_out_time": "17:00",
      "attendance_status": "Present",
      "created_at": "2026-02-04T09:00:00.000Z",
      "updated_at": "2026-02-04T17:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### PUT `/api/admin/attendance/<attendance_id>`

**Request Body:** (all optional)
```json
{
  "check_in_time": "09:30",
  "check_out_time": "17:30",
  "attendance_status": "Half-day"
}
```
`attendance_status`: `Present`, `Absent`, or `Half-day`.

**Response (200):**
```json
{
  "message": "Attendance updated successfully",
  "attendance": { ... }
}
```

**Error (404):** `{"error": "Attendance record not found"}`

---

### Bookings

#### POST `/api/bookings` (Customer)

**Request Body:**
```json
{
  "service_id": "507f1f77bcf86cd799439013",
  "date": "2026-02-15",
  "time_slot": "10:00",
  "notes": "First visit"
}
```
Required: `service_id`, `date` (YYYY-MM-DD), `time_slot` (HH:MM). Optional: `notes`.

**Response (201):**
```json
{
  "message": "Booking created successfully",
  "booking": {
    "_id": "507f1f77bcf86cd799439017",
    "customer_id": "507f1f77bcf86cd799439012",
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "service_id": "507f1f77bcf86cd799439013",
    "service_title": "Haircut",
    "date": "2026-02-15",
    "time_slot": "10:00",
    "base_price": 25.0,
    "final_price": 20.0,
    "discount_applied": true,
    "status": "Pending",
    "notes": "First visit",
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (409):** `{"error": "This time slot is already booked"}`  
**Error (400):** `{"error": "Booking must be for a future date and time"}` or `{"error": "Service is not available"}`

---

#### GET `/api/bookings/my-bookings` (Customer)

**Query Params:** `status` (optional) – Pending, Confirmed, Completed, Cancelled

**Request Body:** None

**Response (200):**
```json
{
  "bookings": [
    {
      "_id": "507f1f77bcf86cd799439017",
      "customer_id": "507f1f77bcf86cd799439012",
      "customer_name": "John Doe",
      "customer_email": "john@example.com",
      "service_id": "507f1f77bcf86cd799439013",
      "service_title": "Haircut",
      "date": "2026-02-15",
      "time_slot": "10:00",
      "base_price": 25.0,
      "final_price": 20.0,
      "discount_applied": true,
      "status": "Pending",
      "notes": "",
      "created_at": "2026-02-04T10:00:00.000Z",
      "updated_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### PUT `/api/bookings/<booking_id>/cancel` (Customer)

**Request Body:** None (or empty `{}`)

**Response (200):**
```json
{
  "message": "Booking cancelled successfully"
}
```

**Error (403):** `{"error": "Unauthorized to cancel this booking"}`  
**Error (400):** `{"error": "Cannot cancel past bookings"}` or `{"error": "Cannot cancel a completed booking"}`

---

#### GET `/api/admin/bookings` (Admin)

**Query Params:** `status`, `date`, `service_id` (optional)

**Request Body:** None

**Response (200):**
```json
{
  "bookings": [
    {
      "_id": "507f1f77bcf86cd799439017",
      "customer_id": "507f1f77bcf86cd799439012",
      "customer_name": "John Doe",
      "customer_email": "john@example.com",
      "service_id": "507f1f77bcf86cd799439013",
      "service_title": "Haircut",
      "date": "2026-02-15",
      "time_slot": "10:00",
      "base_price": 25.0,
      "final_price": 20.0,
      "discount_applied": true,
      "status": "Pending",
      "notes": "",
      "created_at": "2026-02-04T10:00:00.000Z",
      "updated_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 1
}
```

---

#### GET `/api/admin/bookings/<booking_id>` (Admin)

**Request Body:** None

**Response (200):**
```json
{
  "booking": {
    "_id": "507f1f77bcf86cd799439017",
    "customer_id": "507f1f77bcf86cd799439012",
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "service_id": "507f1f77bcf86cd799439013",
    "service_title": "Haircut",
    "date": "2026-02-15",
    "time_slot": "10:00",
    "base_price": 25.0,
    "final_price": 20.0,
    "discount_applied": true,
    "status": "Pending",
    "notes": "",
    "created_at": "2026-02-04T10:00:00.000Z",
    "updated_at": "2026-02-04T10:00:00.000Z"
  }
}
```

**Error (404):** `{"error": "Booking not found"}`

---

#### PUT `/api/admin/bookings/<booking_id>/status` (Admin)

**Request Body:**
```json
{
  "status": "Confirmed"
}
```
`status`: `Pending`, `Confirmed`, `Completed`, or `Cancelled`.

**Response (200):**
```json
{
  "message": "Booking status updated to Confirmed",
  "old_status": "Pending",
  "new_status": "Confirmed"
}
```

**Error (400):** `{"error": "Status is required"}` or `{"error": "Invalid status. Must be one of: Pending, Confirmed, Completed, Cancelled"}`

---

### Dashboard (Admin)

#### GET `/api/admin/dashboard/summary`

**Request Body:** None

**Response (200):**
```json
{
  "total_bookings": 150,
  "todays_bookings": 8,
  "confirmed_bookings": 12,
  "completed_bookings": 120,
  "cancelled_bookings": 18,
  "active_services_count": 5,
  "active_staff_count": 4
}
```

---

#### GET `/api/admin/dashboard/stats`

**Request Body:** None

**Response (200):**
```json
{
  "customers": { "total": 45 },
  "services": { "total": 6, "active": 5 },
  "staff": { "active": 4 },
  "bookings": {
    "total": 150,
    "pending": 10,
    "confirmed": 12,
    "completed": 120,
    "cancelled": 18,
    "today": 8
  },
  "revenue": {
    "total": 3500.50,
    "this_month": 850.00
  },
  "discounts": { "active": 2 }
}
```

---

#### GET `/api/admin/dashboard/recent-bookings`

**Query Params:** `limit` (optional, default 10)

**Request Body:** None

**Response (200):**
```json
{
  "bookings": [
    {
      "_id": "507f1f77bcf86cd799439017",
      "customer_name": "John Doe",
      "service_title": "Haircut",
      "date": "2026-02-15",
      "time_slot": "10:00",
      "status": "Pending",
      "final_price": 20.0,
      "created_at": "2026-02-04T10:00:00.000Z"
    }
  ],
  "total": 10
}
```

---

#### GET `/api/admin/dashboard/revenue-by-service`

**Request Body:** None

**Response (200):**
```json
{
  "revenue_by_service": [
    {
      "service_id": "507f1f77bcf86cd799439013",
      "service_title": "Haircut",
      "total_revenue": 1200.50,
      "booking_count": 48
    }
  ]
}
```

---

#### GET `/api/admin/dashboard/bookings-by-date`

**Query Params:** `days` (optional, default 30)

**Request Body:** None

**Response (200):**
```json
{
  "bookings_by_date": [
    {
      "date": "2026-02-04",
      "count": 8,
      "revenue": 160.00
    }
  ]
}
```

---

#### GET `/api/admin/dashboard/top-services`

**Query Params:** `limit` (optional, default 5)

**Request Body:** None

**Response (200):**
```json
{
  "top_services": [
    {
      "service_id": "507f1f77bcf86cd799439013",
      "service_title": "Haircut",
      "booking_count": 48
    }
  ]
}
```

---

### Health Check

#### GET `/api/health`

**Request Body:** None

**Response (200):**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-02-04T10:00:00.000Z"
}
```
If DB fails: `"database": "error: <message>"`

---

## Default Admin Credentials

- **Username**: admin
- **Password**: admin123

(Change these in production!)

## Booking Statuses

- `Pending`: Initial status when booking is created
- `Confirmed`: Booking confirmed by admin
- `Completed`: Service has been completed
- `Cancelled`: Booking was cancelled

## Email Notifications

The system sends emails for:
- Booking confirmation (on creation)
- Booking cancellation (by customer or admin)
- Status updates (Confirmed, Completed, Cancelled)

Configure SMTP settings in `.env` file for Gmail:
- Enable 2-factor authentication
- Generate an App Password
- Use the App Password as `SMTP_PASSWORD`
