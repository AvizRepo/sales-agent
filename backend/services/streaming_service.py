import asyncio
import base64
import json
import os
import aiohttp 
import numpy as np
import soundfile as sf
from io import BytesIO
import logging
import ssl
from starlette.websockets import WebSocketState, WebSocketDisconnect

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/agent"
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
TWILIO_SAMPLE_RATE = 8000

logging.info(f"Using aiohttp version: {aiohttp.__version__}")


async def resample_audio(audio_data: bytes, current_rate: int, target_rate: int) -> bytes:
    """Resamples raw audio data using numpy and soundfile."""
    if not audio_data: return b''
    try:
        audio_np, _ = sf.read(BytesIO(audio_data), dtype='int16', channels=1, samplerate=current_rate, format='RAW', subtype='PCM_16')
        if current_rate == target_rate: return audio_data
        num_samples = len(audio_np)
        target_num_samples = int(num_samples * target_rate / current_rate)
        if num_samples > 0 and target_num_samples == 0: target_num_samples = 1
        if target_num_samples == 0: return b''
        resampled_audio = np.interp(
            np.linspace(0, num_samples -1 if num_samples > 0 else 0, target_num_samples),
            np.arange(num_samples), audio_np
        ).astype(np.int16)
        output_buffer = BytesIO()
        sf.write(output_buffer, resampled_audio, target_rate, format='RAW', subtype='PCM_16')
        return output_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error during resampling from {current_rate} to {target_rate}: {e}", exc_info=True)
        return b''

async def decode_twilio_mulaw(base64_data: str) -> bytes:
    """Decodes Twilio's base64 Mulaw audio to raw PCM bytes."""
    if not base64_data: return b''
    try:
        mulaw_data = base64.b64decode(base64_data)
        if not mulaw_data: return b''
        pcm_data, sr = sf.read(BytesIO(mulaw_data), dtype='int16', channels=1, samplerate=TWILIO_SAMPLE_RATE, format='RAW', subtype='ULAW')
        output_buffer = BytesIO()
        sf.write(output_buffer, pcm_data, TWILIO_SAMPLE_RATE, format='RAW', subtype='PCM_16')
        return output_buffer.getvalue()
    except sf.SoundFileError as sf_err:
         logging.error(f"SoundFileError decoding Twilio Mulaw: {sf_err} (Payload Size: {len(base64_data)})", exc_info=False)
         return b''
    except Exception as e:
        logging.error(f"Error decoding Twilio Mulaw: {e}", exc_info=True)
        return b''

async def encode_to_twilio_mulaw(pcm_data: bytes, sample_rate: int) -> str:
    """Encodes raw PCM audio bytes (from Deepgram) to base64 Mulaw for Twilio."""
    if not pcm_data: return ""
    try:
        if sample_rate != TWILIO_SAMPLE_RATE:
            logging.debug(f"Resampling Deepgram output from {sample_rate}Hz to {TWILIO_SAMPLE_RATE}Hz for Twilio")
            pcm_data = await resample_audio(pcm_data, sample_rate, TWILIO_SAMPLE_RATE)
            if not pcm_data:
                logging.error("Resampling Deepgram output failed, returning empty.")
                return ""
        audio_np, read_sr = sf.read(BytesIO(pcm_data), dtype='int16', channels=1, samplerate=TWILIO_SAMPLE_RATE, format='RAW', subtype='PCM_16')
        if read_sr != TWILIO_SAMPLE_RATE:
             logging.warning(f"Read sample rate {read_sr} != expected {TWILIO_SAMPLE_RATE} before Mulaw encoding.")
        output_buffer = BytesIO()
        sf.write(output_buffer, audio_np, TWILIO_SAMPLE_RATE, format='RAW', subtype='ULAW')
        mulaw_data = output_buffer.getvalue()
        base64_encoded = base64.b64encode(mulaw_data).decode('utf-8')
        return base64_encoded
    except Exception as e:
        logging.error(f"Error encoding to Twilio Mulaw: {e}", exc_info=True)
        return ""


