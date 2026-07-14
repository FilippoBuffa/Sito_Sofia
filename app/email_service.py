import msal
import requests
from flask import render_template, current_app

_msal_app = None


def _get_graph_token():
    global _msal_app
    if _msal_app is None:
        _msal_app = msal.ConfidentialClientApplication(
            client_id=current_app.config["MS_CLIENT_ID"],
            client_credential=current_app.config["MS_CLIENT_SECRET"],
            authority=f"https://login.microsoftonline.com/{current_app.config['MS_TENANT_ID']}",
        )
    result = _msal_app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Graph auth failed: {result.get('error_description')}")
    return result["access_token"]


def _send(subject, recipients, template, **kwargs):
    kwargs.setdefault("base_url", _base_url())
    html_body = render_template(template, **kwargs)
    sender = current_app.config["MS_SENDER_EMAIL"]
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": r}} for r in recipients],
        },
        "saveToSentItems": "false",
    }
    try:
        token = _get_graph_token()
        resp = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        current_app.logger.error(f"[email] Failed to send to {recipients}: {e}")


def _base_url():
    return current_app.config.get("APP_BASE_URL", "http://localhost:8080")


# ── Account emails ──────────────────────────────────────────────

def send_verification_email(user):
    link = f"{_base_url()}/auth/verify/{user.verification_token}"
    _send(
        subject="Vernay TestLab — Verify your email address",
        recipients=[user.email],
        template="email/verify.html",
        user=user, link=link,
    )


def send_password_reset_email(user):
    link = f"{_base_url()}/auth/reset-password/{user.reset_token}"
    _send(
        subject="Vernay TestLab — Reset your password",
        recipients=[user.email],
        template="email/reset_password.html",
        user=user, link=link,
    )


def send_engineer_welcome(user, temp_password):
    _send(
        subject="Vernay TestLab — Your engineer account",
        recipients=[user.email],
        template="email/engineer_welcome.html",
        user=user,
        temp_password=temp_password,
        login_url=f"{_base_url()}/auth/login",
    )


# ── Status-change notifications ─────────────────────────────────

def send_new_request_notification(req):
    """Notify engineers when a new request is submitted."""
    engineers = req.service.engineers
    recipients = [e.email for e in engineers if e.email]
    if not recipients:
        return
    _send(
        subject=f"[TestLab] New request {req.tr_number}",
        recipients=recipients,
        template="email/new_request.html",
        req=req,
        link=f"{_base_url()}/engineer/request/{req.id}",
    )


def send_awaiting_parts(req):
    """Notify client that request was accepted — please ship parts."""
    if not req.requester.email:
        return
    _send(
        subject=f"[TestLab] {req.tr_number} accepted — please ship your parts",
        recipients=[req.requester.email],
        template="email/parts_awaiting.html",
        req=req,
        link=f"{_base_url()}/client/request/{req.id}",
    )


def send_parts_shipped_notification(req):
    """Notify engineers that client has shipped the parts."""
    engineers = req.service.engineers
    recipients = [e.email for e in engineers if e.email]
    if not recipients:
        return
    _send(
        subject=f"[TestLab] Parts shipped for {req.tr_number}",
        recipients=recipients,
        template="email/parts_shipped.html",
        req=req,
        link=f"{_base_url()}/engineer/request/{req.id}",
    )


def send_parts_received_notification(req):
    """Notify client that parts were received and testing has started."""
    if not req.requester.email:
        return
    _send(
        subject=f"[TestLab] Parts received — {req.tr_number} testing started",
        recipients=[req.requester.email],
        template="email/parts_received.html",
        req=req,
        link=f"{_base_url()}/client/request/{req.id}",
    )


def send_request_returned(req, note):
    if not req.requester.email:
        return
    _send(
        subject=f"[TestLab] {req.tr_number} returned for changes",
        recipients=[req.requester.email],
        template="email/request_returned.html",
        req=req, note=note, accent="#EB7704",
        link=f"{_base_url()}/client/request/{req.id}",
    )


def send_request_resubmitted(req):
    engineers = req.service.engineers
    recipients = [e.email for e in engineers if e.email]
    if not recipients:
        return
    _send(
        subject=f"[TestLab] {req.tr_number} resubmitted by client",
        recipients=recipients,
        template="email/request_resubmitted.html",
        req=req,
        link=f"{_base_url()}/engineer/request/{req.id}",
    )


def send_request_closed(req):
    if not req.requester.email:
        return
    _send(
        subject=f"[TestLab] {req.tr_number} completed — results available",
        recipients=[req.requester.email],
        template="email/request_closed.html",
        req=req,
        link=f"{_base_url()}/client/request/{req.id}",
    )
