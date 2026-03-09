"""
Tool definitions for the AI Agent.
Maps LLM tool calls to actual appointment service functions.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger

from backend.database import (
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    check_availability,
    get_patient_appointments,
    get_doctors_by_specialty,
    get_all_doctors,
    get_doctor_by_name,
)


# ─── OpenAI Function Definitions ──────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check available appointment slots for a specific doctor on a given date. Use this when the patient asks about available times or wants to know when a doctor is free.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The doctor's ID (e.g., DOC001)"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check in YYYY-MM-DD format"
                    }
                },
                "required": ["doctor_id", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_doctors",
            "description": "Search for doctors by specialty (e.g., cardiologist, dermatologist, general physician). Use this when the patient mentions a type of doctor they want to see.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Medical specialty to search for (e.g., cardiologist, dermatologist)"
                    }
                },
                "required": ["specialty"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_doctor_by_name",
            "description": "Find a doctor by their name. Use this when the patient mentions a specific doctor's name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Doctor's name to search for"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_new_appointment",
            "description": "Book a new appointment for the patient. Use this when you have all required information: doctor, date, and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The doctor's ID"
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format"
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time in HH:MM format (24-hour)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the appointment"
                    }
                },
                "required": ["doctor_id", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_existing_appointment",
            "description": "Cancel an existing appointment by its ID. Use this when the patient wants to cancel a booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "The appointment ID to cancel"
                    }
                },
                "required": ["appointment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_existing_appointment",
            "description": "Reschedule an existing appointment to a new date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "The appointment ID to reschedule"
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New date in YYYY-MM-DD format"
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New time in HH:MM format (24-hour)"
                    }
                },
                "required": ["appointment_id", "new_date", "new_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_appointments",
            "description": "Get all current appointments for the patient. Use this when the patient asks about their existing bookings.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_doctors",
            "description": "List all available doctors and their specialties. Use this when the patient wants to see who is available.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# ─── Tool Execution ───────────────────────────────────────────

def _resolve_date(date_str: str) -> str:
    """Resolve relative dates like 'tomorrow', 'next monday' to YYYY-MM-DD."""
    today = datetime.now().date()

    date_lower = date_str.lower().strip()

    if date_lower == "today":
        return today.strftime("%Y-%m-%d")
    elif date_lower == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_lower == "day after tomorrow":
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # Try to match day names
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if day in date_lower:
            current_day = today.weekday()
            target_day = i
            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week
            if "next" in date_lower:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Try direct parsing
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d", "%b %d"]:
        try:
            parsed = datetime.strptime(date_str, fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    patient_id: str,
    patient_name: str
) -> str:
    """
    Execute a tool call from the LLM.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments from the LLM
        patient_id: Current patient ID
        patient_name: Current patient name

    Returns:
        JSON string with tool results
    """
    logger.info(f"🔧 Executing tool: {tool_name} with args: {arguments}")

    try:
        if tool_name == "check_doctor_availability":
            date = _resolve_date(arguments["date"])
            result = await check_availability(arguments["doctor_id"], date)

        elif tool_name == "search_doctors":
            doctors = await get_doctors_by_specialty(arguments["specialty"])
            result = {
                "found": len(doctors),
                "doctors": [
                    {
                        "id": d["id"],
                        "name": d["name"],
                        "specialty": d["specialty"],
                        "hospital": d["hospital"]
                    }
                    for d in doctors
                ]
            }

        elif tool_name == "find_doctor_by_name":
            doctor = await get_doctor_by_name(arguments["name"])
            if doctor:
                result = {
                    "found": True,
                    "id": doctor["id"],
                    "name": doctor["name"],
                    "specialty": doctor["specialty"],
                    "hospital": doctor["hospital"]
                }
            else:
                result = {"found": False, "message": f"No doctor found with name '{arguments['name']}'"}

        elif tool_name == "book_new_appointment":
            date = _resolve_date(arguments["date"])
            result = await book_appointment(
                patient_id=patient_id,
                patient_name=patient_name,
                doctor_id=arguments["doctor_id"],
                date_str=date,
                time_str=arguments["time"],
                notes=arguments.get("notes", "")
            )

        elif tool_name == "cancel_existing_appointment":
            result = await cancel_appointment(
                appointment_id=arguments["appointment_id"],
                patient_id=patient_id
            )

        elif tool_name == "reschedule_existing_appointment":
            new_date = _resolve_date(arguments["new_date"])
            result = await reschedule_appointment(
                appointment_id=arguments["appointment_id"],
                patient_id=patient_id,
                new_date=new_date,
                new_time=arguments["new_time"]
            )

        elif tool_name == "get_my_appointments":
            appointments = await get_patient_appointments(patient_id)
            result = {
                "count": len(appointments),
                "appointments": [
                    {
                        "id": a["id"],
                        "doctor": a["doctor_name"],
                        "specialty": a["specialty"],
                        "date": a["date"],
                        "time": a["time"],
                        "status": a["status"]
                    }
                    for a in appointments
                ]
            }

        elif tool_name == "list_all_doctors":
            doctors = await get_all_doctors()
            result = {
                "total": len(doctors),
                "doctors": [
                    {
                        "id": d["id"],
                        "name": d["name"],
                        "specialty": d["specialty"],
                        "hospital": d["hospital"]
                    }
                    for d in doctors
                ]
            }

        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error(f"❌ Tool execution error ({tool_name}): {str(e)}")
        return json.dumps({"error": str(e)})
