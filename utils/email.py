import smtplib 
import os 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart 

def send_invitation_email(to_email:str)->bool:
    try:
        # Get email configuration from environment variables
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = "You are invited to join CopodsConnect"

        body = """
Hi there, 

You have been invited to join CopodsConnect - your team's recognition and cultural plaform. 

Click the link below to sign in with your Google account and get started. 

[Login link will be added here]

Welcome aboard, 
The CopodsConnect Team
"""
        msg.attach(MIMEText(body,'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
        
        return True
    except Exception as e:
        return False
