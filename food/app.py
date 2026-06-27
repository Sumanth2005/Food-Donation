from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
import os
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = "foodshare_secret_key"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def valid_name(name):
    return re.fullmatch(r"[A-Za-z ]+", name) is not None


def valid_phone(phone):
    return re.fullmatch(r"[0-9]{10}", phone) is not None


def valid_email(email):
    return re.fullmatch(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email) is not None


import requests

def send_email(to_email, subject, body):
    try:
        BREVO_API_KEY = os.getenv("BREVO_API_KEY")

        if not BREVO_API_KEY:
            print("Email failed: BREVO_API_KEY missing")
            return False

        if not EMAIL_USER:
            print("Email failed: EMAIL_USER missing")
            return False

        url = "https://api.brevo.com/v3/smtp/email"

        payload = {
            "sender": {
                "name": "FoodShare",
                "email": EMAIL_USER
            },
            "to": [
                {
                    "email": to_email
                }
            ],
            "subject": subject,
            "textContent": body
        }

        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        print("Brevo status:", response.status_code)
        print("Brevo response:", response.text)

        return response.status_code in [200, 201, 202]

    except Exception as e:
        print("Email failed:", e)
        return False

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "")

        if not valid_name(name):
            flash("Name must contain only alphabets.")
            return redirect(url_for("login", next=next_page))

        if not valid_email(email):
            flash("Enter valid email address.")
            return redirect(url_for("login", next=next_page))

        if not valid_phone(phone):
            flash("Enter 10 digit phone number.")
            return redirect(url_for("login", next=next_page))

        if role not in ["donate", "ngo"]:
            flash("Please select Donate or NGO.")
            return redirect(url_for("login", next=next_page))

        session["name"] = name
        session["email"] = email
        session["phone"] = phone
        session["role"] = role

        supabase.table("users").insert({
            "name": name,
            "email": email,
            "phone": phone,
            "role": role
        }).execute()

        if next_page == "available_food":
            return redirect(url_for("available_food"))

        if role == "donate":
            return redirect(url_for("donor"))

        return redirect(url_for("ngo"))

    return render_template("login.html")


@app.route("/donor", methods=["GET", "POST"])
def donor():
    if request.method == "POST":
        donor_name = request.form.get("donor_name", "").strip()
        location = request.form.get("location", "").strip()
        quantity = request.form.get("quantity", "").strip()
        food_type = request.form.get("food_type", "").strip()

        if not valid_name(donor_name):
            flash("Donor name must contain only alphabets.")
            return redirect(url_for("donor"))

        if location == "" or quantity == "" or food_type == "":
            flash("Please fill all fields.")
            return redirect(url_for("donor"))

        supabase.table("donations").insert({
            "donor_name": donor_name,
            "donor_phone": session.get("phone"),
            "donor_email": session.get("email"),
            "location": location,
            "quantity": int(quantity),
            "food_type": food_type,
            "status": "available",
            "proof_status": "not_uploaded"
        }).execute()

        return redirect(url_for("success"))

    return render_template("donor.html")


