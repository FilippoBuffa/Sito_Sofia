import re
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from app.email_service import send_verification_email, send_password_reset_email
from . import bp

EMAIL_RE = re.compile(r"^[^@\s]+@vernay\.com$", re.IGNORECASE)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_dashboard()

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.email_verified:
                return redirect(url_for("auth.resend_verification", email=email))
            else:
                login_user(user)
                if user.must_change_password:
                    return redirect(url_for("auth.change_password"))
                next_page = request.args.get("next")
                return redirect(next_page or _dashboard_url(user))
        else:
            error = "Email o password non validi."

    return render_template("auth/login.html", error=error)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_dashboard()

    error = None
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not first_name or not last_name:
            error = "Nome e cognome sono obbligatori."
        elif not EMAIL_RE.match(email):
            error = "L'indirizzo email deve essere un indirizzo @vernay.com."
        elif len(password) < 8:
            error = "La password deve essere di almeno 8 caratteri."
        elif password != confirm:
            error = "Le password non coincidono."
        elif User.query.filter_by(email=email).first():
            error = "Esiste già un account con questa email."
        else:
            # Derive a unique username from email local part
            username_base = email.split("@")[0]
            username = username_base
            suffix = 1
            while User.query.filter_by(username=username).first():
                username = f"{username_base}{suffix}"
                suffix += 1

            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role="client",
                email_verified=False,
            )
            user.set_password(password)
            user.generate_verification_token()
            db.session.add(user)
            db.session.commit()

            send_verification_email(user)
            return redirect(url_for("auth.verify_pending"))

    return render_template("auth/register.html", error=error)


@bp.route("/verify-pending")
def verify_pending():
    return render_template("auth/verify_pending.html")


@bp.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Link di verifica non valido o già utilizzato.", "danger")
        return redirect(url_for("auth.login"))

    user.email_verified = True
    user.verification_token = None
    db.session.commit()
    flash("Email verificata! Ora puoi accedere.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    email = request.args.get("email", "").strip().lower()
    sent = False
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user or user.email_verified:
            # Don't reveal whether the account exists
            sent = True
        else:
            user.generate_verification_token()
            db.session.commit()
            send_verification_email(user)
            sent = True

    return render_template("auth/resend_verification.html", email=email, sent=sent, error=error)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    email = request.args.get("email", "").strip().lower()
    sent = False

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user and user.email_verified:
            user.generate_reset_token()
            db.session.commit()
            send_password_reset_email(user)
        # Always show the same confirmation, whether or not the account exists
        sent = True

    return render_template("auth/forgot_password.html", email=email, sent=sent)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_valid:
        flash("Il link per reimpostare la password non è valido o è scaduto.", "danger")
        return redirect(url_for("auth.forgot_password"))

    error = None
    if request.method == "POST":
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if len(new_pw) < 8:
            error = "La nuova password deve essere di almeno 8 caratteri."
        elif new_pw != confirm:
            error = "Le password non coincidono."
        else:
            user.set_password(new_pw)
            user.clear_reset_token()
            user.must_change_password = False
            db.session.commit()
            flash("Password reimpostata con successo. Ora puoi accedere.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, error=error)


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pw):
            error = "La password attuale non è corretta."
        elif len(new_pw) < 8:
            error = "La nuova password deve essere di almeno 8 caratteri."
        elif new_pw != confirm:
            error = "Le password non coincidono."
        else:
            current_user.set_password(new_pw)
            current_user.must_change_password = False
            db.session.commit()
            flash("Password aggiornata con successo.", "success")
            return redirect(_dashboard_url(current_user))

    return render_template("auth/change_password.html", error=error)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout effettuato.", "info")
    return redirect(url_for("auth.login"))


def _redirect_dashboard():
    return redirect(_dashboard_url(current_user))


def _dashboard_url(user):
    if user.is_engineer:
        return url_for("engineer.dashboard")
    return url_for("client.dashboard")
