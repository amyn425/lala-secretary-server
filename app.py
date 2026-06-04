"""
LALA Secretary Server — definitive build.

Features:
  - CONTACTS table (replace placeholder numbers with real ones; match = last 10 digits)
  - Per-caller greetings: Mom, Malka, Lyana, Sisters, Brother-in-law,
    Santosh, Mindi, Store, Friends, VIP friends, Unknown
  - Adaptive follow-up: known callers are NOT asked who they are; they are
    asked only the purpose. Unknown callers are asked for name + message.
    Shared Malka/Lyana number asks which person it is.
  - Language follows caller:
      * Unknown + Mindi + Store -> English greeting + en-IN recognition
      * All other known callers  -> Hindi/Hinglish greeting + hi-IN recognition
  - Beep before each Gather (clear "speak now" cue)
  - print(..., flush=True) logging: INCOMING, RESPONSE, and DECISION
  - Decision categories: urgent_store, callback_request, normal_message, unclear

No transfer, no SMS, no paid AI, no MP3 dependency.
"""

from datetime import datetime
from flask import Flask, request, Response

app = Flask(__name__)

# Voices
VOICE_HI = "Google.hi-IN-Wavenet-F"     # Hindi voice (known callers)
VOICE_EN = "Google.en-IN-Wavenet-F"     # Indian-English voice (unknown / English callers)
HI = "hi-IN"
EN = "en-IN"

# Beep tone played right before listening.
BEEP_URL = "https://sdk.twilio.com/js/client/sounds/releases/1.0.0/dtmf1.mp3"

# ---- CONTACTS: replace placeholder numbers (last 10 digits) ----
# Flags:
#   shared=True  -> two people share this phone; LALA asks which one
#   english=True -> greet + listen in English (en-IN)
#   store=True   -> time-based English store greeting
#   vip=True     -> greet by name
CONTACTS = {
    "5550000001": {
        "name": "Mom",
        "greeting": "Yaa Ali Madad, Mom. Main Amin ka secretary hoon. Amin abhi busy hain. Main bhai ko bata dunga ki aap ne call kiya tha.",
        "ask": "Aap message bol dijiye beep ke baad.",
    },
    "3373755027": {
        "name": "Malka",
        "shared": True,
        "greeting": "Hello. Main bhai ka secretary hoon. Bhai abhi busy hain.",
        "ask": "Aap Malka bhabhi hain ya Lyana beta? Aur kya baat hai, beep ke baad boliye.",
    },
    "5550000003": {
        "name": "Lyana",
        "greeting": "Hello beautiful Lyana. Baba abhi busy hain.",
        "ask": "Aap batao beta, koi important baat hai? Beep ke baad boliye.",
    },
    "5550000004": {
        "name": "Sister",
        "greeting": "Hello sister. Main Amin ka secretary hoon. Bhai abhi busy hain.",
        "ask": "Aap message de dijiye beep ke baad.",
    },
    "5550000005": {
        "name": "Jijaji",
        "greeting": "Hello jijaji. Main Amin ka secretary hoon. Bhai abhi busy hain.",
        "ask": "Kya koi zaroori baat hai? Beep ke baad boliye.",
    },
    "5550000006": {
        "name": "Santosh",
        "greeting": "Namaste Santosh bhai. Main Amin bhai ka secretary hoon.",
        "ask": "Store mein koi urgent baat hai kya? Beep ke baad boliye.",
    },
    "5550000007": {
        "name": "Mindi",
        "english": True,
        "greeting": "Hello Mindi. I am Amin bhai's secretary.",
        "ask": "Is there anything urgent regarding the store? Please speak after the beep.",
    },
    "5550000008": {
        "name": "Store",
        "store": True,
        "english": True,
    },
    "5550000009": {
        "name": "Friend",
        "greeting": "Hello bhai. Main Amin ka secretary hoon. Bhai abhi busy hain.",
        "ask": "Kya message dena hai? Beep ke baad boliye.",
    },
    "5550000010": {"name": "Julian", "vip": True},
    "5550000011": {"name": "Amelie", "vip": True},
    "5550000012": {"name": "Tina", "vip": True},
}

# Unknown callers: assumed English speakers.
UNKNOWN_GREETING = "Hello. I am Amin's secretary. Amin is busy right now."
UNKNOWN_ASK = "Please say your name and message after the beep."

# Shared lines (per language)
REASK_HI = "Bhai, beep ke baad phir se boliye."
REASK_EN = "Please speak again after the beep."
GIVE_UP_HI = "Koi baat nahi. Bhai ko bata doonga ki aapka phone aaya tha."
GIVE_UP_EN = "No problem. I will tell Amin you called."

# Acknowledgement lines per decision category
ACK = {
    "urgent_store":     {"hi": "Theek hai, main abhi bhai ko batata hoon.",
                         "en": "Okay, I will tell Amin right away."},
    "callback_request": {"hi": "Theek hai, bhai ko bol doonga aapko call karne ke liye.",
                         "en": "Okay, I will ask Amin to call you back."},
    "normal_message":   {"hi": "Theek hai, main bhai ko aapka message de doonga.",
                         "en": "Okay, I will give Amin your message."},
    "unclear":          {"hi": "Theek hai, main bhai ko bata doonga.",
                         "en": "Okay, I will let Amin know."},
}

# ---- Decision keywords (matched against the transcription, lowercased) ----
URGENT_WORDS = [
    # English
    "urgent", "emergency", "store", "pos", "register", "cash", "machine",
    "lottery", "problem", "issue", "down", "broken", "not working", "help",
    # hinglish / devanagari
    "जरूरी", "zaroori", "urgent", "store", "मशीन", "machine", "जल्दी", "jaldi",
    "परेशानी", "problem", "खराब", "kharab", "बंद", "band",
]
CALLBACK_WORDS = [
    "call back", "callback", "call me", "phone karna", "call karna",
    "call karne", "phone kare", "वापस", "wapas", "कॉल", "call", "phone karo",
    "ring me", "call back kar",
]


