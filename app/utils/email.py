import resend
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY

def send_reset_link(to_email: str, token: str):
    reset_link = f"http://localhost:3000/reset-password?token={token}"
    
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
        response = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": to_email,
            "subject": "Reset Your Password",
            "html": html_content
        })
        print(f"✅ EMAIL SENT SUCCESSFULLY TO {to_email}")
        
    except Exception as e:
        print("=========================================")
        print(f"❌ EMAIL SENDING FAILED: {e}")
        print("=========================================")