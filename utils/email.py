# utils/email.py
import asyncio
import os
import pathlib
import boto3
from botocore.exceptions import ClientError

# NOTE: Emails are fire-and-forget via thread pool. If the server restarts
# mid-send, background emails in flight will be lost silently.

# ---------------------------------------------------------------------------
# Admin panel base URL — set ADMIN_PANEL_URL in your environment.
# ---------------------------------------------------------------------------
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "https://app.copods.co")

# ---------------------------------------------------------------------------
# Logo — read from public/assets/logo.svg and inlined into HTML emails.
# Inlining is required because email clients block external image URLs.
# ---------------------------------------------------------------------------
_LOGO_PATH = pathlib.Path(__file__).resolve().parent.parent / "public" / "assets" / "logo.svg"
try:
    _LOGO_SVG = _LOGO_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    _LOGO_SVG = ""  # Emails still send cleanly without the logo


def get_ses_client():
    """Helper to initialize the boto3 SES client using environment variables."""
    return boto3.client(
        'ses',
        region_name=os.getenv("AWS_REGION", "ap-south-1").strip(),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )


# ---------------------------------------------------------------------------
# Shared HTML shell — all emails share this card template
# ---------------------------------------------------------------------------

def _html_shell(
    *,
    title: str,
    headline: str,
    body_html: str,
    button_label: str | None = None,
    button_url: str | None = None,
) -> str:
    """
    Returns a complete HTML email document.
    The logo SVG is inlined; everything is table-based for email client
    compatibility (Gmail, Outlook, Apple Mail).
    """
    button_block = ""
    if button_label and button_url:
        button_block = f"""
        <tr>
          <td align="center" style="padding:8px 0 32px;">
            <a href="{button_url}"
               target="_blank"
               style="display:inline-block;
                      background:linear-gradient(135deg,#353986 0%,#5b5fcb 100%);
                      color:#ffffff;
                      font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
                      font-size:15px;
                      font-weight:600;
                      letter-spacing:0.3px;
                      text-decoration:none;
                      padding:14px 36px;
                      border-radius:10px;
                      box-shadow:0 4px 18px rgba(53,57,134,0.35);">
              {button_label}
            </a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f1ff;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#f0f1ff;padding:40px 16px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:580px;background:#ffffff;border-radius:20px;
                      overflow:hidden;box-shadow:0 8px 40px rgba(53,57,134,0.12);">

          <!-- Header gradient band -->
          <tr>
            <td align="center"
                style="background:linear-gradient(135deg,#353986 0%,#5b5fcb 100%);
                       padding:36px 40px 28px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center"
                      style="background:#ffffff;border-radius:14px;
                             padding:10px 14px;
                             box-shadow:0 2px 12px rgba(0,0,0,0.15);">
                    {_LOGO_SVG}
                  </td>
                </tr>
              </table>
              <p style="margin:14px 0 0;font-size:13px;font-weight:700;
                        letter-spacing:2px;text-transform:uppercase;
                        color:rgba(255,255,255,0.75);">
                CopodsConnect
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 44px 12px;">
              <h1 style="margin:0 0 20px;font-size:22px;font-weight:700;
                         color:#1a1d4e;line-height:1.3;">
                {headline}
              </h1>
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                {body_html}
                {button_block}
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 44px;">
              <hr style="border:none;border-top:1px solid #e8e9ff;margin:0;"/>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center"
                style="padding:24px 44px 32px;font-size:12px;
                       color:#9a9bc4;line-height:1.6;">
              <p style="margin:0;">
                This email was sent by <strong style="color:#353986;">CopodsConnect</strong>.
                If you have questions, reach out to your administrator.
              </p>
              <p style="margin:8px 0 0;">&#169; 2025 CopodsConnect &middot; All rights reserved</p>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""


def _p(text: str) -> str:
    """Wraps text in an email-safe table row paragraph."""
    return f"""
    <tr>
      <td style="font-size:15px;color:#444560;line-height:1.7;padding-bottom:14px;">
        {text}
      </td>
    </tr>"""


def _spacer(px: int = 8) -> str:
    return f'<tr><td style="height:{px}px;line-height:{px}px;">&nbsp;</td></tr>'


# ---------------------------------------------------------------------------
# Core SES sender — plain text + optional HTML
# ---------------------------------------------------------------------------

def _send_email_via_ses(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> bool:
    """Core function to send emails using Amazon SES."""
    sender = os.getenv("MAIL_FROM", os.getenv("MAIL_fROM", "dev@copods.co")).strip()
    client = get_ses_client()

    message_body: dict = {
        'Text': {'Charset': "UTF-8", 'Data': body_text},
    }
    if body_html:
        message_body['Html'] = {'Charset': "UTF-8", 'Data': body_html}

    try:
        client.send_email(
            Destination={'ToAddresses': [to_email]},
            Message={
                'Body': message_body,
                'Subject': {'Charset': "UTF-8", 'Data': subject},
            },
            Source=sender,
        )
        return True
    except ClientError as e:
        print(f"Failed to send email via SES: {e.response['Error']['Message']}")
        return False


# ---------------------------------------------------------------------------
# 1. Member invitation — no button (link to be wired up later)
# ---------------------------------------------------------------------------

async def send_invitation_email(to_email: str) -> bool:
    """Sends app invitation email to a new user (MEMBER)."""
    subject = "You're invited to join CopodsConnect"

    body_text = """\
