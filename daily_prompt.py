"""Daily reflection prompt generator + emailer.

Runs once a day (via GitHub Actions cron). Pulls one probing question
from your cognitive graph and emails it to you.

Reads all config from environment variables (see .env.example):
    GROQ_API_KEY, NEO4J_*, EMAIL_USER, EMAIL_APP_PASSWORD, EMAIL_TO
"""
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv

from mind_mirror import MindMirrorEngine
from prompt_library import FOLLOWUP_PROMPT

load_dotenv()


def build_daily_question(mirror: MindMirrorEngine) -> str:
    """Pick the most fertile probe based on graph state."""
    new_nodes, _ = mirror.db.get_recent_changes(days=14)
    recurring = mirror.db.get_recurring_nodes(min_times_seen=2, limit=5)

    if not new_nodes and not recurring:
        return (
            "You haven't logged anything in two weeks. "
            "What's the truest thing you can say about how you've been lately?"
        )

    payload = json.dumps({
        "raw_thought": "(daily auto-prompt — no new input today)",
        "extracted_nodes": new_nodes[:10],
        "recurring_load_bearers": recurring,
        "context": "Generate a probing question for the user's daily reflection. "
                   "Reference one specific node by label. Make them re-examine a load-bearer "
                   "or a stale intent. One line. No quotes.",
        "contradictions": [],
    })
    return mirror._chat(FOLLOWUP_PROMPT, payload, temperature=0.6).strip().strip('"')


def send_email(question: str, to_addr: str, from_addr: str, app_password: str):
    today = datetime.now().strftime("%A, %b %d")
    body = f"""Mind Mirror — Daily Reflection · {today}

{question}

— reply by visiting your Mind Mirror app and committing a thought.
"""
    msg = MIMEText(body)
    msg["Subject"] = f"🧠 {today}: {question[:60]}{'...' if len(question) > 60 else ''}"
    msg["From"] = from_addr
    msg["To"] = to_addr

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(from_addr, app_password)
        smtp.send_message(msg)


def main():
    to_addr = os.getenv("EMAIL_TO")
    from_addr = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    if not all([to_addr, from_addr, app_password]):
        print("❌ EMAIL_USER / EMAIL_APP_PASSWORD / EMAIL_TO must be set")
        sys.exit(1)

    mirror = MindMirrorEngine()
    question = build_daily_question(mirror)
    print(f"📩 Daily question: {question}")

    send_email(question, to_addr, from_addr, app_password)
    print(f"✅ Sent to {to_addr}")


if __name__ == "__main__":
    main()
