import os
import json
import asyncio
import base64
import time
from fastapi import FastAPI, Response, Request, WebSocket
from dotenv import load_dotenv
import websockets

from utils import decode_ulaw_bytes, save_wav_stereo, ensure_directories
from scenarios import get_scenario
from audio_converter import save_pcm_as_mp3_ogg
from twilio.twiml.voice_response import VoiceResponse

load_dotenv()

def get_elapsed_timestamp(start_time: float) -> str:
    """Calculates [MM:SS] formatted timestamp relative to start_time."""
    elapsed = int(time.time() - start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60
    return f"[{minutes:02d}:{seconds:02d}]"

# Validate crucial environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PUBLIC_URL = os.getenv("PUBLIC_URL")

if not OPENAI_API_KEY:
    print("[WARNING] OPENAI_API_KEY environment variable is not set. The media stream will fail to connect to OpenAI.")
if not PUBLIC_URL:
    print("[WARNING] PUBLIC_URL environment variable is not set. Twilio webhooks will fail to locate this server.")

app = FastAPI(
    title="AI Voice Patient Simulator Bot",
    description="FastAPI server that streams outbound calls to OpenAI Realtime to simulate a patient."
)

# Ensure recordings/ and transcripts/ directories exist
ensure_directories()

# Scenarios are dynamically loaded from scenarios.py based on scenario_id query parameter.

@app.get("/")
async def root():
    return {"status": "running", "message": "AI Patient Bot FastAPI Server"}

@app.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio POST Webhook. When the outbound call connects, Twilio queries this endpoint
    and receives TwiML directing it to connect to our WebSocket server for bi-directional streaming.
    """
    # Try to get scenario_id from query parameters first
    scenario_id = request.query_params.get("scenario_id")
    
    # If not in query parameters, try to parse from the POST body (form-encoded)
    if not scenario_id:
        try:
            body = await request.body()
            if body:
                from urllib.parse import parse_qs
                form_data = parse_qs(body.decode("utf-8"))
                scenario_ids = form_data.get("scenario_id")
                if scenario_ids:
                    scenario_id = scenario_ids[0]
        except Exception as e:
            print(f"Error parsing form data in incoming-call: {e}")
            
    # Default to "default_receptionist" if still not found
    if not scenario_id:
        scenario_id = "default_receptionist"

    print(f"Received incoming-call webhook from Twilio with scenario_id: {scenario_id}")
    
    # We clean the public URL to construct the WSS path
    cleaned_url = PUBLIC_URL.replace("https://", "").replace("http://", "").strip("/")
    
    # Use VoiceResponse to generate perfectly formatted XML so Twilio doesn't crash
    response = VoiceResponse()
    connect = response.connect()
    connect.stream(url=f"wss://{cleaned_url}/media-stream?scenario_id={scenario_id}")
    
    return Response(content=response.to_xml(), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """
    FastAPI WebSocket endpoint handling the bi-directional stream from Twilio
    and bridging it with OpenAI's Realtime API.
    """
    await websocket.accept()
    
    # Extract scenario_id from query parameters
    scenario_id = websocket.query_params.get("scenario_id", "default_receptionist")
    scenario = get_scenario(scenario_id)
    instructions = scenario["instructions"]
    
    print(f"Twilio WebSocket connection accepted for scenario_id: {scenario_id} ({scenario['name']})")
    
    # Initialize session recorders & state variables
    start_time = time.time()
    inbound_pcm = []
    outbound_pcm = []
    transcripts = []
    
    stream_sid = None
    call_sid = "unknown_call"
    
    # Configure OpenAI Realtime API headers
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    openai_url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2"
    
    async def run_bridge(openai_ws):
        # Send initial session configuration to OpenAI
        session_update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "instructions": instructions,
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcmu"
                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.8,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 1000
                        },
                        "transcription": {
                            "model": "gpt-realtime-whisper"
                        }
                    },
                    "output": {
                        "format": {
                            "type": "audio/pcmu"
                        },
                        "voice": "ash"
                    }
                }
            }
        }
        await openai_ws.send(json.dumps(session_update))
        print("Session configuration update sent to OpenAI.")
        
        # Send response.create to force the model to speak first
        response_create = {
            "type": "response.create",
            "response": {}
        }
        await openai_ws.send(json.dumps(response_create))
        print("Initial response.create event sent to OpenAI.")
        
        async def twilio_to_openai():
            """Task: Receive audio from Twilio and forward it to OpenAI."""
            nonlocal stream_sid, call_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event = data.get("event")
                    
                    if event == "media":
                        media = data["media"]
                        payload = media["payload"]
                        
                        # 1. Record inbound audio (receptionist speaking)
                        inbound_bytes = base64.b64decode(payload)
                        inbound_pcm.extend(decode_ulaw_bytes(inbound_bytes))
                        
                        # 2. Forward to OpenAI Realtime API
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": payload
                        }))
                        
                    elif event == "start":
                        stream_sid = data["start"]["streamSid"]
                        call_sid = data["start"].get("callSid", "no_call_sid")
                        print(f"Twilio stream started: StreamSid={stream_sid}, CallSid={call_sid}")
                        
                    elif event == "stop":
                        print("Twilio stream sent stop event.")
                        break
                        
            except Exception as e:
                print(f"Error in twilio_to_openai: {e}")
        
        async def openai_to_twilio():
            """Task: Receive events/audio from OpenAI and forward it to Twilio."""
            nonlocal stream_sid, call_sid
            try:
                async for message in openai_ws:
                    response = json.loads(message)
                    event_type = response.get("type")
                    
                    if event_type in ("error", "warning"):
                        print(f"[OpenAI {event_type.upper()}] {response}")
                    
                    # 1. Handle incoming audio delta from OpenAI (our simulated patient speaking)
                    if event_type == "response.output_audio.delta":
                        payload = response.get("delta")
                        if payload:
                            # Record outbound audio aligned to start timeline
                            outbound_bytes = base64.b64decode(payload)
                            pcm_samples = decode_ulaw_bytes(outbound_bytes)
                            
                            current_time = time.time()
                            target_index = int((current_time - start_time) * 8000)
                            
                            # Align using padding
                            if len(outbound_pcm) < target_index:
                                outbound_pcm.extend([0] * (target_index - len(outbound_pcm)))
                            outbound_pcm.extend(pcm_samples)
                            
                            # Send audio payload back to Twilio
                            if stream_sid:
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": payload
                                    }
                                })
                                
                    # 2. Handle interruption: receptionist speaking while patient was outputting audio
                    elif event_type == "input_audio_buffer.speech_started":
                        print("Receptionist speech detected. Truncating patient output to handle interruption.")
                        if stream_sid:
                            await websocket.send_json({
                                "event": "clear",
                                "streamSid": stream_sid
                            })
                            
                    # 3. Save receptionist transcript
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = response.get("transcript", "").strip()
                        if transcript:
                            ts = get_elapsed_timestamp(start_time)
                            entry = f"{ts} Agent: {transcript}"
                            transcripts.append(entry)
                            print(f"Transcript -> {entry}")
                            
                    # 4. Save patient transcript
                    elif event_type == "response.audio_transcript.done":
                        transcript = response.get("transcript", "").strip()
                        if transcript:
                            ts = get_elapsed_timestamp(start_time)
                            entry = f"{ts} Patient: {transcript}"
                            transcripts.append(entry)
                            print(f"Transcript -> {entry}")
                            
            except Exception as e:
                print(f"Error in openai_to_twilio: {e}")
        
        # Start concurrent processing loops
        t_twilio = asyncio.create_task(twilio_to_openai())
        t_openai = asyncio.create_task(openai_to_twilio())
        
        # Wait until one of the loops terminates (e.g. call hangs up or connection fails)
        done, pending = await asyncio.wait(
            [t_twilio, t_openai],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel the remaining task
        for task in pending:
            task.cancel()

    print("Connecting to OpenAI Realtime API...")
    try:
        try:
            # Try connecting using the standard additional_headers keyword
            async with websockets.connect(
                openai_url, 
                additional_headers=headers
            ) as openai_ws:
                print("Successfully connected to OpenAI Realtime API (using additional_headers).")
                await run_bridge(openai_ws)
        except TypeError:
            # Fallback if the library version expects extra_headers
            async with websockets.connect(
                openai_url, 
                extra_headers=headers
            ) as openai_ws:
                print("Successfully connected to OpenAI Realtime API (using extra_headers).")
                await run_bridge(openai_ws)
    except Exception as e:
        print(f"Connection error inside WebSocket bridge: {e}")
        
    finally:
        print("Closing stream connection. Saving call assets...")
        
        # Standardize files using the CallSid and scenario_id
        wav_path = f"recordings/{call_sid}_{scenario_id}.wav"
        txt_path = f"transcripts/{call_sid}_{scenario_id}.txt"
        mp3_path = f"recordings/{call_sid}_{scenario_id}.mp3"
        
        # Save recording if audio exists
        if inbound_pcm or outbound_pcm:
            try:
                save_wav_stereo(wav_path, inbound_pcm, outbound_pcm)
                print(f"Saved recording to: {wav_path}")
            except Exception as e:
                print(f"Failed to save WAV: {e}")
                
            try:
                # Save high-quality MP3 (will notify/fail gracefully if ffmpeg is missing)
                save_pcm_as_mp3_ogg(inbound_pcm, outbound_pcm, mp3_path, fmt="mp3")
            except Exception as e:
                print(f"Failed to save MP3: {e}")
                
        # Save transcript if text dialogues exist
        if transcripts:
            try:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(transcripts))
                print(f"Saved transcript to: {txt_path}")
            except Exception as e:
                print(f"Failed to save transcript: {e}")
        else:
            print("No dialogues transcribed to write to file.")
            
        print("Cleaned up and closed WebSocket session.")
