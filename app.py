"""
LALA Secretary — Step 2 voice + listen.

Flow:
  1. Caller dials in -> /voice
  2. LALA speaks the greeting (slowed), then asks who's calling and why.
  3. <Gather> records the caller's speech and Twilio transcribes it.
  4. Twilio POSTs the transcription to /handle_response.
  5. LALA acknowledges ("Theek hai, main bhai ko bata doonga.") and hangs up.

Still no contact lookup, no message recording, no transfer, no SMS — those
come in later steps. The two-endpoint pattern here (speak -> gather ->
handle) is the foundation everything else builds on.

Render Free tier: fine for testing (wake /voice in a browser first).
"""

from flask import Flask, request, Response

app = Flask(__name__)

# Voice + language for Amazon Polly (Indian English, handles Hinglish best).
VOICE = "Polly.Aditi"
LANG = "en-IN"

# Lines LALA speaks.
GREETING = "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain."
ASK = "Aap kaun bol rahe hain aur kya kaam hai?"
ACK = "Theek hai, main bhai ko bata doonga."
NO_INPUT = "Maaf kijiye, kuch sunai nahi diya. Bhai ko bata doonga ki aapka phone aaya tha."


def twiml(body: str) -> Response:
    """Wrap a TwiML body in a proper XML response Twilio understands."""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def say_slow(text: str) -> str:
    """
    A <Say> block slowed down with SSML prosody + a short trailing pause.
    'rate=slow' paces the speech; the break adds breathing room after.
    """
    return (
        f'<Say voice="{VOICE}" language="{LANG}">'
        f'<prosody rate="slow">{text}</prosody>'
        f'<break time="400ms"/>'
        f'</Say>'
    )


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """
    Entry point when a call arrives. LALA greets, asks who's calling, then
    <Gather> listens for the caller's spoken reply and sends it to
    /handle_response.
    """
    gather = (
        f'<Gather input="speech" language="{LANG}" '
        f'speechTimeout="auto" action="/handle_response" method="POST">'
        f'{say_slow(GREETING)}'
        f'{say_slow(ASK)}'
        f'</Gather>'
        # If the caller says nothing, <Gather> falls through to here.
        f'{say_slow(NO_INPUT)}'
        f'<Hangup/>'
    )
    return twiml(gather)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    """
    Twilio posts the caller's transcribed speech here as 'SpeechResult'.
    For Step 2 we just acknowledge and hang up. The transcription is logged
    so you can see what Twilio heard (later steps will act on it).
    """
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")

    # Logged to Render logs — your window into what Twilio transcribed.
    app.logger.info(f"Caller {caller} said: '{speech}' (confidence={confidence})")

    body = f'{say_slow(ACK)}<Hangup/>'
    return twiml(body)


@app.route("/", methods=["GET"])
def health():
    """Health check — visit in a browser to confirm the service is awake."""
    return "LALA voice server (Step 2) is running. Webhook at /voice", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
