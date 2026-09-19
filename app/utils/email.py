import resend
import logging
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY
logger = logging.getLogger(__name__)

def send_reset_link(to_email: str, token: str):
    reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    
    html_content = f"""
    <div>
        <h2>Password Reset Request</h2>
        <p>Aapne apna password reset karne ki request ki hai. Niche click karein:</p>
        <a href="{reset_link}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Reset Password
        </a>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": to_email,
            "subject": "Reset Your Password",
            "html": html_content
        })
        logger.info("Password reset email sent")
    except Exception:
        logger.exception("Password reset email delivery failed")