@app.route("/ngo", methods=["GET", "POST"])
def ngo():
    if request.method == "POST":
        ngo_name = request.form.get("ngo_name", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()

        if not valid_name(ngo_name):
            flash("NGO name must contain only alphabets.")
            return redirect(url_for("ngo"))

        if location == "":
            flash("Please enter NGO location.")
            return redirect(url_for("ngo"))

        if not valid_phone(phone):
            flash("Enter 10 digit phone number.")
            return redirect(url_for("ngo"))

        session["ngo_name"] = ngo_name
        session["ngo_location"] = location
        session["ngo_phone"] = phone

        supabase.table("ngos").insert({
            "ngo_name": ngo_name,
            "location": location,
            "phone": phone
        }).execute()

        return redirect(url_for("available_food"))

    return render_template("ngo.html")


@app.route("/available_food")
def available_food():
    response = (
        supabase.table("donations")
        .select("*")
        .eq("status", "available")
        .gt("quantity", 0)
        .execute()
    )

    return render_template("available_food.html", foods=response.data)


@app.route("/order/<int:food_id>", methods=["GET", "POST"])
def order(food_id):
    food_response = supabase.table("donations").select("*").eq("id", food_id).execute()

    if not food_response.data:
        flash("Food not found.")
        return redirect(url_for("available_food"))

    food = food_response.data[0]

    if request.method == "POST":
        required_quantity = request.form.get("required_quantity", "").strip()

        if required_quantity == "":
            flash("Please enter required quantity.")
            return redirect(url_for("order", food_id=food_id))

        required_quantity = int(required_quantity)
        available_quantity = int(food["quantity"])

        if required_quantity <= 0:
            flash("Quantity must be greater than 0.")
            return redirect(url_for("order", food_id=food_id))

        if required_quantity > available_quantity:
            flash("Required quantity is more than available quantity.")
            return redirect(url_for("order", food_id=food_id))

        remaining_quantity = available_quantity - required_quantity
        ngo_name = session.get("ngo_name", "NGO User")

        supabase.table("orders").insert({
            "food_id": food_id,
            "ngo_name": ngo_name,
            "required_quantity": required_quantity,
            "status": "ordered",
            "ordered_at": datetime.now().isoformat()
        }).execute()

        new_status = "available" if remaining_quantity > 0 else "ordered"

        supabase.table("donations").update({
            "quantity": remaining_quantity,
            "ordered_by": ngo_name,
            "status": new_status,
            "proof_status": "pending_upload"
        }).eq("id", food_id).execute()

        session["last_order_food_id"] = food_id

        return redirect(url_for("order_success"))

    return render_template("order_quantity.html", food=food)


@app.route("/upload_proof/<int:food_id>", methods=["GET", "POST"])
def upload_proof(food_id):
    if request.method == "POST":
        ngo_name = request.form.get("ngo_name", "").strip()
        ngo_location = request.form.get("ngo_location", "").strip()
        ngo_phone = request.form.get("ngo_phone", "").strip()
        people_served = request.form.get("people_served", "").strip()
        proof_image = request.files.get("proof_image")

        if not valid_name(ngo_name):
            flash("NGO name must contain only alphabets.")
            return redirect(url_for("upload_proof", food_id=food_id))

        if ngo_location == "":
            flash("Please enter NGO location.")
            return redirect(url_for("upload_proof", food_id=food_id))

        if not valid_phone(ngo_phone):
            flash("Enter valid 10 digit NGO phone number.")
            return redirect(url_for("upload_proof", food_id=food_id))

        if people_served == "":
            flash("Please enter people served.")
            return redirect(url_for("upload_proof", food_id=food_id))

        if proof_image is None or proof_image.filename == "":
            flash("Please upload proof image.")
            return redirect(url_for("upload_proof", food_id=food_id))

        filename = secure_filename(proof_image.filename)
        filename = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        proof_image.save(filepath)

        supabase.table("donations").update({
            "ngo_name": ngo_name,
            "ngo_location": ngo_location,
            "ngo_phone": ngo_phone,
            "people_served": int(people_served),
            "proof_image": "uploads/" + filename,
            "status": "proof_uploaded",
            "proof_status": "waiting_admin_verification"
        }).eq("id", food_id).execute()

        return redirect(url_for("proof_submitted"))

    return render_template("upload_proof.html", food_id=food_id)


@app.route("/proof_submitted")
def proof_submitted():
    return render_template("proof_submitted.html")


@app.route("/impact")
def impact():
    food_id = session.get("last_order_food_id")

    if food_id:
        response = supabase.table("donations").select("*").eq("id", food_id).execute()
    else:
        response = (
            supabase.table("donations")
            .select("*")
            .neq("status", "available")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

    donation = response.data[0] if response.data else None
    return render_template("impact.html", donation=donation)


@app.route("/admin_verify")
def admin_verify():
    response = (
        supabase.table("donations")
        .select("*")
        .eq("proof_status", "waiting_admin_verification")
        .execute()
    )

    return render_template("admin_verify.html", proofs=response.data)


@app.route("/approve/<int:food_id>")
def approve(food_id):
    response = supabase.table("donations").select("*").eq("id", food_id).execute()

    if not response.data:
        flash("Donation not found.")
        return redirect(url_for("admin_verify"))

    donation = response.data[0]

    if donation.get("proof_status") != "waiting_admin_verification" or not donation.get("proof_image"):
        flash("Cannot approve. NGO must upload proof first.")
        return redirect(url_for("admin_verify"))

    supabase.table("donations").update({
        "status": "completed",
        "proof_status": "approved",
        "completed_at": datetime.now().isoformat()
    }).eq("id", food_id).execute()

    donor_email = donation.get("donor_email")

    if donor_email:
        subject = "FoodShare - Your Donation Has Been Successfully Distributed"

        body = f"""
Hello {donation.get("donor_name")},

Your food donation has been successfully verified and distributed.

Donation Details:
Food Donated: {donation.get("food_type")}
Ordered By NGO: {donation.get("ngo_name")}
NGO Location: {donation.get("ngo_location")}
NGO Contact Number: {donation.get("ngo_phone")}
People Served: {donation.get("people_served")}

Your donated food has been supplied to people in need.

Thank you for donating through FoodShare.

Regards,
FoodShare Team
"""

        email_sent = send_email(donor_email, subject, body)

        if email_sent:
            flash("Donation approved and email sent to donor.")
        else:
            flash("Donation approved, but email sending failed. Check terminal.")

    else:
        flash("Donation approved, but donor email was not found.")

    return redirect(url_for("admin_verify"))


@app.route("/reject/<int:food_id>")
def reject(food_id):
    supabase.table("donations").update({
        "status": "flagged",
        "proof_status": "rejected"
    }).eq("id", food_id).execute()

    return redirect(url_for("admin_verify"))


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/order_success")
def order_success():
    return render_template("order_success.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
