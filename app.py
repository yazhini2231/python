from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DATABASE = "marketing.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            status TEXT NOT NULL DEFAULT 'New'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    admin = cursor.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()

    if not admin:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    connection.commit()
    connection.close()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect("/")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db()
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def dashboard():
    connection = get_db()
    total_leads = connection.execute(
        "SELECT COUNT(*) FROM leads"
    ).fetchone()[0]
    total_campaigns = connection.execute(
        "SELECT COUNT(*) FROM campaigns"
    ).fetchone()[0]
    converted = connection.execute(
        "SELECT COUNT(*) FROM leads WHERE status = 'Converted'"
    ).fetchone()[0]
    connection.close()

    conversion_rate = round((converted / total_leads) * 100, 1) if total_leads else 0

    return render_template(
        "dashboard.html",
        total_leads=total_leads,
        total_campaigns=total_campaigns,
        converted=converted,
        conversion_rate=conversion_rate
    )


@app.route("/leads")
@login_required
def leads():
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM leads ORDER BY id DESC"
    ).fetchall()
    connection.close()
    return render_template("leads.html", leads=rows)


@app.route("/add-lead", methods=["POST"])
@login_required
def add_lead():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    status = request.form.get("status", "New")

    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect("/leads")

    connection = get_db()
    connection.execute(
        "INSERT INTO leads (name, email, phone, status) VALUES (?, ?, ?, ?)",
        (name, email, phone, status)
    )
    connection.commit()
    connection.close()

    flash("Lead added successfully.", "success")
    return redirect("/leads")


@app.route("/edit-lead/<int:lead_id>", methods=["GET", "POST"])
@login_required
def edit_lead(lead_id):
    connection = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        status = request.form.get("status", "New")

        connection.execute("""
            UPDATE leads
            SET name = ?, email = ?, phone = ?, status = ?
            WHERE id = ?
        """, (name, email, phone, status, lead_id))
        connection.commit()
        connection.close()

        flash("Lead updated successfully.", "success")
        return redirect("/leads")

    lead = connection.execute(
        "SELECT * FROM leads WHERE id = ?", (lead_id,)
    ).fetchone()
    connection.close()

    if not lead:
        return redirect("/leads")

    return render_template("edit_lead.html", lead=lead)


@app.route("/delete-lead/<int:lead_id>")
@login_required
def delete_lead(lead_id):
    connection = get_db()
    connection.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    connection.commit()
    connection.close()

    flash("Lead deleted.", "success")
    return redirect("/leads")


@app.route("/nurture-lead/<int:lead_id>")
@login_required
def nurture_lead(lead_id):
    stages = {
        "New": "Contacted",
        "Contacted": "Qualified",
        "Qualified": "Converted",
        "Converted": "Converted"
    }

    connection = get_db()
    lead = connection.execute(
        "SELECT * FROM leads WHERE id = ?", (lead_id,)
    ).fetchone()

    if lead:
        new_status = stages.get(lead["status"], "New")
        connection.execute(
            "UPDATE leads SET status = ? WHERE id = ?",
            (new_status, lead_id)
        )
        connection.commit()
        flash(f"Lead moved to {new_status}.", "success")

    connection.close()
    return redirect("/leads")


@app.route("/campaigns")
@login_required
def campaigns():
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM campaigns ORDER BY id DESC"
    ).fetchall()
    connection.close()
    return render_template("campaigns.html", campaigns=rows)


@app.route("/add-campaign", methods=["POST"])
@login_required
def add_campaign():
    name = request.form.get("name", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not subject or not message:
        flash("All campaign fields are required.", "error")
        return redirect("/campaigns")

    connection = get_db()
    connection.execute("""
        INSERT INTO campaigns (name, subject, message, status)
        VALUES (?, ?, ?, 'Draft')
    """, (name, subject, message))
    connection.commit()
    connection.close()

    flash("Campaign created as Draft.", "success")
    return redirect("/campaigns")


@app.route("/send-campaign/<int:campaign_id>")
@login_required
def send_campaign(campaign_id):
    # Demo sending: changes status without sending real email.
    connection = get_db()
    campaign = connection.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()

    if campaign:
        connection.execute(
            "UPDATE campaigns SET status = 'Sent' WHERE id = ?",
            (campaign_id,)
        )
        connection.commit()
        flash("Campaign marked as Sent (demo mode).", "success")

    connection.close()
    return redirect("/campaigns")


@app.route("/delete-campaign/<int:campaign_id>")
@login_required
def delete_campaign(campaign_id):
    connection = get_db()
    connection.execute(
        "DELETE FROM campaigns WHERE id = ?", (campaign_id,)
    )
    connection.commit()
    connection.close()

    flash("Campaign deleted.", "success")
    return redirect("/campaigns")


@app.route("/segments")
@login_required
def segments():
    connection = get_db()

    grouped = {}
    for status in ["New", "Contacted", "Qualified", "Converted"]:
        grouped[status] = connection.execute(
            "SELECT * FROM leads WHERE status = ? ORDER BY id DESC",
            (status,)
        ).fetchall()

    connection.close()
    return render_template("segments.html", grouped=grouped)


@app.route("/analytics")
@login_required
def analytics():
    connection = get_db()

    counts = {}
    for status in ["New", "Contacted", "Qualified", "Converted"]:
        counts[status] = connection.execute(
            "SELECT COUNT(*) FROM leads WHERE status = ?",
            (status,)
        ).fetchone()[0]

    total_leads = connection.execute(
        "SELECT COUNT(*) FROM leads"
    ).fetchone()[0]
    total_campaigns = connection.execute(
        "SELECT COUNT(*) FROM campaigns"
    ).fetchone()[0]
    sent_campaigns = connection.execute(
        "SELECT COUNT(*) FROM campaigns WHERE status = 'Sent'"
    ).fetchone()[0]

    connection.close()

    conversion_rate = round(
        (counts["Converted"] / total_leads) * 100, 1
    ) if total_leads else 0

    return render_template(
        "analytics.html",
        total_leads=total_leads,
        total_campaigns=total_campaigns,
        sent_campaigns=sent_campaigns,
        new_count=counts["New"],
        contacted_count=counts["Contacted"],
        qualified_count=counts["Qualified"],
        converted_count=counts["Converted"],
        conversion_rate=conversion_rate
    )


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
