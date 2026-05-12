# utils/email.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_invitation_email(to_email: str) -> bool:
    """Sends app invitation email to a new user (MEMBER)."""
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


def send_admin_invitation_email(to_email: str) -> bool:
    """Sends admin panel invitation email to a new admin (ADMIN role)."""
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