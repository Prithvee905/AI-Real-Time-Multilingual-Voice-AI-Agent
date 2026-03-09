"""
AI Agent Reasoning Engine.
Uses OpenAI GPT with function calling for appointment management.
Integrates with memory systems and tool orchestration.
"""
import json
import time
from typing import Dict, Optional
from loguru import logger

from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from agent.prompt.system_prompt import get_system_prompt
from agent.tools.tool_definitions import TOOL_DEFINITIONS, execute_tool
from memory.session_memory.session_manager import SessionMemory
from memory.persistent_memory.persistent_manager import PersistentMemory

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
persistent_memory = PersistentMemory()


async def process_message(
    text: str,
    session_id: str,
    patient_id: str,
    patient_name: str = "Patient",
    language: str = "en"
) -> Dict:
    """
    Process a user message through the AI agent.

    Args:
        text: User's transcribed text
        session_id: Current session ID
        patient_id: Patient identifier
        patient_name: Patient's name
        language: Detected language code

    Returns:
        Dict with 'response' text and metadata
    """
    start_time = time.perf_counter()

    # Initialize memory
    session = SessionMemory(session_id, patient_id)
    await session.add_message("user", text, language)

    # Update persistent memory
    persistent_memory.increment_interaction(patient_id)
    if patient_name and patient_name != "Patient":
        persistent_memory.update_patient(patient_id, {"name": patient_name})
    persistent_memory.set_language_preference(patient_id, language)

    # Get context from memories
    patient_context = persistent_memory.get_context_for_agent(patient_id)
    session_context = await session.get_context_summary()

    # Build messages
    system_prompt = get_system_prompt(language, patient_context, session_context)
    conversation_history = await session.get_conversation_messages()

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)

    try:
        # Call LLM with tool definitions
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        )

        message = response.choices[0].message

        # Handle tool calls (may need multiple rounds)
        tool_call_count = 0
        while message.tool_calls and tool_call_count < 5:
            tool_call_count += 1
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                tool_result = await execute_tool(
                    func_name, func_args, patient_id, patient_name
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

                # Update memory with booking info
                result_data = json.loads(tool_result)
                if func_name == "book_new_appointment" and result_data.get("success"):
                    persistent_memory.add_appointment_history(patient_id, result_data)

            # Get next response after tool execution
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500
            )
            message = response.choices[0].message

        # Extract final response text
        response_text = message.content or "I'm sorry, I couldn't process that. Could you please try again?"

        # Save assistant response to session
        await session.add_message("assistant", response_text, language)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"🤖 Agent [{duration_ms:.0f}ms]: {response_text[:100]}...")

        return {
            "response": response_text,
            "language": language,
            "tool_calls_made": tool_call_count,
            "duration_ms": round(duration_ms, 2),
            "success": True
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"❌ Agent Error [{duration_ms:.0f}ms]: {str(e)}")

        # Provide a safe fallback response
        fallback_responses = {
            "en": "I'm having trouble processing that request. Could you please repeat?",
            "hi": "मुझे उस अनुरोध को संसाधित करने में कठिनाई हो रही है। क्या आप कृपया दोहरा सकते हैं?",
            "ta": "அந்த கோரிக்கையை செயலாக்குவதில் சிக்கல் உள்ளது. தயவுசெய்து மீண்டும் சொல்ல முடியுமா?"
        }

        return {
            "response": fallback_responses.get(language, fallback_responses["en"]),
            "language": language,
            "tool_calls_made": 0,
            "duration_ms": round(duration_ms, 2),
            "success": False,
            "error": str(e)
        }