Hi there,

You have been invited to join CopodsConnect — your team's recognition and culture platform.

Sign in with your Google account to get started and become part of your team's community.

Your login link will be shared with you shortly. Stay tuned!

Welcome aboard,
The CopodsConnect Team
"""

    body_html = _html_shell(
        title="You're invited to join CopodsConnect",
        headline="Welcome to CopodsConnect! 🎉",
        body_html=(
            _p("Hi there,")
            + _p(
                "You've been invited to join <strong>CopodsConnect</strong> &mdash; your "
                "team's recognition and culture platform where great work gets celebrated."
            )
            + _p(
                "Sign in with your Google account to get started and become part of your "
                "team's community."
            )
            + _spacer(4)
            + _p("<em>Your login link will be shared with you shortly. Stay tuned!</em>")
            + _spacer(16)
            + _p("Welcome aboard,<br/><strong>The CopodsConnect Team</strong>")
        ),
        # No button yet — login link will be wired up later
    )

    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body_text, body_html)


# ---------------------------------------------------------------------------
# 2. Admin invitation — button → admin panel login / landing page
# ---------------------------------------------------------------------------

async def send_admin_invitation_email(to_email: str) -> bool:
    """Sends admin panel invitation email to a new admin (ADMIN role)."""
    subject = "You've been added as an Admin on CopodsConnect"
    login_url = f"{ADMIN_PANEL_URL}/"

    body_text = f"""\
Hi there,

You have been granted admin access to the CopodsConnect Admin Panel.

As an admin, you can manage users, send invitations, review flagged content,
and oversee platform activity.

Click the link below to sign in with your Google account and access the admin panel:
{login_url}

Regards,
The CopodsConnect Team
"""

    body_html = _html_shell(
        title="You've been added as an Admin on CopodsConnect",
        headline="You're now an Admin on CopodsConnect 🛡️",
        body_html=(
            _p("Hi there,")
            + _p(
                "You have been granted <strong>admin access</strong> to the "
                "CopodsConnect Admin Panel."
            )
            + _p("As an admin, you'll be able to:")
            + """
            <tr>
              <td style="font-size:15px;color:#444560;line-height:1.9;
                         padding-bottom:16px;padding-left:16px;">
                &#9989;&nbsp; Manage and invite users<br/>
                &#9989;&nbsp; Review and moderate flagged content<br/>
                &#9989;&nbsp; Monitor platform activity and analytics
              </td>
            </tr>"""
            + _p(
                "Click the button below to sign in with your Google account and get started."
            )
            + _spacer(8)
        ),
        button_label="Open Admin Panel",
        button_url=login_url,
    )

    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body_text, body_html)


# ---------------------------------------------------------------------------
# 3. Promotion to Admin — button → /dashboard/stats
# ---------------------------------------------------------------------------

async def send_promotion_email(to_email: str) -> bool:
    """Sends email when a user is promoted to Admin."""
    subject = "You've been promoted to Admin on CopodsConnect"
    dashboard_url = f"{ADMIN_PANEL_URL}/dashboard/stats"

    body_text = f"""\
Hi there,

Great news! You have been promoted to Admin on CopodsConnect.

As an admin, you can manage users, send invitations, and oversee platform
activity on the admin panel.

Head over to your dashboard:
{dashboard_url}

