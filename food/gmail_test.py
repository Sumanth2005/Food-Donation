import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

print("EMAIL_USER =", EMAIL_USER)
print("PASSWORD LOADED =", EMAIL_PASSWORD is not None)

receiver = input("Enter receiver email: ")

msg = MIMEText("FoodShare test email is working.")
msg["Subject"] = "FoodShare Test Email"
msg["From"] = EMAIL_USER
msg["To"] = receiver

try:
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(EMAIL_USER, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()

    print("✅ EMAIL SENT SUCCESSFULLY")

except Exception as e:
    print("❌ EMAIL FAILED:")
    print(e)