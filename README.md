# AI Voice Patient Simulator Bot 🎙️🤖

An agentic testing pipeline built in Python to stress-test AI medical receptionists and automated front-desk systems. By simulating diverse patient personas and injecting specific behavioral scenarios (e.g., weekend bookings, cardiac emergencies, chatty tangents), this bot evaluates boundary conditions, conversational robustness, and safety guardrails.

---

## 🚀 Quick Start (Single-Command Run)

After completing the [Setup](#-setup) instructions below, you can run the entire system in a single command using:

```bash
# Make the run script executable (if needed) and run it
chmod +x run.sh
./run.sh
```

*(Alternatively, run manually: `uvicorn main:app --port 5050 --reload` in one window and `python make_call.py` in another.)*

---

## 🛠️ Setup

### 1. Prerequisites
- **Python 3.10+**
- **ffmpeg** (Required by `pydub` for high-quality MP3/OGG stereo encoding)
  - *macOS:* `brew install ffmpeg`
  - *Ubuntu/Debian:* `sudo apt-get install ffmpeg`

### 2. Installation
Clone the repository, set up a virtual environment, and install dependencies:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file from the example template:
```bash
cp .env.example .env
```
Open [`.env`](file:///Users/mohammed/Downloads/ai-patient-bot/.env) and populate it with your credentials:
- `TWILIO_ACCOUNT_SID` & `TWILIO_AUTH_TOKEN`: Your Twilio account credentials.
- `TWILIO_PHONE_NUMBER`: The outbound phone number provisioned by Twilio.
- `TO_PHONE_NUMBER`: The phone number of the target clinic receptionist bot to stress-test.
- `PUBLIC_URL`: Your public ngrok or local tunnel domain (e.g., `xxxx.ngrok-free.app`), without `https://`.
- `OPENAI_API_KEY`: Your OpenAI API key (supporting the Realtime WebSocket API).

---

## 🏗️ System Architecture & Latency Management

This simulator connects Twilio's bi-directional media streams directly to the OpenAI Realtime API (`gpt-realtime-2`) over full-duplex WebSockets using `asyncio` coroutines. By routing raw audio bytes directly without intermediate text transcription (Speech-to-Text) or speech synthesis (Text-to-Speech) blocks, we bypass traditional pipeline latencies, achieving sub-second conversation response times. 

Incoming G.711 mu-law audio from Twilio is decoded to 16-bit linear PCM in $O(1)$ time via a precomputed lookup table, keeping CPU overhead negligible. Audio from both channels is recorded in stereo layout (Inbound/Left, Outbound/Right) and padded with time-aligned silence to accurately capture interruptions and conversational turn-taking behaviors.

---

## 📁 Repository Structure

* [**`main.py`**](file:///Users/mohammed/Downloads/ai-patient-bot/main.py): The FastAPI core server. Establishes the Twilio media stream WebSocket, hooks into OpenAI Realtime (`gpt-realtime-2`), manages bi-directional audio routing, and records calls.
* [**`make_call.py`**](file:///Users/mohammed/Downloads/ai-patient-bot/make_call.py): Outbound call trigger script. Lets you choose a patient scenario via terminal menu and kicks off the Twilio call.
* [**`scenarios.py`**](file:///Users/mohammed/Downloads/ai-patient-bot/scenarios.py): Profile database containing the 10 custom patient personas/scenarios with system prompts and injection tests.
* [**`audio_converter.py`**](file:///Users/mohammed/Downloads/ai-patient-bot/audio_converter.py): Utilities to encode raw linear PCM audio into stereo MP3 and OGG formats.
* [**`utils.py`**](file:///Users/mohammed/Downloads/ai-patient-bot/utils.py): Lower-level audio helper functions, including a lookup table to decode G.711 mu-law bytes to 16-bit PCM.
* [**`BUG_REPORT.md`**](file:///Users/mohammed/Downloads/ai-patient-bot/BUG_REPORT.md): Bug report detailing schedule validations, emergency triage handoff failure, and conversation drift observed during the stress tests.
* [**`ARCHITECTURE.md`**](file:///Users/mohammed/Downloads/ai-patient-bot/ARCHITECTURE.md): Detailed architectural explanation and design rationale.

---

## 🧬 Patient Scenarios

When you run `python make_call.py`, you can select from **10 testing scenarios** configured in [`scenarios.py`](file:///Users/mohammed/Downloads/ai-patient-bot/scenarios.py):
1. **Standard Clinic Receptionist**: Polite, normal booking dialog.
2. **Strict Weekend Closed Rule**: Attempts to book on a Sunday (tests BUG-01).
3. **Chatty / Slow-Paced Receptionist**: Talks in long tangents to test turn-taking and interruptions (tests BUG-03).
4. **Strict Insurance Gatekeeper**: Requires verified insurance before choosing times.
5. **High-Alert Triage Agent**: Describes severe chest numbness to trigger medical safety warnings (tests BUG-02).
6. **Detail-Oriented Clinical Assistant**: Presses the bot for precise pain severity scales.
7. **Identity Verification Agent**: Demands full verification steps.
8. **Medication Refill Gatekeeper**: Validates refills against bottle/dosage names.
9. **Rapid-Fire Booking Agent**: Speaks quickly and offers sudden schedules to test comprehension speed.
10. **Flexible Appointment Changer**: Drops appointments mid-stream to test dynamic adaptation.

---

## 🎙️ Transcripts & Recordings
All transcripts and stereo call recordings are automatically captured after calls finish:
* Transcripts are written to the [`transcripts/`](file:///Users/mohammed/Downloads/ai-patient-bot/transcripts) directory.
* High-quality stereo audio files are exported to [`recordings/`](file:///Users/mohammed/Downloads/ai-patient-bot/recordings).
  > [!NOTE]
  > Recordings are stereo-aligned: **Left Channel** captures the inbound agent/receptionist, and **Right Channel** captures our patient simulator bot.
