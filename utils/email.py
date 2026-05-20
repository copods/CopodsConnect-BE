# utils/email.py
import asyncio
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# NOTE: Emails are fire-and-forget via thread pool. If the server restarts
# mid-send, background emails in flight will be lost silently.
# Use resend_invite to retry. A persistent queue (e.g. ARQ + Redis) should
# replace this when reliability becomes a requirement.


async def send_invitation_email(to_email: str) -> bool:
    """Sends app invitation email to a new user (MEMBER)."""
    return await asyncio.to_thread(_send_invitation_email_sync, to_email)


def _send_invitation_email_sync(to_email: str) -> bool:
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = "You are invited to join CopodsConnect"

        body = """
Hi there,

You have been invited to join CopodsConnect - your team's recognition and cultural platform.

Click the link below to sign in with your Google account and get started.

[Login link will be added here]

Welcome aboard,
The CopodsConnect Team
"""
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        return True
    except Exception:
        return False


async def send_admin_invitation_email(to_email: str) -> bool:
    """Sends admin panel invitation email to a new admin (ADMIN role)."""
    return await asyncio.to_thread(_send_admin_invitation_email_sync, to_email)


def _send_admin_invitation_email_sync(to_email: str) -> bool:
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = "You have been added as an Admin on CopodsConnect"

        body = """
Hi there,

You have been granted admin access to the CopodsConnect Admin Panel.

As an admin, you will be able to manage users, send invitations, and oversee platform activity.

Click the link below to sign in with your Google account and access the admin panel.

[Admin panel login link will be added here]

Regards,
The CopodsConnect Team
"""
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        return True
    except Exception:
        return False


async def send_promotion_email(to_email: str) -> bool:
    """Sends email when a user is promoted to Admin."""
    return await asyncio.to_thread(_send_promotion_email_sync, to_email)


def _send_promotion_email_sync(to_email: str) -> bool:
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = "You have been promoted to Admin on CopodsConnect"

        body = """
Hi there,

Great news! You have been promoted to Admin on CopodsConnect.

As an admin, you will be able to manage users, send invitations,
and oversee platform activity on the admin panel.

You can now sign in to the CopodsConnect Admin Panel with your
Google account.

[Admin panel login link will be added here]

Regards,
The CopodsConnect Team
"""
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        return True
    except Exception:
        return False


async def send_demotion_email(to_email: str) -> bool:
    """Sends email when a user's admin access is removed (Member)."""
    return await asyncio.to_thread(_send_demotion_email_sync, to_email)


def _send_demotion_email_sync(to_email: str) -> bool:
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = "Your admin access on CopodsConnect has been updated"

        body = """
Hi there,

Your role on CopodsConnect has been updated. You are now a Member
and no longer have admin access to the admin panel.

You can continue to use the CopodsConnect app with your Google account.

[App login link will be added here]

Regards,
The CopodsConnect Team
"""
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        return True
    except Exception:
        return False
