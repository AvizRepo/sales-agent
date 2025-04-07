# AI Sales Agent

An AI-powered voice sales agent that makes outbound calls, engages users in natural conversation, and books follow-up demo calls. Built with Twilio for telephony, Deepgram for AI voice interaction (using OpenAI GPT-4o), and a FastAPI/React stack.

## Features
- **Outbound Calls**: Users can request calls via a React frontend; Twilio initiates the call.
- **Real-Time Voice Interaction**: The AI agent "Emma" uses Deepgram to listen, think (via GPT-4o), and speak naturally.
- **Admin Dashboard**: Configure the company name and knowledge summary for the AI agent.
- **Audio Streaming**: Bidirectional WebSocket streaming between Twilio and Deepgram with audio resampling.

## Tech Stack
- **Backend**: FastAPI (Python), WebSockets, `numpy`, `soundfile`, `aiohttp`
- **Frontend**: React, React Router
- **Telephony**: Twilio
- **AI Voice**: Deepgram Agent (OpenAI GPT-4o, Aura-Asteria TTS)
- **Dependencies**: See `backend/requirements.txt` and `frontend/package.json`

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- Twilio account (API credentials)
- Deepgram account (API key)
- Git installed

### Backend Setup
1. Navigate to `backend/`:
   ```bash
   cd backend
   ```
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set environment variables in a `.env` file:
   ```
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_PHONE_NUMBER=your_twilio_number
   PUBLIC_BASE_URL=https://your-public-url
   DEEPGRAM_API_KEY=your_deepgram_key
   ```
5. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup
1. Navigate to `frontend/`:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   - Access at `http://localhost:5173`.

### Running the Agent
1. Start the backend server.
2. Run `npx localtunnel --port 3000 --subdomain mycustomname` on terminal to expose backend API to internet for Twilio WebSocket connectivity.
3. Start the frontend.
4. Log in as:
   - **Admin**: `admin/pass` at `/company-login`
   - **User**: `user/pass` at `/`
5. Configure company info and knowledge via the admin dashboard.
6. Request a call as a user with a valid phone number.

## Limitations
- No database; data is stored in memory.
- Hardcoded frontend credentials.
- Conversation history endpoint is not yet implemented.
- Requires a public URL (e.g., localtunnel) for Twilio WebSocket connectivity.

## Future Improvements
- Add a database (e.g., Mongo) for persistence.
- Implement secure authentication (JWT, OAuth).
- Store and retrieve conversation logs.
- Enhance error handling and logging.
