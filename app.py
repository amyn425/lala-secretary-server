"""
LALA Secretary — listening fix + per-caller greetings.

Changes:
  1. Logging uses print(..., flush=True) so From / CallSid / SpeechResult /
     Confidence always appear in Render logs (stdout, unbuffered).
  2. Greeting is chosen by the caller's phone number (CONTACTS table below).
     Replace the placeholder numbers with the real ones.

Still no transfer, no SMS, no message storage — just greet correctly,
capture speech, log it, acknowledge, hang up.
"""

from flask import Flask, request, Response

app = Flask(__name__)

VOICE = "Google.hi-IN-Wavenet-F"
LANG = "hi-IN"

# ---- Contacts: replace placeholder numbers with real ones ----
# Match is on the last 10 digits, so formatting (+1, spaces) doesn't matter.
# 'lang' just notes intended tone; the greeting text is what's spoken.
CONTACTS = {
    "5550000001": {  # <-- REPLACE: Malka
        "name": "Malka",
        "greeting": "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain.",
    },
    "3373755027": {  # <-- REPLACE: Lyana (calls may come from Malka's phone too)
        "name": "Lyana",
        "greeting": "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain.",
    },
    "5550000003": {  # <-- REPLACE: Santosh (store)
        "name": "Santosh",
        "greeting": "Namaste Santosh bhai. Main Amin bhai ka secretary hoon. Store mein koi urgent baat hai kya?",
    },
    "5550000004": {  # <-- REPLACE: Mindi (store)
        "name": "Mindi",
        "greeting": "Hello Mindi. I am Amin bhai's secretary. Is there anything urgent regarding the store?",
    },
}

# Default greeting for any number not in CONTACTS.
UNKNOWN_GREETING = "Hello. I am Amin bhai's secretary. Amin bhai is busy right now."

# Shared follow-up lines.
ASK = "Aap kaun bol rahe hain, aur kya kaam hai?"
REASK = "Bhai, phir se boliye. Aap kaun hain aur kya kaam hai?"
ACK = "Theek hai. Main bhai ko aapka message de doonga."
GIVE_UP = "Koi baat nahi. Bhai ko bata doonga ki aapka phone aaya tha."


def twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def say(text: str) -> str:
    return f'<Say voice="{VOICE}" language="{LANG}">{text}</Say>'


def gather(prompt_say: str, attempt: int) -> str:
    return (
        f'<Gather input="speech" language="{LANG}" '
        f'speechTimeout="3" timeout="6" '
        f'speechModel="phone_call" enhanced="true" '
        f'action="/handle_response?attempt={attempt}" method="POST">'
        f'{prompt_say}'
        f'</Gather>'
    )


def last10(number: str) -> str:
    """Reduce a phone number to its last 10 digits for tolerant matching."""
    digits = "".join(ch for ch in (number or "") if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def greeting_for(number: str) -> str:
    """Pick the greeting based on the caller's number."""
    contact = CONTACTS.get(last10(number))
    if contact:
        return contact["greeting"]
    return UNKNOWN_GREETING


def contact_name(number: str) -> str:
    contact = CONTACTS.get(last10(number))
    return contact["name"] if contact else "Unknown"


@app.route("/voice", methods=["GET", "POST"])
def voice():
    caller = request.values.get("From", "unknown")
    call_sid = request.values.get("CallSid", "unknown")
    name = contact_name(caller)

    print(f"[LALA] INCOMING From={caller} CallSid={call_sid} Matched={name}", flush=True)

    greeting = greeting_for(caller)
    body = gather(say(greeting) + say(ASK), attempt=1)
    body += f'{say(REASK)}'
    body += gather("", attempt=2)
    body += f'{say(GIVE_UP)}<Hangup/>'
    return twiml(body)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")
    call_sid = request.values.get("CallSid", "unknown")
    attempt = request.args.get("attempt", "1")
    name = contact_name(caller)

    print(
        f"[LALA] RESPONSE attempt={attempt} From={caller} Matched={name} "
        f"CallSid={call_sid} Confidence={confidence} SpeechResult='{speech}'",
        flush=True,
    )

    if speech:
        return twiml(f'{say(ACK)}<Hangup/>')

    if attempt == "1":
        body = gather(say(REASK), attempt=2)
        body += f'{say(GIVE_UP)}<Hangup/>'
        return twiml(body)
    else:
        return twiml(f'{say(GIVE_UP)}<Hangup/>')


@app.route("/", methods=["GET"])
def health():
    return "LALA voice server (greetings + logging) is running. Webhook at /voice", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
