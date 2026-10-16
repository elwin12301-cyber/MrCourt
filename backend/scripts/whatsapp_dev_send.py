"""Send a message to the local app as if it came from WhatsApp, and show what the app answers (development only).

The webhook accepts development messages only when they carry a signature made with the server's secret, so this
script signs the request the same way. The person must have linked their number in Settings first (or the app
will answer with the "not linked" reply, which is also worth seeing).

    python scripts/whatsapp_dev_send.py --from 9000000005 --text "What is Section 138 of the NI Act?"
    python scripts/whatsapp_dev_send.py --from 9000000005 --text "next hearing"
    python scripts/whatsapp_dev_send.py --from 9000000005 --text STOP

The replies are read from the development messages list, so the server must run with WHATSAPP_PROVIDER=none.
Voice notes cannot be tried this way (there is no real audio); use the Twilio sandbox for that.
"""

import argparse
import json
import sys
import time
import uuid

import httpx

from mrcourt.config import get_settings
from mrcourt.services.whatsapp.development import SIGNATURE_HEADER, sign

COUNTRY_CODE = get_settings().sms_country_code


def number_of(value: str) -> str:
    digits = "".join(c for c in value if c.isdigit())
    return f"{COUNTRY_CODE}{digits}" if len(digits) == 10 else digits


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # replies contain characters a Windows console would refuse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="sender", required=True, help="the sender's mobile number")
    parser.add_argument("--text", default="", help="the message text")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait", type=float, default=15.0, help="seconds to wait for the reply")
    args = parser.parse_args()

    sender = number_of(args.sender)
    body = json.dumps(
        {
            "id": f"dev-{uuid.uuid4().hex[:12]}",
            "from": sender,
            "kind": "text",
            "text": args.text,
            "media": None,
        }
    ).encode()
    base = args.base_url.rstrip("/")
    earlier = {(m["at"], m["text"]) for m in httpx.get(f"{base}/api/v1/dev/messages", timeout=10).json()}
    started = time.time()
    response = httpx.post(
        f"{base}/api/v1/whatsapp/webhook",
        content=body,
        headers={SIGNATURE_HEADER: sign(body), "Content-Type": "application/json"},
        timeout=30,
    )
    print(f"Webhook answered {response.status_code}")
    if response.status_code != 200:
        return 1
    while time.time() - started < args.wait:
        messages = httpx.get(f"{base}/api/v1/dev/messages", timeout=10).json()
        mine = [m for m in messages if m["to"] == sender and m["channel"] == "whatsapp" and (m["at"], m["text"]) not in earlier]
        if mine:
            print(f"\nReply to +{sender}:\n")
            print(mine[0]["text"])
            return 0
        time.sleep(0.5)
    print("No reply within the wait (a STOP from a person who is not linked, or a stranger's repeat, gets none).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
