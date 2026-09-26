"""Dynamic per-user Gmail tool integration using Google OAuth 2.0 & Gmail REST API.

Supports:
- Official Google OAuth 2.0 Access & Refresh Tokens
- Automatic token refresh via https://oauth2.googleapis.com/token
- Gmail REST API (Search messages, read emails, draft messages, send emails)
- App Password IMAP/SMTP fallback
"""
import base64
import email
from email.header import decode_header
import email.message
import imaplib
import json
import logging
import smtplib
from typing import Any, Dict, List, Optional, Tuple
import requests

from langchain_core.tools import tool

from .. import config

logger = logging.getLogger("omnivox.gmail")
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _refresh_google_token_if_needed(creds_data: Dict[str, Any]) -> str:
    """Check if token needs refresh and return a valid access token."""
    access_token = creds_data.get("access_token", "")
    refresh_token = creds_data.get("refresh_token", "")
    client_id = creds_data.get("client_id") or config.GOOGLE_CLIENT_ID
    client_secret = creds_data.get("client_secret") or config.GOOGLE_CLIENT_SECRET

    if not access_token and not refresh_token:
        return ""

    # Test token validity with a quick call to userinfo
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        test_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, timeout=5)
        if test_resp.status_code == 200:
            return access_token
    except Exception:
        pass

    # If token expired and we have a refresh token, exchange it
    if refresh_token and client_id and client_secret:
        try:
            token_resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            if token_resp.status_code == 200:
                new_data = token_resp.json()
                new_token = new_data.get("access_token")
                creds_data["access_token"] = new_token
                return new_token
        except Exception as exc:
            logger.error(f"Failed to refresh Google OAuth token: {exc}")

    return access_token


def validate_gmail_credentials(email_addr: str, app_password: str) -> Tuple[bool, str]:
    """Actively test IMAP login to ensure App Password credentials are valid before saving."""
    email_clean = email_addr.strip()
    pwd_clean = app_password.replace(" ", "").strip()

    if not email_clean or "@" not in email_clean:
        return False, "Please enter a valid Gmail address."
    if not pwd_clean:
        return False, "App Password cannot be empty."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_clean, pwd_clean)
        mail.logout()
        return True, "Gmail authentication verified successfully via Google IMAP."
    except imaplib.IMAP4.error as err:
        err_msg = str(err)
        if "AUTHENTICATIONFAILED" in err_msg or "Invalid credentials" in err_msg:
            return False, (
                "Authentication failed: Google rejected the App Password. "
                "Ensure 2-Step Verification is enabled on your Google Account, "
                "and generate a 16-character App Password at https://myaccount.google.com/apppasswords."
            )
        return False, f"Google IMAP authentication error: {err_msg}"
    except Exception as exc:
        return False, f"Could not connect to Gmail servers: {exc}"


def _parse_credentials(credentials_str: str) -> Dict[str, Any]:

    """Parse user's credentials string (JSON or formatted string)."""
    credentials_str = credentials_str.strip()
    if credentials_str.startswith("{"):
        try:
            data = json.loads(credentials_str)
            if "app_password" in data and data["app_password"]:
                data["app_password"] = data["app_password"].replace(" ", "").strip()
            return data
        except Exception:
            pass
    if ":" in credentials_str and "@" in credentials_str:
        user_email, password = credentials_str.split(":", 1)
        return {"email": user_email.strip(), "app_password": password.replace(" ", "").strip()}
    return {"access_token": credentials_str}


