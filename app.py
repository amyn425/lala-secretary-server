"""
LALA Secretary — Step 2 (live <Say>, no MP3 files).

Flow:
  1. Caller dials in -> /voice
  2. LALA greets, then asks who's calling and why.
  3. <Gather> records the caller's speech; Twilio transcribes it.
  4. Twilio POSTs the transcription to /handle_response.
  5. LALA acknowledges and hangs up.

Voice is Twilio <Say>. Voice quality/choice is a swap for later — the
engine (listening + deciding) is what matters next.
"""

from flask import Flask, request, Response

app = Flask(__name__)

# Voice + language. Change VOICE here to try different Twilio voices.
VOICE = "Google.hi-IN-Wavenet-F"
LANG = "hi-IN"
GREETING = "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain."
ASK = "Aap kaun bol rahe hain aur kya kaam hai?"
ACK = "Theek hai, main bhai ko bata doonga."
NO_INPUT = "Maaf kijiye, kuch sunai nahi diya. Bhai ko bata doonga ki aapka phone aaya tha."


def twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def say_slow(text: str) -> str:
    return (
        f'<Say voice="{VOICE}" language="{LANG}">'
        f'<prosody rate="slow">{text}</prosody>'
        f'<break time="400ms"/>'
        f'</Say>'
    )


@app.route("/voice", methods=["GET", "POST"])
def voice():
    gather = (
        f'<Gather input="speech" language="{LANG}" '
        f'speechTimeout="auto" action="/handle_response" method="POST">'
        f'{say_slow(GREETING)}'
        f'{say_slow(ASK)}'
        f'</Gather>'
        f'{say_slow(NO_INPUT)}'
        f'<Hangup/>'
    )
    return twiml(gather)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")
    app.logger.info(f"Caller {caller} said: '{speech}' (confidence={confidence})")

    body = f'{say_slow(ACK)}<Hangup/>'
    return twiml(body)


@app.route("/", methods=["GET"])
def health():
    return "LALA voice server (Step 2, Say mode) is running. Webhook at /voice", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
