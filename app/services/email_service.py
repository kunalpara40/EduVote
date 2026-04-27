import smtplib
from email.message import EmailMessage
import requests
import base64
from app.config import Config

def get_google_access_token():
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "refresh_token": Config.GOOGLE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]

def send_otp_email_helper(recipient_email, otp):
    access_token = get_google_access_token()
    auth_string = f"user={Config.GOOGLE_USER}\1auth=Bearer {access_token}\1\1"
    
    msg = EmailMessage()
    msg['Subject'] = 'Your Registration OTP for EduVote'
    msg['From'] = Config.GOOGLE_USER
    msg['To'] = recipient_email
    
    msg.set_content(f"Welcome to EduVote!\n\nYour OTP for registration is: {otp}.\nIt is valid for this session.\n\nThank you!")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f6f9fc; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .header {{ background: #4f46e5; padding: 30px; text-align: center; color: white; }}
            .header h1 {{ margin: 0; font-size: 28px; letter-spacing: 1px; }}
            .content {{ padding: 40px 30px; color: #333333; line-height: 1.6; }}
            .content p {{ font-size: 16px; margin-bottom: 20px; }}
            .otp-box {{ background: #f3f4f6; border: 2px dashed #4f46e5; border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0; }}
            .otp-code {{ font-size: 36px; font-weight: bold; color: #4f46e5; letter-spacing: 8px; margin: 0; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to EduVote!</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Thank you for registering with <strong>EduVote</strong>! To complete your registration securely, please use the following verification code:</p>
                
                <div class="otp-box">
                    <p class="otp-code">{otp}</p>
                </div>
                
                <p>This code is valid for your current session. Please do not share this code with anyone.</p>
                <p>If you did not initiate this registration request, you can safely ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 EduVote Team. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.add_alternative(html_content, subtype='html')

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.docmd("AUTH", "XOAUTH2 " + base64.b64encode(auth_string.encode()).decode())
    server.send_message(msg)
    server.quit()