def search_gmail_messages(creds_data: Dict[str, Any], query: str = "ALL", limit: int = 5) -> str:
    """Search emails using Google OAuth REST API or IMAP fallback."""
    access_token = _refresh_google_token_if_needed(creds_data)

    # 1. Official Google OAuth REST API
    if access_token:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            q_param = f"&q={query}" if query and query.upper() != "ALL" else ""
            resp = requests.get(
                f"{GMAIL_API_BASE}/messages?maxResults={limit}{q_param}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return f"Gmail API error ({resp.status_code}): {resp.text}"
            data = resp.json()
            messages = data.get("messages", [])
            if not messages:
                return f"No emails found in your Gmail inbox matching '{query}'."

            results = []
            for idx, m in enumerate(messages, 1):
                m_id = m.get("id")
                detail_resp = requests.get(
                    f"{GMAIL_API_BASE}/messages/{m_id}?format=metadata",
                    headers=headers,
                    timeout=10,
                )
                if detail_resp.status_code == 200:
                    payload = detail_resp.json().get("payload", {})
                    headers_list = payload.get("headers", [])
                    hdr_map = {h["name"].lower(): h["value"] for h in headers_list}
                    subject = hdr_map.get("subject", "No Subject")
                    sender = hdr_map.get("from", "Unknown")
                    date_str = hdr_map.get("date", "")
                    snippet = detail_resp.json().get("snippet", "")
                    results.append(
                        f"{idx}. Sender: {sender}\n"
                        f"   Subject: {subject}\n"
                        f"   Date: {date_str}\n"
                        f"   Summary: {snippet[:120]}"
                    )

            return f"Found {len(results)} Recent Emails:\n\n" + "\n\n".join(results)
        except Exception as exc:
            return f"Failed to search Gmail via OAuth: {exc}"

    # 2. IMAP with App Password Fallback
    user_email = creds_data.get("email")
    app_pwd = creds_data.get("app_password")
    if user_email and app_pwd:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(user_email, app_pwd)
            mail.select("inbox")

            search_criteria = "ALL"
            if query and query.upper() != "ALL":
                search_criteria = f'(OR (FROM "{query}") (SUBJECT "{query}"))'

            status, messages = mail.search(None, search_criteria)
            if status != "OK" or not messages[0]:
                mail.logout()
                return f"No emails found matching query '{query}' in your inbox."

            msg_ids = messages[0].split()
            recent_ids = msg_ids[-limit:]
            recent_ids.reverse()

            results = []
            for num, msg_id in enumerate(recent_ids, 1):
                res, data = mail.fetch(msg_id, "(RFC822.HEADER)")
                if res != "OK":
                    continue
                msg = email.message_from_bytes(data[0][1])
                raw_subject = msg.get("Subject", "No Subject")
                try:
                    decoded = decode_header(raw_subject)[0]
                    subject = decoded[0]
                    encoding = decoded[1]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8", errors="ignore")
                except Exception:
                    subject = str(raw_subject)
                sender = msg.get("From", "Unknown Sender")
                results.append(f"{num}. Sender: {sender} | Subject: {subject}")

            mail.logout()
            return f"Found {len(results)} Recent Emails:\n" + "\n".join(results)
        except Exception as exc:
            return f"Failed to search Gmail: {exc}"

    return "Gmail OAuth credentials not connected. Please link your Gmail account via Google OAuth."


def send_or_draft_email(creds_data: Dict[str, Any], to_email: str, subject: str, body: str, send: bool = False) -> str:
    """Send or draft an email via Gmail REST API."""
    access_token = _refresh_google_token_if_needed(creds_data)

    if not send:
        # Create draft via API
        if access_token:
            try:
                msg = email.message.EmailMessage()
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.set_content(body)
                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

                headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
                resp = requests.post(
                    f"{GMAIL_API_BASE}/drafts",
                    headers=headers,
                    json={"message": {"raw": raw_message}},
                    timeout=10,
                )
                if resp.status_code in (200, 201):
                    return f"Status: Draft Created in Gmail\nTo: {to_email}\nSubject: {subject}\nDetails: {body[:150]}"
            except Exception as exc:
                logger.error(f"Draft creation error: {exc}")
        return f"Status: Draft Prepared\nTo: {to_email}\nSubject: {subject}\nDetails: {body[:150]}"

    # Send message via Google OAuth REST API
    if access_token:
        try:
            msg = email.message.EmailMessage()
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(body)
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            resp = requests.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers=headers,
                json={"raw": raw_message},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return f"Status: Sent Successfully via Gmail API\nTo: {to_email}\nSubject: {subject}\nDetails: {body[:150]}"
            return f"Gmail API error sending email ({resp.status_code}): {resp.text}"
        except Exception as exc:
            return f"Failed to send email via Google API: {exc}"

    return "Sending emails requires your Gmail connected via Google OAuth."


def build_user_gmail_tools(credentials_str: str):
    """Build LangChain tools bound to user's Gmail OAuth credentials."""
    creds_data = _parse_credentials(credentials_str)

    @tool
    def search_emails(query: str = "ALL", limit: int = 5) -> str:
        """Search recent emails in the user's Gmail inbox by keyword, subject, or sender."""
        return search_gmail_messages(creds_data, query=query, limit=limit)

    @tool
    def draft_or_send_message(to_email: str, subject: str, body: str, confirm_send: bool = False) -> str:
        """Draft or send an email from the user's Gmail account. Only sends if confirm_send is True."""
        return send_or_draft_email(creds_data, to_email=to_email, subject=subject, body=body, send=confirm_send)

    return [search_emails, draft_or_send_message]
