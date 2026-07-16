# utils/email.py
import asyncio
import os
import boto3
from botocore.exceptions import ClientError

# NOTE: Emails are fire-and-forget via thread pool. If the server restarts
# mid-send, background emails in flight will be lost silently.

def get_ses_client():
    """Helper to initialize the boto3 SES client using environment variables."""
    return boto3.client(
        'ses',
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

def _send_email_via_ses(to_email: str, subject: str, body_text: str) -> bool:
    """Core function to send emails using Amazon SES."""
    sender = os.getenv("MAIL_FROM", "dev@copods.co")
    client = get_ses_client()

    try:
        response = client.send_email(
            Destination={'ToAddresses': [to_email]},
            Message={
                'Body': {
                    'Text': {'Charset': "UTF-8", 'Data': body_text},
                },
                'Subject': {'Charset': "UTF-8", 'Data': subject},
            },
            Source=sender,
        )
        return True
    except ClientError as e:
        print(f"Failed to send email via SES: {e.response['Error']['Message']}")
        return False


async def send_invitation_email(to_email: str) -> bool:
    """Sends app invitation email to a new user (MEMBER)."""
    subject = "You are invited to join CopodsConnect"
    body = """
Hi there,

You have been invited to join CopodsConnect - your team's recognition and cultural platform.

Click the link below to sign in with your Google account and get started.

[Login link will be added here]

Welcome aboard,
The CopodsConnect Team
"""
    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body)


async def send_admin_invitation_email(to_email: str) -> bool:
    """Sends admin panel invitation email to a new admin (ADMIN role)."""
    subject = "You have been added as an Admin on CopodsConnect"
    body = """
Hi there,

You have been granted admin access to the CopodsConnect Admin Panel.

As an admin, you will be able to manage users, send invitations, and oversee platform activity.

Click the link below to sign in with your Google account and access the admin panel.

[Admin panel login link will be added here]

Regards,
The CopodsConnect Team
"""
    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body)


async def send_promotion_email(to_email: str) -> bool:
    """Sends email when a user is promoted to Admin."""
    subject = "You have been promoted to Admin on CopodsConnect"
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
    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body)


async def send_demotion_email(to_email: str) -> bool:
    """Sends email when a user's admin access is removed (Member)."""
    subject = "Your admin access on CopodsConnect has been updated"
    body = """
Hi there,

Your role on CopodsConnect has been updated. You are now a Member
and no longer have admin access to the admin panel.

You can continue to use the CopodsConnect app with your Google account.

[App login link will be added here]

Regards,
The CopodsConnect Team
"""
    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body)


async def send_nsfw_alert_email(to_email: str, flagged_user_name: str, flagged_user_email: str, post_id: str) -> bool:
    """Sends alert email to an admin when a post is flagged for NSFW content."""
    subject = "[CopodsConnect] NSFW Content Flagged for Review"
    body = f"""
Hi Admin,

A post on CopodsConnect has been flagged for NSFW content by the moderation system.

User: {flagged_user_name} ({flagged_user_email})
Post ID: {post_id}
Action taken: Flagged — requires your review

Please log in to the admin panel to review this post and take action.

Regards,
CopodsConnect Moderation System
"""
    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body)

