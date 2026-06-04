"""
LALA Secretary — listening fix.

Goal: make Twilio <Gather> actually capture the caller's speech, log it,
then acknowledge and hang up. No contacts, no transfer, no SMS yet.

Key fixes vs. the broken version:
  - Fixed speechTimeout (instead of "auto", which cut off too early).
  - A longer overall 'timeout' so the caller has time to start speaking.
  - speechModel="phone_call" + enhanced for better phone-audio Hinglish.
  - A RETRY: if nothing is captured, LALA re-asks once before giving up.
  - Full logging of SpeechResult / Confidence / From / CallSid.

Flow:
  /voice            -> greet + ask + Gather (attempt 1)
  /handle_response  -> if speech: log + acknowledge + hang up
                       if silence: re-ask + Gather (attempt 2)
                       if still silence: polite close + hang up
"""

from flask import Flask, request, Response

app = Flask(__name__)

# Voice for now — quality doesn't matter for the listening experiment.
VOICE = "Google.hi-IN-Wavenet-F"
LANG = "hi-IN"

GREETING = "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain."
ASK = "Aap kaun bol rahe hain, aur kya kaam hai?"
REASK = "Bhai, phir se boliye. Aap kaun hain aur kya kaam hai?"
ACK = "Theek hai. Main bhai ko aapka message de doonga."
GIVE_UP = "Koi baat nahi. Bhai ko bata doonga ki aapka phone aaya tha."


def twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def say(text: str) -> str:
    """Plain <Say>; voice quality intentionally not a focus right now."""
    return f'<Say voice="{VOICE}" language="{LANG}">{text}</Say>'


def gather(prompt_say: str, attempt: int) -> str:
    """
    A <Gather> that speaks `prompt_say` and then listens.

    - input="speech": we want spoken words, not keypad.
    - speechTimeout="3": wait 3s of silence AFTER speech to decide they're done.
    - timeout="6": wait up to 6s for the caller to START speaking.
    - speechModel="phone_call" + enhanced: tuned for telephone audio.
    - action carries the attempt number so /handle_response knows if this
      was the first try or the retry.
    """
    return (
        f'<Gather input="speech" language="{LANG}" '
        f'speechTimeout="3" timeout="6" '
        f'speechModel="phone_call" enhanced="true" '
        f'action="/handle_response?attempt={attempt}" method="POST">'
        f'{prompt_say}'
        f'</Gather>'
    )


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """Attempt 1: greet, ask, and listen."""
    body = gather(say(GREETING) + say(ASK), attempt=1)
    # If Gather itself times out with no input, it falls through to here:
    body += f'{say(REASK)}'
    body += gather("", attempt=2)  # second listen with no extra prompt
    body += f'{say(GIVE_UP)}<Hangup/>'
    return twiml(body)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    """
    Twilio posts the transcription here. Log everything. If we got speech,
    acknowledge and hang up. If not, re-ask once (attempt 2), then give up.
    """
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")
    call_sid = request.values.get("CallSid", "unknown")
    attempt = request.args.get("attempt", "1")

    app.logger.info(
        f"[LALA] attempt={attempt} CallSid={call_sid} From={caller} "
        f"Confidence={confidence} SpeechResult='{speech}'"
    )

    if speech:
        # Got something — acknowledge and end.
        return twiml(f'{say(ACK)}<Hangup/>')

    # No speech captured.
    if attempt == "1":
        # Retry: re-ask and listen again.
        body = gather(say(REASK), attempt=2)
        body += f'{say(GIVE_UP)}<Hangup/>'
        return twiml(body)
    else:
        # Already retried — give up gracefully.
        return twiml(f'{say(GIVE_UP)}<Hangup/>')


@app.route("/", methods=["GET"])
def health():
    return "LALA voice server (listening fix) is running. Webhook at /voice", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
