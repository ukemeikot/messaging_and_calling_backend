"""
Email service using Resend API.
Better free tier alternative to SendGrid.

Free Plan: 3,000 emails/month forever
Setup: https://resend.com/
"""

import os
import logging
import resend

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service using Resend HTTP API.
    
    Benefits:
    - Free 3,000 emails/month (forever)
    - Modern API
    - No SMTP port blocking
    - Better developer experience
    """
    
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        self.from_name = os.getenv("RESEND_FROM_NAME", "Your App")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        if not self.api_key:
            logger.warning("⚠️ RESEND_API_KEY not set - emails will fail!")
        else:
            resend.api_key = self.api_key
    
    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str
    ) -> bool:
        """
        Send email verification link.
        """
        if not self.api_key:
            logger.error("❌ Resend API key not set - check RESEND_API_KEY")
            return False
        
        verification_url = f"{self.frontend_url}/verify-email?token={verification_token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✉️ Email Verification</h1>
                </div>
                <div class="content">
                    <h2>Hi {username}! 👋</h2>
                    <p>Thanks for signing up! Please verify your email address to unlock all features:</p>
                    <div style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </div>
                    <div class="warning">
                        ⏰ <strong>This link expires in 24 hours.</strong>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2025 {self.from_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        try:
            # FIX: The SDK expects a dictionary passed to the 'params' argument
            # 'from' is a reserved keyword, so we use a dictionary to avoid syntax errors
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "Verify Your Email Address",
                "html": html_content,
            }
            
            resend.Emails.send(params)
            logger.info(f"✅ Verification email sent to {to_email}")
            return True
                
        except Exception as e:
            logger.error(f"❌ Failed to send verification email to {to_email}: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """
        Send password reset link.
        """
        if not self.api_key:
            logger.error("❌ Resend API key not set")
            return False
        
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body>
            <div class="container">
                <h1>🔒 Password Reset</h1>
                <p>Hi {username}, we received a request to reset your password.</p>
                <a href="{reset_url}">Reset Password</a>
            </div>
        </body>
        </html>
        """
        
        try:
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "Reset Your Password",
                "html": html_content,
            }
            
            resend.Emails.send(params)
            logger.info(f"✅ Password reset email sent to {to_email}")
            return True
                
        except Exception as e:
            logger.error(f"❌ Failed to send password reset email to {to_email}: {str(e)}")
            return False