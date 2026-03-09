"""
API Routes for the Voice AI Agent.
Provides REST endpoints for appointments, doctors, campaigns, and memory.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from backend.database import (
    get_all_doctors,
    get_doctors_by_specialty,
    get_doctor_by_id,
    check_availability,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_patient_appointments,
    get_upcoming_appointments,
)
from memory.persistent_memory.persistent_manager import PersistentMemory
from scheduler.campaign_scheduler import CampaignScheduler

router = APIRouter()
persistent_memory = PersistentMemory()
campaign_scheduler = CampaignScheduler()


# ─── Request Models ───────────────────────────────────────────

class BookingRequest(BaseModel):
    patient_id: str
    patient_name: str
    doctor_id: str
    date: str
    time: str
    language: str = "en"
    notes: str = ""


class RescheduleRequest(BaseModel):
    appointment_id: int
    patient_id: str
    new_date: str
    new_time: str


class CancelRequest(BaseModel):
    appointment_id: int
    patient_id: str


class CampaignRequest(BaseModel):
    campaign_type: str = "reminder"
    name: str
    target_patients: List[str]
    message_template: str
    language: str = "en"


# ─── Doctor Endpoints ─────────────────────────────────────────

@router.get("/api/doctors")
async def list_doctors():
    """Get all available doctors."""
    doctors = await get_all_doctors()
    return {"doctors": doctors, "total": len(doctors)}


@router.get("/api/doctors/search/{specialty}")
async def search_doctors(specialty: str):
    """Search doctors by specialty."""
    doctors = await get_doctors_by_specialty(specialty)
    return {"doctors": doctors, "total": len(doctors)}


@router.get("/api/doctors/{doctor_id}")
async def get_doctor(doctor_id: str):
    """Get doctor details by ID."""
    doctor = await get_doctor_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.get("/api/doctors/{doctor_id}/availability/{date}")
async def doctor_availability(doctor_id: str, date: str):
    """Check doctor availability for a specific date."""
    result = await check_availability(doctor_id, date)
    return result


# ─── Appointment Endpoints ────────────────────────────────────

@router.post("/api/appointments/book")
async def create_booking(request: BookingRequest):
    """Book a new appointment."""
    result = await book_appointment(
        patient_id=request.patient_id,
        patient_name=request.patient_name,
        doctor_id=request.doctor_id,
        date_str=request.date,
        time_str=request.time,
        language=request.language,
        notes=request.notes
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/api/appointments/cancel")
async def cancel_booking(request: CancelRequest):
    """Cancel an existing appointment."""
    result = await cancel_appointment(request.appointment_id, request.patient_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/api/appointments/reschedule")
async def reschedule_booking(request: RescheduleRequest):
    """Reschedule an existing appointment."""
    result = await reschedule_appointment(
        request.appointment_id,
        request.patient_id,
        request.new_date,
        request.new_time
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/api/appointments/{patient_id}")
async def patient_appointments(patient_id: str):
    """Get all appointments for a patient."""
    appointments = await get_patient_appointments(patient_id)
    return {"appointments": appointments, "total": len(appointments)}


@router.get("/api/appointments/upcoming/{hours}")
async def upcoming_appointments(hours: int = 24):
    """Get appointments coming up in the next N hours."""
    appointments = await get_upcoming_appointments(hours)
    return {"appointments": appointments, "total": len(appointments)}


# ─── Campaign Endpoints ───────────────────────────────────────

@router.post("/api/campaigns/create")
async def create_campaign(request: CampaignRequest):
    """Create a new outbound campaign."""
    campaign = campaign_scheduler.create_campaign(
        campaign_type=request.campaign_type,
        name=request.name,
        target_patients=request.target_patients,
        message_template=request.message_template,
        language=request.language
    )
    return campaign


@router.get("/api/campaigns")
async def list_campaigns():
    """List all campaigns."""
    campaigns = campaign_scheduler.get_all_campaigns()
    return {"campaigns": campaigns, "total": len(campaigns)}


@router.get("/api/campaigns/active")
async def active_campaigns():
    """List active campaigns."""
    campaigns = campaign_scheduler.get_active_campaigns()
    return {"campaigns": campaigns, "total": len(campaigns)}


@router.post("/api/campaigns/generate-reminders")
async def generate_reminders():
    """Auto-generate reminder campaigns for upcoming appointments."""
    campaigns = await campaign_scheduler.generate_reminder_campaigns()
    return {"generated": len(campaigns), "campaigns": campaigns}


# ─── Memory Endpoints ─────────────────────────────────────────

@router.get("/api/memory/{patient_id}")
async def get_patient_memory(patient_id: str):
    """Get patient's persistent memory profile."""
    profile = persistent_memory.get_patient(patient_id)
    return profile


@router.get("/api/memory")
async def list_all_patients():
    """List all patient profiles."""
    patients = persistent_memory.get_all_patients()
    return {"patients": patients, "total": len(patients)}