async def handle_deepgram_connection(twilio_ws, call_sid: str, company_name: str, knowledge_summary: str):
    """Handles the connection to Deepgram Agent using aiohttp and bridges audio with Twilio."""
    if not DEEPGRAM_API_KEY:
        logging.error(f"[{call_sid}] Error: DEEPGRAM_API_KEY not found.")
        if twilio_ws.client_state == WebSocketState.CONNECTED:
            await twilio_ws.close(code=1011, reason="Internal configuration error")
        return

    logging.info(f"[{call_sid}] Attempting to connect to Deepgram Agent using aiohttp.")
    deepgram_aiohttp_ws = None 
    twilio_stream_sid = "UNKNOWN"
    forward_twilio_task = None
    forward_deepgram_task = None
    aiohttp_session = None 

    try:
        aiohttp_session = aiohttp.ClientSession()

        deepgram_headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

        async with aiohttp_session.ws_connect(
            DEEPGRAM_AGENT_URL,
            headers=deepgram_headers,
            # timeout=30.0 
        ) as dg_ws:
            deepgram_aiohttp_ws = dg_ws 
            logging.info(f"[{call_sid}] Successfully connected to Deepgram Agent (aiohttp).")

            agent_instructions = (
                f"You are an AI voice calling agent named Emma from {company_name or 'our company'}. "
                f"Your goal is to engage the user, briefly introduce the services based on the following summary, "
                f"understand their needs, and ultimately try to book a follow-up demo call. "
                f"Keep responses concise and conversational for a voice call.\n\n"
                f"Knowledge Summary:\n{knowledge_summary or 'No specific product knowledge provided.'}"
            )
            settings = {
                "type": "SettingsConfiguration", "audio": {"input": {"encoding": "linear16", "sample_rate": INPUT_SAMPLE_RATE}, "output": {"encoding": "linear16", "sample_rate": OUTPUT_SAMPLE_RATE, "container": "none"}},
                "agent": {"listen": {"model": "nova-2"}, "think": {"provider": {"type": "open_ai"}, "model": "gpt-4o", "instructions": agent_instructions}, "speak": {"model": "aura-asteria-en"}}
            }
            await deepgram_aiohttp_ws.send_str(json.dumps(settings))
            logging.info(f"[{call_sid}] Sent configuration to Deepgram (aiohttp).")

            async def forward_twilio_to_deepgram_task_func():
                nonlocal twilio_stream_sid
                """Task to receive audio from Twilio and forward to Deepgram via aiohttp."""
                while True:
                    try:
                        if twilio_ws.client_state != WebSocketState.CONNECTED or deepgram_aiohttp_ws.closed:
                            logging.warning(f"[{call_sid}] WS state invalid, stopping forward_twilio task. Twilio: {twilio_ws.client_state}, Deepgram Closed: {deepgram_aiohttp_ws.closed}")
                            break
                        message = await twilio_ws.receive_text()
                        data = json.loads(message)
                        event = data.get('event')
                        if event == 'start':
                            twilio_stream_sid = data.get('streamSid', 'UNKNOWN')
                            logging.info(f"[{call_sid}] Twilio Stream Started: {twilio_stream_sid}")
                        elif event == 'media':
                            payload = data.get('media', {}).get('payload')
                            if not payload: continue
                            pcm_8k_data = await decode_twilio_mulaw(payload)
                            if pcm_8k_data:
                                pcm_16k_data = await resample_audio(pcm_8k_data, TWILIO_SAMPLE_RATE, INPUT_SAMPLE_RATE)
                                if pcm_16k_data and not deepgram_aiohttp_ws.closed:
                                    
                                    await deepgram_aiohttp_ws.send_bytes(pcm_16k_data)
                        elif event == 'stop':
                            logging.info(f"[{call_sid}] Twilio Stream Stopped.")
                            break
                        elif event == 'mark':
                             logging.info(f"[{call_sid}] Received Twilio Mark: {data.get('mark', {}).get('name')}")
                    except WebSocketDisconnect:
                         logging.info(f"[{call_sid}] Twilio WebSocket disconnected (forward_twilio task).")
                         break
                    except json.JSONDecodeError as e:
                        logging.error(f"[{call_sid}] Error decoding JSON from Twilio: {e} - Message: {message[:100]}...")
                    except Exception as e: 
                        logging.error(f"[{call_sid}] Error in forward_twilio task (aiohttp): {e}", exc_info=True)
                        break
                if not deepgram_aiohttp_ws.closed:
                     logging.info(f"[{call_sid}] forward_twilio task ending, closing Deepgram WS (aiohttp).")
                     await deepgram_aiohttp_ws.close()

            async def forward_deepgram_to_twilio_task_func():
                """Task to receive audio from Deepgram via aiohttp and forward to Twilio."""
                while True:
                    try:
                        if deepgram_aiohttp_ws.closed or twilio_ws.client_state != WebSocketState.CONNECTED:
                             logging.warning(f"[{call_sid}] WS state invalid, stopping forward_deepgram task. Deepgram Closed: {deepgram_aiohttp_ws.closed}, Twilio: {twilio_ws.client_state}")
                             break

                        msg = await deepgram_aiohttp_ws.receive()

                        if msg.type == aiohttp.WSMsgType.BINARY:
                             if not msg.data: continue
                             base64_mulaw_output = await encode_to_twilio_mulaw(msg.data, OUTPUT_SAMPLE_RATE)
                             if base64_mulaw_output and twilio_ws.client_state == WebSocketState.CONNECTED:
                                 await twilio_ws.send_text(json.dumps({
                                     "event": "media", "streamSid": twilio_stream_sid,
                                     "media": {"payload": base64_mulaw_output}
                                 }))
                        elif msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                dg_data = json.loads(msg.data)
                                logging.info(f"[{call_sid}] Deepgram Text (aiohttp): {json.dumps(dg_data)}")
                            except json.JSONDecodeError:
                                 logging.warning(f"[{call_sid}] Received non-JSON text from Deepgram (aiohttp): {msg.data[:100]}")
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                             logging.info(f"[{call_sid}] Deepgram WebSocket closed message received (aiohttp).")
                             break 
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                             logging.error(f"[{call_sid}] Deepgram WebSocket error message received (aiohttp): {deepgram_aiohttp_ws.exception()}")
                             break 
                    except WebSocketDisconnect:
                        logging.warning(f"[{call_sid}] Twilio connection closed during send in forward_deepgram task (aiohttp).")
                        break
                    except Exception as e: 
                        logging.error(f"[{call_sid}] Error in forward_deepgram task (aiohttp): {e}", exc_info=True)
                        break
                if twilio_ws.client_state == WebSocketState.CONNECTED:
                    logging.info(f"[{call_sid}] forward_deepgram task ending, closing Twilio WS.")
                    await twilio_ws.close()


            forward_twilio_task = asyncio.create_task(forward_twilio_to_deepgram_task_func())
            forward_deepgram_task = asyncio.create_task(forward_deepgram_to_twilio_task_func())
            await asyncio.gather(forward_twilio_task, forward_deepgram_task)
            logging.info(f"[{call_sid}] Both forwarding tasks finished (aiohttp).")

    # --- Exception Handling ---
    except aiohttp.ClientConnectionError as e: 
         logging.error(f"[{call_sid}] aiohttp failed to connect to Deepgram: {e}", exc_info=True)
         if twilio_ws.client_state == WebSocketState.CONNECTED:
             await twilio_ws.close(code=1011, reason="Failed to connect to AI Agent")
    except aiohttp.WSServerHandshakeError as e: 
        logging.error(f"[{call_sid}] aiohttp Deepgram handshake error (check API key?): {e}", exc_info=True)
        if twilio_ws.client_state == WebSocketState.CONNECTED:
            await twilio_ws.close(code=1011, reason="AI Agent authentication error")
    except Exception as e: 
        logging.error(f"[{call_sid}] Unexpected error in handle_deepgram_connection (aiohttp): {e}", exc_info=True)
        if twilio_ws.client_state == WebSocketState.CONNECTED:
            await twilio_ws.close(code=1011, reason="Unexpected agent error")


    finally:
        logging.info(f"[{call_sid}] Cleaning up Deepgram connection handler (aiohttp).")
        if forward_twilio_task and not forward_twilio_task.done():
             forward_twilio_task.cancel()
             logging.info(f"[{call_sid}] Cancelled forward_twilio task.")
        if forward_deepgram_task and not forward_deepgram_task.done():
             forward_deepgram_task.cancel()
             logging.info(f"[{call_sid}] Cancelled forward_deepgram task.")

        if aiohttp_session and not aiohttp_session.closed:
            logging.info(f"[{call_sid}] Closing aiohttp ClientSession.")
            await aiohttp_session.close()


        if twilio_ws.client_state == WebSocketState.CONNECTED:
            logging.info(f"[{call_sid}] Closing Twilio WS in finally block (aiohttp handler).")
            try: await twilio_ws.close(code=1000, reason="Handler finished cleanup")
            except Exception as close_exc: logging.warning(f"[{call_sid}] Exception during final Twilio WS close: {close_exc}")
        logging.info(f"[{call_sid}] Deepgram handler cleanup finished (aiohttp).")