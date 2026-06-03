"""
LALA Secretary — Step 2 with PRE-GENERATED AUDIO (free, male Hinglish voice).

Instead of Twilio's robotic <Say>, LALA plays pre-recorded MP3 files you
generate once with a free neural TTS tool (male Indian voice). Twilio just
<Play>s them — free, good quality, works on Render Free tier.

Flow:
  1. Caller dials in -> /voice
  2. LALA plays greeting.mp3, then ask.mp3
  3. <Gather> listens for the caller's speech
  4. Twilio transcribes + POSTs to /handle_response
  5. LALA plays ack.mp3 and hangs up

Audio files live in the /audio folder of this repo and are served by Flask.

Required files in audio/:
  - greeting.mp3   "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain."
  - ask.mp3        "Aap kaun bol rahe hain aur kya kaam hai?"
  - ack.mp3        "Theek hai, main bhai ko bata doonga."
  - noinput.mp3    "Maaf kijiye, kuch sunai nahi diya. Bhai ko bata doonga ki aapka phone aaya tha."
"""

import os
from flask import Flask, request, Response, send_from_directory, url_for

app = Flask(__name__)

LANG = "en-IN"  # for the speech recognizer in <Gather>

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")


def twiml(body: str) -> Response:
    """Wrap a TwiML body in a proper XML response Twilio understands."""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def play(filename: str) -> str:
    """
    A <Play> pointing at one of our MP3s. Twilio needs an absolute, publicly
    reachable URL, so we build it from the incoming request host.
    """
    # _external=True makes a full https://your-app.onrender.com/audio/<file> URL.
    audio_url = url_for("audio", filename=filename, _external=True)
    return f'<Play>{audio_url}</Play>'


@app.route("/audio/<path:filename>", methods=["GET"])
def audio(filename):
    """Serves the MP3 files from the audio/ folder so Twilio can fetch them."""
    return send_from_directory(AUDIO_DIR, filename)


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """
    Entry point. LALA plays greeting + question, then <Gather> listens and
    sends the caller's transcribed speech to /handle_response.
    """
    gather = (
        f'<Gather input="speech" language="{LANG}" '
        f'speechTimeout="auto" action="/handle_response" method="POST">'
        f'{play("greeting.mp3")}'
        f'{play("ask.mp3")}'
        f'</Gather>'
        # If caller says nothing, fall through:
        f'{play("noinput.mp3")}'
        f'<Hangup/>'
    )
    return twiml(gather)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    """
    Twilio posts the caller's transcribed speech here as 'SpeechResult'.
    Step 2: acknowledge (play ack.mp3) and hang up. Transcription is logged.
    """
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")
    app.logger.info(f"Caller {caller} said: '{speech}' (confidence={confidence})")

    body = f'{play("ack.mp3")}<Hangup/>'
    return twiml(body)


@app.route("/", methods=["GET"])
def health():
    """Health check — also reports which audio files are present."""
    files = []
    if os.path.isdir(AUDIO_DIR):
        files = sorted(os.listdir(AUDIO_DIR))
    return (
        "LALA voice server (Step 2, audio mode) is running. Webhook at /voice. "
        f"Audio files found: {files}",
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