Regards,
The CopodsConnect Team
"""

    body_html = _html_shell(
        title="You've been promoted to Admin on CopodsConnect",
        headline="Congratulations — you're now an Admin! 🚀",
        body_html=(
            _p("Hi there,")
            + _p(
                "Great news! You have been <strong>promoted to Admin</strong> on "
                "CopodsConnect."
            )
            + _p("Your new role gives you access to the full Admin Panel, including:")
            + """
            <tr>
              <td style="font-size:15px;color:#444560;line-height:1.9;
                         padding-bottom:16px;padding-left:16px;">
                &#127919;&nbsp; Platform analytics &amp; statistics<br/>
                &#128101;&nbsp; User management &amp; invitations<br/>
                &#128737;&#65039;&nbsp; Content moderation &amp; review<br/>
                &#128202;&nbsp; Activity monitoring
              </td>
            </tr>"""
            + _p(
                "Click the button below to head to your dashboard. If you haven't "
                "logged in yet, you'll be redirected to the login page first."
            )
            + _spacer(8)
        ),
        button_label="Go to Dashboard",
        button_url=dashboard_url,
    )

    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body_text, body_html)


# ---------------------------------------------------------------------------
# 4. Demotion from Admin — no button (informational only)
# ---------------------------------------------------------------------------

async def send_demotion_email(to_email: str) -> bool:
    """Sends email when a user's admin access is removed (Member role)."""
    subject = "Your admin access on CopodsConnect has been updated"

    body_text = """\
Hi there,

Your role on CopodsConnect has been updated. You are now a Member and no longer
have admin access to the admin panel.

You can continue to enjoy CopodsConnect through the mobile app using your Google account.
Your profile, recognitions, and activity remain intact.

If you think this was done in error, please reach out to your team's super admin.

Regards,
The CopodsConnect Team
"""

    body_html = _html_shell(
        title="Your CopodsConnect role has been updated",
        headline="Your role has been updated",
        body_html=(
            _p("Hi there,")
            + _p(
                "Your role on CopodsConnect has been updated. You are now a "
                "<strong>Member</strong> and no longer have access to the Admin Panel."
            )
            + _p(
                "You can continue to enjoy CopodsConnect through the mobile app with "
                "your Google account &mdash; your profile, recognitions, and activity "
                "remain intact."
            )
            + _p(
                "If you believe this was done in error, please reach out to your "
                "team's super admin."
            )
            + _spacer(16)
            + _p("Regards,<br/><strong>The CopodsConnect Team</strong>")
        ),
        # No button — demotion is informational only
    )

    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body_text, body_html)


# ---------------------------------------------------------------------------
# 5. NSFW / Blacklist alert — button → specific alert review page
# ---------------------------------------------------------------------------

async def send_nsfw_alert_email(
    to_email: str,
    flagged_user_name: str,
    flagged_user_email: str,
    post_id: str,
    alert_id: str | None = None,
) -> bool:
    """
    Sends alert email to an admin when a post is flagged for NSFW / blacklist content.

    alert_id: when provided, the button deep-links to /dashboard/review/{alert_id};
              otherwise falls back to the general /dashboard/review list.
    """
    subject = "[CopodsConnect] Content Flagged for Review"

    review_url = (
        f"{ADMIN_PANEL_URL}/dashboard/review/{alert_id}"
        if alert_id
        else f"{ADMIN_PANEL_URL}/dashboard/review"
    )

    body_text = f"""\
Hi Admin,

A post on CopodsConnect has been flagged for review by the moderation system.

User:    {flagged_user_name} ({flagged_user_email})
Post ID: {post_id}

Please review the flagged content and take the appropriate action.

Review the alert here:
{review_url}

Regards,
CopodsConnect Moderation System
"""

    body_html = _html_shell(
        title="[CopodsConnect] Content Flagged for Review",
        headline="⚠️ Content Flagged for Review",
        body_html=(
            _p("Hi Admin,")
            + _p(
                "The CopodsConnect moderation system has flagged a post that requires "
                "your attention."
            )
            + f"""
            <tr>
              <td style="padding-bottom:20px;">
                <table width="100%" cellpadding="12" cellspacing="0" border="0"
                       style="background:#f5f5ff;border-left:4px solid #353986;
                              border-radius:8px;">
                  <tr>
                    <td style="font-size:14px;color:#1a1d4e;line-height:1.9;">
                      <strong>Flagged User:</strong>&nbsp; {flagged_user_name}<br/>
                      <strong>Email:</strong>&nbsp; {flagged_user_email}<br/>
                      <strong>Post ID:</strong>&nbsp;
                      <code style="font-size:12px;background:#e8e9ff;
                                   padding:2px 6px;border-radius:4px;">{post_id}</code>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""
            + _p(
                "Please review the flagged content and decide whether to "
                "<strong>restore</strong>, <strong>remove</strong>, "
                "<strong>blacklist</strong>, or take any other appropriate action."
            )
            + _spacer(8)
        ),
        button_label="Review Alert Now",
        button_url=review_url,
    )

    return await asyncio.to_thread(_send_email_via_ses, to_email, subject, body_text, body_html)