def twiml(body):
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        mimetype="text/xml",
    )


def say(text, english=False):
    v = VOICE_EN if english else VOICE_HI
    lang = EN if english else HI
    return f'<Say voice="{v}" language="{lang}">{text}</Say>'


def beep():
    # Native short pause + spoken-free tone via <Play digits>. Using Twilio's
    # built-in DTMF tone generator (no external file to fetch, can't fail).
    return '<Play digits="9"></Play>'


def time_greeting():
    h = datetime.now().hour
    part = "Good morning" if h < 12 else ("Good afternoon" if h < 17 else "Good evening")
    return f"{part}. This is Amin bhai's secretary."


def last10(number):
    d = "".join(ch for ch in (number or "") if ch.isdigit())
    return d[-10:] if len(d) >= 10 else d


def lookup(number):
    return CONTACTS.get(last10(number))


def is_english_caller(number):
    c = lookup(number)
    if c is None:
        return True  # unknown -> English
    return bool(c.get("english")) or bool(c.get("store"))


def contact_name(number):
    c = lookup(number)
    return c["name"] if c else "Unknown"


def greeting_and_ask(number):
    """Return (greeting_text, ask_text, english_bool)."""
    c = lookup(number)
    if c is None:
        return UNKNOWN_GREETING, UNKNOWN_ASK, True
    if c.get("store"):
        return time_greeting(), "Is this urgent? Please speak after the beep.", True
    if c.get("vip"):
        return (
            f"Hello {c['name']}. Main Amin ka secretary hoon. Bhai abhi busy hain.",
            "Kya koi zaroori baat hai? Beep ke baad boliye.",
            False,
        )
    return c.get("greeting", ""), c.get("ask", ""), bool(c.get("english"))


def classify(speech, caller):
    """
    Rules-based decision. Returns one of:
      urgent_store, callback_request, normal_message, unclear
    Store contacts (Santosh/Mindi/Store) bias toward urgent_store on any
    store keyword. Empty/garbled -> unclear.
    """
    if not speech:
        return "unclear"
    text = speech.lower()
    c = lookup(caller) or {}
    is_store_contact = c.get("name") in ("Santosh", "Mindi", "Store")

    if any(w in text for w in URGENT_WORDS):
        return "urgent_store"
    if any(w in text for w in CALLBACK_WORDS):
        return "callback_request"
    # A store contact who said something non-trivial -> treat as store matter.
    if is_store_contact and len(text.split()) >= 2:
        return "urgent_store"
    if len(text.split()) >= 2:
        return "normal_message"
    return "unclear"


def gather(prompt_say, attempt, english):
    lang = EN if english else HI
    inner = prompt_say + beep()
    return (
        f'<Gather input="speech" language="{lang}" '
        f'speechTimeout="3" timeout="6" speechModel="phone_call" enhanced="true" '
        f'action="/handle_response?attempt={attempt}&amp;en={1 if english else 0}" method="POST">'
        f'{inner}</Gather>'
    )


@app.route("/voice", methods=["GET", "POST"])
def voice():
    caller = request.values.get("From", "unknown")
    call_sid = request.values.get("CallSid", "unknown")
    name = contact_name(caller)
    english = is_english_caller(caller)
    print(
        f"[LALA] INCOMING From={caller} CallSid={call_sid} "
        f"Matched={name} Lang={'en' if english else 'hi'}",
        flush=True,
    )

    greeting, ask, eng = greeting_and_ask(caller)
    reask = REASK_EN if eng else REASK_HI
    giveup = GIVE_UP_EN if eng else GIVE_UP_HI

    body = gather(say(greeting, eng) + say(ask, eng), attempt=1, english=eng)
    body += f'{say(reask, eng)}'
    body += gather("", attempt=2, english=eng)
    body += f'{say(giveup, eng)}<Hangup/>'
    return twiml(body)


@app.route("/handle_response", methods=["GET", "POST"])
def handle_response():
    speech = request.values.get("SpeechResult", "").strip()
    confidence = request.values.get("Confidence", "")
    caller = request.values.get("From", "unknown")
    call_sid = request.values.get("CallSid", "unknown")
    attempt = request.args.get("attempt", "1")
    english = request.args.get("en", "0") == "1"
    name = contact_name(caller)

    print(
        f"[LALA] RESPONSE attempt={attempt} From={caller} Matched={name} "
        f"Lang={'en' if english else 'hi'} CallSid={call_sid} "
        f"Confidence={confidence} SpeechResult='{speech}'",
        flush=True,
    )

    if speech:
        decision = classify(speech, caller)
        print(
            f"[LALA] DECISION From={caller} Matched={name} "
            f"Category={decision} SpeechResult='{speech}'",
            flush=True,
        )
        ack_text = ACK[decision]["en" if english else "hi"]
        return twiml(f'{say(ack_text, english)}<Hangup/>')

    # No speech captured
    reask = REASK_EN if english else REASK_HI
    giveup = GIVE_UP_EN if english else GIVE_UP_HI
    if attempt == "1":
        body = gather(say(reask, english), attempt=2, english=english)
        body += f'{say(giveup, english)}<Hangup/>'
        return twiml(body)
    print(f"[LALA] DECISION From={caller} Matched={name} Category=unclear SpeechResult='' (no input)", flush=True)
    return twiml(f'{say(giveup, english)}<Hangup/>')


@app.route("/", methods=["GET"])
def health():
    return "LALA Secretary Server - adaptive greeting + language + decision logging", 200


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
