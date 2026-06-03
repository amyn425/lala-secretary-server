"""
LALA Secretary — Step 1 voice proof.

A single /voice endpoint that Twilio calls when a phone call comes in.
It returns TwiML telling Twilio to speak one line in LALA's voice, then hang up.

This is intentionally minimal: no contact lookup, no SMS, no message-taking,
no transfer. Just proves a caller hears LALA through Twilio.

Later steps add: contact lookup, <Gather> for the caller's reply, message
recording, transfer to your cell, and an /sms endpoint — all on this same app.
"""

from flask import Flask, request, Response

app = Flask(__name__)

# The one line LALA speaks in Step 1.
LALA_LINE = "Yaa Ali Madad. Main Amin bhai ka secretary hoon. Bhai abhi busy hain."


def twiml(body: str) -> Response:
    """Wrap a TwiML body in a proper XML response Twilio understands."""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """
    Twilio hits this when a call arrives at your Twilio number.
    We tell Twilio to speak LALA's line, then hang up.

    'Polly.Aditi' is an Indian-English voice that handles Hinglish far better
    than the default robotic voice. language='en-IN' sets Indian pronunciation.
    """
    body = (
        f'<Say voice="Polly.Aditi" language="en-IN">{LALA_LINE}</Say>'
        f'<Hangup/>'
    )
    return twiml(body)


@app.route("/", methods=["GET"])
def health():
    """Simple health check so you can confirm the service is awake in a browser."""
    return "LALA voice server is running. Twilio webhook is at /voice", 200


if __name__ == "__main__":
    # Local run only; on Render, gunicorn runs the app (see Procfile).
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
