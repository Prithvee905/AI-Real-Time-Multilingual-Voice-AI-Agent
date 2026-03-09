"""
Database module for appointment management.
Uses SQLite with aiosqlite for async operations.
"""
import aiosqlite
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from loguru import logger
from config import DATABASE_PATH


async def init_database():
    """Initialize the database with required tables and seed data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # ─── Appointments Table ───────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'confirmed',
                language TEXT DEFAULT 'en',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─── Doctors Table ────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                hospital TEXT DEFAULT '',
                available_days TEXT DEFAULT '["Monday","Tuesday","Wednesday","Thursday","Friday"]',
                available_slots TEXT DEFAULT '["09:00","09:30","10:00","10:30","11:00","11:30","14:00","14:30","15:00","15:30","16:00","16:30"]'
            )
        """)

        # ─── Seed Doctors ─────────────────────────────────────
        doctors = [
            ("DOC001", "Dr. Sharma", "Cardiologist", "Apollo Hospital",
             '["Monday","Tuesday","Wednesday","Thursday","Friday"]',
             '["09:00","09:30","10:00","10:30","11:00","11:30","14:00","14:30","15:00","15:30","16:00","16:30"]'),
            ("DOC002", "Dr. Patel", "Dermatologist", "Fortis Hospital",
             '["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]',
             '["10:00","10:30","11:00","11:30","14:00","14:30","15:00","15:30"]'),
            ("DOC003", "Dr. Arun Kumar", "General Physician", "Medanta Hospital",
             '["Monday","Tuesday","Wednesday","Thursday","Friday"]',
             '["09:00","09:30","10:00","10:30","11:00","14:00","14:30","15:00","15:30","16:00"]'),
            ("DOC004", "Dr. Priya Rajan", "Orthopedic", "Max Hospital",
             '["Monday","Wednesday","Friday"]',
             '["09:00","10:00","11:00","14:00","15:00","16:00"]'),
            ("DOC005", "Dr. Meena", "Pediatrician", "Apollo Hospital",
             '["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]',
             '["09:00","09:30","10:00","10:30","11:00","11:30","14:00","14:30","15:00"]'),
            ("DOC006", "Dr. Venkatesh", "ENT Specialist", "AIIMS",
             '["Tuesday","Thursday","Saturday"]',
             '["10:00","10:30","11:00","11:30","14:00","14:30","15:00"]'),
        ]

        for doc in doctors:
            await db.execute("""
                INSERT OR IGNORE INTO doctors (id, name, specialty, hospital, available_days, available_slots)
                VALUES (?, ?, ?, ?, ?, ?)
            """, doc)

        await db.commit()
        logger.info("✅ Database initialized with tables and seed data")


# ─── Doctor Operations ─────────────────────────────────────────

async def get_doctors_by_specialty(specialty: str) -> List[Dict]:
    """Find doctors by specialty (case-insensitive partial match)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM doctors WHERE LOWER(specialty) LIKE ?",
            (f"%{specialty.lower()}%",)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_doctors() -> List[Dict]:
    """Get all doctors."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM doctors")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_doctor_by_id(doctor_id: str) -> Optional[Dict]:
    """Get a specific doctor by ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_doctor_by_name(name: str) -> Optional[Dict]:
    """Find a doctor by name (case-insensitive partial match)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM doctors WHERE LOWER(name) LIKE ?",
            (f"%{name.lower()}%",)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─── Availability Operations ──────────────────────────────────

async def check_availability(doctor_id: str, date_str: str) -> Dict:
    """Check available slots for a doctor on a given date."""
    doctor = await get_doctor_by_id(doctor_id)
    if not doctor:
        return {"available": False, "error": "Doctor not found", "slots": []}

    # Parse the date
    try:
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"available": False, "error": "Invalid date format. Use YYYY-MM-DD", "slots": []}

    # Check if date is in the past
    if appt_date < date.today():
        return {"available": False, "error": "Cannot book appointments in the past", "slots": []}

    # Check if doctor works on this day
    day_name = appt_date.strftime("%A")
    available_days = json.loads(doctor["available_days"])
    if day_name not in available_days:
        return {
            "available": False,
            "error": f"Dr. {doctor['name']} is not available on {day_name}s",
            "slots": [],
            "available_days": available_days
        }

    # Get all available slots
    all_slots = json.loads(doctor["available_slots"])

    # Get already booked slots
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT time FROM appointments WHERE doctor_id = ? AND date = ? AND status = 'confirmed'",
            (doctor_id, date_str)
        )
        booked = [row[0] for row in await cursor.fetchall()]

    # Filter available slots
    available_slots = [s for s in all_slots if s not in booked]

    # Filter past times if booking for today
    if appt_date == date.today():
        current_time = datetime.now().strftime("%H:%M")
        available_slots = [s for s in available_slots if s > current_time]

    return {
        "available": len(available_slots) > 0,
        "doctor": doctor["name"],
        "date": date_str,
        "day": day_name,
        "total_slots": len(all_slots),
        "booked_slots": len(booked),
        "slots": available_slots
    }


