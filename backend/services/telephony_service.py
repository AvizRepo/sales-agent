import os
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") 

if ACCOUNT_SID and AUTH_TOKEN:
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    print("Twilio Client Initialized.")
else:
    client = None
    print("Warning: Twilio credentials missing in .env file.")

def create_connect_stream_twiml(websocket_url: str) -> str:
    """Generates TwiML to connect the call to a WebSocket stream."""
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=websocket_url)
    response.append(connect)
    response.say("Please wait while I connect you to the AI agent.") 

    response.pause(length=15)
    response.say("Sorry, I couldn't connect to the agent. Please try again later. Goodbye.")
    response.hangup()
    print(f"Generated TwiML for <Connect><Stream> to {websocket_url}:\n{str(response)}")
    return str(response)

def make_call(destination_number: str, call_sid_placeholder: str):
    """Initiates a call that will connect to our backend WebSocket stream."""
    if not client:
        return {"error": "Twilio client not initialized. Check credentials in .env file."}
    if not TWILIO_NUMBER:
        return {"error": "Twilio phone number not found in .env file."}
    if not destination_number:
        return {"error": "Destination phone number is required."}
    if not PUBLIC_BASE_URL or "mycustomname.loca.lt" in PUBLIC_BASE_URL:
         print(f"Warning: PUBLIC_BASE_URL might be a placeholder or default: {PUBLIC_BASE_URL}")


    backend_websocket_url = f"wss://{PUBLIC_BASE_URL.split('//')[1]}/ws/call/{call_sid_placeholder}"

    initial_twiml_fetch_url = f"{PUBLIC_BASE_URL}/handle_call_start/{call_sid_placeholder}"

    try:
        print(f"Attempting to call {destination_number} from {TWILIO_NUMBER}")
        print(f"Twilio will fetch initial TwiML from: {initial_twiml_fetch_url}")

        call = client.calls.create(
            to=destination_number,
            from_=TWILIO_NUMBER,
            url=initial_twiml_fetch_url,
            record=False
        )

        print(f"Call initiated successfully. Actual Call SID: {call.sid}")
        return {
            "success": True,
            "message": f"Call initiated to {destination_number}",
            "call_sid": call.sid
        }

    except Exception as e:
        error_message = f"Twilio call initiation failed: {str(e)}"
        print(error_message)
        return {"error": error_message}