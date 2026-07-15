import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


def _send_email_sync(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
        server.sendmail(settings.EMAIL_USER, to_email, msg.as_string())


async def send_password_reset_email(to_email: str, token: str) -> None:
    subject = "Password Reset Request"
    reset_link = f"http://localhost:8000/api/v1/auth/reset-password?token={token}"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Password Reset</h2>
        <p>You requested a password reset. Copy and paste this token:</p>
        <p><code>{token}</code></p>
        <p>This link expires in {settings.RESET_TOKEN_EXPIRE_HOURS} hour(s).</p>
        <p>If you did not request this, please ignore this email.</p>
      </body>
    </html>
    """

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, _send_email_sync, to_email, subject, html_body
    )