# ─── Appointment CRUD Operations ──────────────────────────────

async def book_appointment(
    patient_id: str,
    patient_name: str,
    doctor_id: str,
    date_str: str,
    time_str: str,
    language: str = "en",
    notes: str = ""
) -> Dict:
    """Book a new appointment with conflict detection."""
    # Get doctor details
    doctor = await get_doctor_by_id(doctor_id)
    if not doctor:
        return {"success": False, "error": "Doctor not found"}

    # Check availability
    availability = await check_availability(doctor_id, date_str)
    if not availability["available"]:
        return {
            "success": False,
            "error": availability.get("error", "No slots available"),
            "available_slots": availability.get("slots", [])
        }

    # Check if the specific time slot is available
    if time_str not in availability["slots"]:
        return {
            "success": False,
            "error": f"The {time_str} slot is already booked",
            "available_slots": availability["slots"]
        }

    # Check for patient double-booking (same patient, same date, same time)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM appointments WHERE patient_id = ? AND date = ? AND time = ? AND status = 'confirmed'",
            (patient_id, date_str, time_str)
        )
        if await cursor.fetchone():
            return {"success": False, "error": "You already have an appointment at this time"}

        # Book the appointment
        cursor = await db.execute("""
            INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, specialty, date, time, language, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, patient_name, doctor_id, doctor["name"], doctor["specialty"], date_str, time_str, language, notes))
        await db.commit()

        return {
            "success": True,
            "appointment_id": cursor.lastrowid,
            "doctor_name": doctor["name"],
            "specialty": doctor["specialty"],
            "hospital": doctor["hospital"],
            "date": date_str,
            "time": time_str,
            "message": f"Appointment booked with {doctor['name']} ({doctor['specialty']}) on {date_str} at {time_str}"
        }


async def cancel_appointment(appointment_id: int, patient_id: str) -> Dict:
    """Cancel an existing appointment."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appointments WHERE id = ? AND patient_id = ? AND status = 'confirmed'",
            (appointment_id, patient_id)
        )
        appointment = await cursor.fetchone()

        if not appointment:
            return {"success": False, "error": "Appointment not found or already cancelled"}

        await db.execute(
            "UPDATE appointments SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (appointment_id,)
        )
        await db.commit()

        return {
            "success": True,
            "message": f"Appointment #{appointment_id} with {appointment['doctor_name']} on {appointment['date']} at {appointment['time']} has been cancelled"
        }


async def reschedule_appointment(
    appointment_id: int,
    patient_id: str,
    new_date: str,
    new_time: str
) -> Dict:
    """Reschedule an existing appointment."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appointments WHERE id = ? AND patient_id = ? AND status = 'confirmed'",
            (appointment_id, patient_id)
        )
        appointment = await cursor.fetchone()

        if not appointment:
            return {"success": False, "error": "Appointment not found or already cancelled"}

        # Check new slot availability
        availability = await check_availability(appointment["doctor_id"], new_date)
        if not availability["available"]:
            return {
                "success": False,
                "error": f"No available slots on {new_date}",
                "available_slots": availability.get("slots", [])
            }

        if new_time not in availability["slots"]:
            return {
                "success": False,
                "error": f"The {new_time} slot is not available",
                "available_slots": availability["slots"]
            }

        # Update the appointment
        await db.execute("""
            UPDATE appointments SET date = ?, time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (new_date, new_time, appointment_id))
        await db.commit()

        return {
            "success": True,
            "message": f"Appointment #{appointment_id} rescheduled to {new_date} at {new_time} with {appointment['doctor_name']}"
        }


async def get_patient_appointments(patient_id: str, status: str = "confirmed") -> List[Dict]:
    """Get all appointments for a patient."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appointments WHERE patient_id = ? AND status = ? ORDER BY date, time",
            (patient_id, status)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_upcoming_appointments(hours_ahead: int = 24) -> List[Dict]:
    """Get appointments happening in the next N hours (for reminders)."""
    now = datetime.now()
    future = now + timedelta(hours=hours_ahead)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM appointments
            WHERE status = 'confirmed'
            AND date >= ? AND date <= ?
            ORDER BY date, time
        """, (now.strftime("%Y-%m-%d"), future.strftime("%Y-%m-%d")))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
