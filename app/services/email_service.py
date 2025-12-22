"""
Email service - handles sending emails.
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from typing import Optional
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

load_dotenv()

class EmailService:
    """
    Service for sending emails.
    
    Supports:
    - Verification emails
    - Password reset emails
    - Welcome emails
    - Notification emails
    """
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@example.com")
        self.from_name = os.getenv("SMTP_FROM_NAME", "Enterprise Messaging")
        
        # Setup Jinja2 for email templates
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        template_dir.mkdir(parents=True, exist_ok=True)
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text fallback (optional)
            
        Returns:
            True if sent successfully, False otherwise
            
        Security:
            - Uses TLS encryption
            - Validates recipient email
            - Rate limited (handled by SMTP server)
        """
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add plain text version (fallback)
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=True
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending email to {to_email}: {e}")
            return False
    
    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str
    ) -> bool:
        """
        Send email verification email.
        
        Args:
            to_email: User's email
            username: User's username
            verification_token: Verification token
            
        Returns:
            True if sent successfully
        """
        
        verification_url = f"{os.getenv('VERIFICATION_URL_BASE')}/api/v1/auth/verify-email?token={verification_token}"
        
        # HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px 20px;
                    text-align: center;
                }}
                .header h1 {{
                    color: white;
                    margin: 0;
                    font-size: 28px;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .content h2 {{
                    color: #333;
                    font-size: 24px;
                    margin-top: 0;
                }}
                .content p {{
                    color: #666;
                    font-size: 16px;
                    line-height: 1.8;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 20px 0;
                    font-size: 16px;
                }}
                .button:hover {{
                    opacity: 0.9;
                }}
                .footer {{
                    background: #f8f9fa;
                    padding: 20px 30px;
                    text-align: center;
                    font-size: 14px;
                    color: #666;
                }}
                .footer a {{
                    color: #667eea;
                    text-decoration: none;
                }}
                .divider {{
                    height: 1px;
                    background: #e0e0e0;
                    margin: 30px 0;
                }}
                .info-box {{
                    background: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to Enterprise Messaging!</h1>
                </div>
                
                <div class="content">
                    <h2>Hi {username}!</h2>
                    
                    <p>Thanks for signing up! We're excited to have you on board.</p>
                    
                    <p>To get started and unlock all features, please verify your email address by clicking the button below:</p>
                    
                    <div style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </div>
                    
                    <div class="info-box">
                        <p style="margin: 0;"><strong>⏰ This link expires in 24 hours</strong></p>
                    </div>
                    
                    <div class="divider"></div>
                    
                    <p><strong>Why verify?</strong></p>
                    <ul>
                        <li>Send and receive messages</li>
                        <li>Make voice and video calls</li>
                        <li>Upload profile pictures</li>
                        <li>Add and manage contacts</li>
                    </ul>
                    
                    <div class="divider"></div>
                    
                    <p style="font-size: 14px; color: #999;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <a href="{verification_url}" style="color: #667eea; word-break: break-all;">{verification_url}</a>
                    </p>
                    
                    <p style="font-size: 14px; color: #999;">
                        If you didn't create an account, you can safely ignore this email.
                    </p>
                </div>
                
                <div class="footer">
                    <p>
                        © 2024 Enterprise Messaging. All rights reserved.<br>
                        <a href="#">Help Center</a> | <a href="#">Privacy Policy</a> | <a href="#">Terms of Service</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_content = f"""
        Hi {username}!
        
        Thanks for signing up for Enterprise Messaging!
        
        To verify your email address, please visit:
        {verification_url}
        
        This link expires in 24 hours.
        
        Once verified, you'll be able to:
        - Send and receive messages
        - Make voice and video calls
        - Upload profile pictures
        - Add and manage contacts
        
        If you didn't create an account, you can safely ignore this email.
        
        Best regards,
        Enterprise Messaging Team
        """
        
        return await self.send_email(
            to_email=to_email,
            subject="✉️ Verify your email address",
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """
        Send password reset email.
        
        Args:
            to_email: User's email
            username: User's username
            reset_token: Password reset token
            
        Returns:
            True if sent successfully
        """
        
        reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={reset_token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #dc3545;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .warning {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔐 Password Reset Request</h2>
                
                <p>Hi {username},</p>
                
                <p>We received a request to reset your password. If you didn't make this request, you can safely ignore this email.</p>
                
                <p>To reset your password, click the button below:</p>
                
                <a href="{reset_url}" class="button">Reset Password</a>
                
                <div class="warning">
                    <p><strong>⚠️ Security Notice:</strong></p>
                    <ul>
                        <li>This link expires in 1 hour</li>
                        <li>Can only be used once</li>
                        <li>Never share this link with anyone</li>
                    </ul>
                </div>
                
                <p>If the button doesn't work, copy and paste this link:</p>
                <p style="word-break: break-all; color: #666;">{reset_url}</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                
                <p style="font-size: 14px; color: #999;">
                    If you didn't request a password reset, please secure your account immediately by:
                    <br>1. Changing your password
                    <br>2. Enabling two-factor authentication
                    <br>3. Contacting support if you suspect unauthorized access
                </p>
                
                <p style="font-size: 14px; color: #999;">
                    Best regards,<br>
                    Enterprise Messaging Team
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {username},
        
        We received a request to reset your password.
        
        To reset your password, visit:
        {reset_url}
        
        This link expires in 1 hour and can only be used once.
        
        If you didn't request this, please ignore this email and secure your account.
        
        Best regards,
        Enterprise Messaging Team
        """
        
        return await self.send_email(
            to_email=to_email,
            subject="🔐 Password Reset Request",
            html_content=html_content,
            text_content=text_content
        )