import os
import uuid
from fastapi import FastAPI, Response, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import logging 
from starlette.websockets import WebSocketState 

from services import telephony_service
from services import streaming_service 

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s') 

knowledge_summary: Optional[str] = None
company_name: Optional[str] = "Default AI Services Inc." 


app = FastAPI(title="AI Sales Agent API - Deepgram Integration")

origins = ["http://localhost:5173", "http://localhost"] 
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CallRequest(BaseModel):
    phone_number: str
    user_name: str = Field(..., min_length=1)
class KnowledgeUploadRequest(BaseModel):
    knowledge_text: str = Field(..., min_length=10)
class CompanyInfoRequest(BaseModel):
    name: str = Field(..., min_length=2)

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "AI Sales Agent Backend (Deepgram) is running!"}

@app.get("/company_info")
async def get_company_info():
    global company_name
    logging.info("Fetching company info")
    return {"company_name": company_name or "Not Set"}

@app.post("/company_info")
async def set_company_info(request: CompanyInfoRequest):
    global company_name
    company_name = request.name
    logging.info(f"Company name updated to: {company_name}")
    return {"success": True, "message": f"Company name set to {company_name}"}

@app.get("/get_knowledge")
async def get_knowledge():
    global knowledge_summary
    logging.info("Fetching knowledge summary")
    return {"knowledge_summary": knowledge_summary or "No knowledge summary available yet."}

@app.post("/upload_knowledge")
async def upload_knowledge(request: KnowledgeUploadRequest):
    """
    Stores the raw knowledge text. Deepgram's internal OpenAI call will use this.
    """
    global knowledge_summary
    logging.info("Received knowledge text for agent.")
    knowledge_summary = request.knowledge_text.strip()
    logging.info(f"Knowledge base updated (length: {len(knowledge_summary)} chars).")
    return {"success": True, "message": "Knowledge base text stored for AI agent."}


@app.post("/initiate_call")
async def handle_initiate_call(request: CallRequest):
    """
    Initiates the call using Twilio, providing a URL for Twilio to fetch TwiML.
    """
    phone_to_call = request.phone_number
    user_name = request.user_name
    call_sid_placeholder = f"TEMP_{uuid.uuid4()}"
    logging.info(f"Received request to call: {phone_to_call} for user: {user_name} (placeholder: {call_sid_placeholder})")

    result = telephony_service.make_call(
        destination_number=phone_to_call,
        call_sid_placeholder=call_sid_placeholder
        )

    if result.get("success"):
        actual_call_sid = result["call_sid"]
        logging.info(f"Call initiated with actual CallSid: {actual_call_sid}. Frontend can now use this SID.")
    else:
        logging.error(f"Call initiation failed: {result.get('error')}")

    return result

@app.post("/handle_call_start/{call_sid_placeholder}")
async def handle_call_start(request: Request, call_sid_placeholder: str):
    """
    This endpoint is called by Twilio *immediately* after initiating the call.
    It returns the TwiML instructing Twilio to connect to our WebSocket endpoint.
    """
    form_data = await request.form()
    actual_call_sid = form_data.get("CallSid")

    if not actual_call_sid:
        logging.error("'/handle_call_start' called without CallSid in form data.")
        raise HTTPException(status_code=400, detail="CallSid missing from request.")

    logging.info(f"Handling call start for CallSid: {actual_call_sid} (placeholder was {call_sid_placeholder})")

    public_base_host = telephony_service.PUBLIC_BASE_URL
    if not public_base_host:
         logging.error("PUBLIC_BASE_URL is not set in environment variables!")
         raise HTTPException(status_code=500, detail="Server configuration error: PUBLIC_BASE_URL missing.")
    if public_base_host.startswith("https://"):
        public_base_host = public_base_host[len("https://"):]
    elif public_base_host.startswith("http://"):
         public_base_host = public_base_host[len("http://"):]
    public_base_host = public_base_host.rstrip('/')

    if not public_base_host:
         logging.error("PUBLIC_BASE_URL resulted in an empty host!")
         raise HTTPException(status_code=500, detail="Server configuration error: Invalid PUBLIC_BASE_URL.")

    backend_websocket_url = f"wss://{public_base_host}/ws/call/{actual_call_sid}"
    logging.info(f"Generating TwiML to connect to: {backend_websocket_url}")

    twiml_response_content = telephony_service.create_connect_stream_twiml(backend_websocket_url)

    return Response(content=twiml_response_content, media_type="application/xml")


@app.websocket("/ws/call/{call_sid}")
async def websocket_call_handler(websocket: WebSocket, call_sid: str):
    """
    Handles the bidirectional audio stream between Twilio and Deepgram Agent.
    """
    await websocket.accept()
    logging.info(f"Twilio WebSocket connected for CallSid: {call_sid} from {websocket.client}")
    global company_name, knowledge_summary 

    try:
        current_company_name = company_name
        current_knowledge_summary = knowledge_summary

        await streaming_service.handle_deepgram_connection(
            twilio_ws=websocket,
            call_sid=call_sid,
            company_name=current_company_name,
            knowledge_summary=current_knowledge_summary
        )
    except WebSocketDisconnect:
        logging.warning(f"Twilio WebSocket disconnected expectedly for CallSid: {call_sid}")
    except Exception as e:
        logging.error(f"Unexpected error in main WebSocket handler for CallSid {call_sid}: {e}", exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTED:
             try:
                 await websocket.close(code=1011, reason="Internal server error during streaming")
             except Exception as close_exc:
                  logging.error(f"Error closing WebSocket after exception for {call_sid}: {close_exc}")
    finally:
        logging.info(f"Main WebSocket handler finished processing for CallSid: {call_sid}")
        if websocket.client_state == WebSocketState.CONNECTED:
            logging.warning(f"WebSocket {call_sid} still connected in main handler finally block, attempting close.")
            try:
                await websocket.close(code=1000, reason="Handler cleanup complete")
            except Exception as final_close_exc:
                 logging.warning(f"Exception during final WebSocket close in main handler for {call_sid}: {final_close_exc}")


@app.post("/recording_status")
async def recording_status(request: Request):
    form_data = await request.form();
    logging.info(f"Recording Status Callback: {dict(form_data)}")
    return Response(status_code=200)

@app.post("/transcription_status")
async def transcription_status(request: Request):
    form_data = await request.form();
    logging.info(f"Transcription Status Callback: {dict(form_data)}")
    return Response(status_code=200)