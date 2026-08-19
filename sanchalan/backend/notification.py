"""Twilio SMS notification service (Phase 5).

Requires environment variables:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER
  TWILIO_TO_NUMBER

If Twilio is not configured, notifications are logged but not sent.
"""

import os
from datetime import datetime


def is_twilio_configured() -> bool:
    return all([
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN"),
        os.environ.get("TWILIO_FROM_NUMBER"),
        os.environ.get("TWILIO_TO_NUMBER"),
    ])


def send_sms(message: str, to_number: str = None) -> dict:
    """Send SMS via Twilio. Falls back to console log if not configured.

    Returns:
        dict with status, sid (if sent), channel, ts
    """
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    to_number = to_number or os.environ.get("TWILIO_TO_NUMBER", "")

    if not is_twilio_configured():
        print(f"[NOTIFY] Twilio not configured. SMS logged:")
        print(f"  To: {to_number}")
        print(f"  Message: {message}")
        return {
            "status": "logged",
            "channel": "sms",
            "sid": None,
            "ts": datetime.utcnow().isoformat(),
        }

    try:
        from twilio.rest import Client
        client = Client(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"],
        )
        sms = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        print(f"[NOTIFY] SMS sent. SID: {sms.sid}")
        return {
            "status": "sent",
            "channel": "sms",
            "sid": sms.sid,
            "ts": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[NOTIFY] SMS failed: {e}")
        return {
            "status": "failed",
            "channel": "sms",
            "error": str(e),
            "ts": datetime.utcnow().isoformat(),
        }


def notify_corridor_red(corridor_id: str, crs_score: float, actions: list[dict]) -> dict:
    """Send notification when a corridor goes red.

    This is the main entry point called from the recommendation engine.
    """
    action_summary = "; ".join(a.get("action_type", "unknown") for a in actions)
    message = (
        f"SANCHALAN Alert: {corridor_id.replace('_', ' ').upper()} corridor "
        f"CRS at {crs_score:.2f} (RED). "
        f"Recommended actions: {action_summary}. "
        f"Please review at dashboard."
    )
    result = send_sms(message)
    return {
        "corridor_id": corridor_id,
        "crs_score": crs_score,
        "notification": result,
    }
