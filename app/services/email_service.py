# app/services/email_service.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
from datetime import datetime, timedelta
import secrets
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER") 
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) 
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USERNAME)
SENDER_NAME = os.getenv("SENDER_NAME", "Othor AI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an email using organization's SMTP server
    """
    try:
        if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD]):
            logger.error("SMTP credentials not configured")
            return False

        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        message["To"] = to_email

        # Add HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        # Connect to SMTP server
        # Note: Some servers might use SSL instead of TLS
        try:
            # Try TLS connection first
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        except:
            # If TLS fails, try SSL
            with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def generate_verification_token() -> str:
    """Generate a secure verification token"""
    return secrets.token_urlsafe(32)

def send_verification_email(email: str, token: str, frontend_url: Optional[str] = None) -> bool:
    """Send verification email with Othor AI branding"""
    print(f"--------{frontend_url}-------------")
    verification_link = f"{FRONTEND_URL}/verification?token={token}"
    
    template = Template("""
    <!DOCTYPE html>
    <html>
        <head>
            <style>
                body { font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #1a1a1a; padding: 20px; text-align: center; }
                .logo { width: 150px; height: auto; }
                .content { padding: 30px 20px; background-color: #ffffff; }
                .button {
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #007bff;
                    color: white !important;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                    font-weight: bold;
                }
                .footer {
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    font-size: 12px;
                    color: #666;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="{{ logo_url }}" alt="Othor AI" class="logo">
                </div>
                <div class="content">
                    <h2>Verify your email address</h2>
                    <p>Thank you for signing up for Othor AI! Please click the button below to verify your email address:</p>
                    <a href="{{ verification_link }}" class="button">Verify Email</a>
                    <p>Or copy and paste this link into your browser:</p>
                    <p>{{ verification_link }}</p>
                    <p>This link will expire in 24 hours.</p>
                </div>
                <div class="footer">
                    <p>If you didn't request this verification, please ignore this email.</p>
                    <p>© {{ year }} Othor AI. All rights reserved.</p>
                </div>
            </div>
        </body>
    </html>
    """)
    
    html_content = template.render(
        verification_link=verification_link,
        logo_url=f"{FRONTEND_URL}/images/othor-logo.png",
        year=datetime.utcnow().year
    )
    
    return send_email(
        to_email=email,
        subject="Verify your Othor AI account",
        html_content=html_content
    )

def send_welcome_email(email: str) -> bool:
    """Send welcome email with Othor AI branding"""
    template = Template("""
    <!DOCTYPE html>
    <html>
        <head>
            <style>
                body { font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #1a1a1a; padding: 20px; text-align: center; }
                .logo { width: 150px; height: auto; }
                .content { padding: 30px 20px; background-color: #ffffff; }
                .button {
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #007bff;
                    color: white !important;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                    font-weight: bold;
                }
                .footer {
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    font-size: 12px;
                    color: #666;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="{{ logo_url }}" alt="Othor AI" class="logo">
                </div>
                <div class="content">
                    <h2>Welcome to Othor AI!</h2>
                    <p>Thank you for verifying your email address. Your account is now fully activated.</p>
                    <p>You can now log in to your account and start exploring our platform:</p>
                    <a href="{{ login_link }}" class="button">Log In to Othor AI</a>
                    <p>If you have any questions or need assistance, our support team is here to help.</p>
                </div>
                <div class="footer">
                    <p>© {{ year }} Othor AI. All rights reserved.</p>
                </div>
            </div>
        </body>
    </html>
    """)
    
    html_content = template.render(
        login_link=f"{FRONTEND_URL}/login",
        logo_url=f"{FRONTEND_URL}/images/othor-logo.png",
        year=datetime.utcnow().year
    )
    
    return send_email(
        to_email=email,
        subject="Welcome to Othor AI!",
        html_content=html_content
    )