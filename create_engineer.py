#!/usr/bin/env python3
"""
Script per creare un nuovo account Engineer.
Uso: python3.10 create_engineer.py

Crea l'account nel DB e invia una email con la password temporanea all'engineer.
Al primo login, l'engineer sarà obbligato a cambiare password.
"""
import secrets
import string
import re

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User, TestService

EMAIL_RE = re.compile(r"^[^@\s]+@vernay\.com$", re.IGNORECASE)

app = create_app("development")


def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "Temp_" + "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    with app.app_context():
        print("\n=== Creazione nuovo account Engineer ===\n")

        # --- Dati engineer ---
        first_name = input("Nome: ").strip()
        last_name = input("Cognome: ").strip()
        email = input("Email (@vernay.com): ").strip().lower()

        if not EMAIL_RE.match(email):
            print("ERRORE: l'email deve essere @vernay.com")
            return

        if User.query.filter_by(email=email).first():
            print("ERRORE: esiste già un account con questa email.")
            return

        # --- Servizi ---
        services = TestService.query.filter_by(active=True).all()
        if not services:
            print("ERRORE: nessun servizio attivo nel DB.")
            return

        print("\nServizi disponibili:")
        for i, s in enumerate(services, 1):
            print(f"  {i}. {s.name}")

        raw = input("\nServizi assegnati (numeri separati da virgola, es. 1,2): ").strip()
        selected = []
        for part in raw.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(services):
                    selected.append(services[idx])
            except ValueError:
                pass

        if not selected:
            print("ERRORE: nessun servizio selezionato.")
            return

        # --- Crea utente ---
        username_base = email.split("@")[0]
        username = username_base
        suffix = 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}{suffix}"
            suffix += 1

        temp_password = generate_temp_password()

        engineer = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="engineer",
            email_verified=True,
            must_change_password=True,
        )
        engineer.set_password(temp_password)
        engineer.services = selected
        db.session.add(engineer)
        db.session.commit()

        print(f"\nAccount creato: {email} (password temporanea: {temp_password})")

        # --- Invia email ---
        send_mail = input("Inviare email di benvenuto? (s/n): ").strip().lower()
        if send_mail == "s":
            from app.email_service import send_engineer_welcome
            send_engineer_welcome(engineer, temp_password)
            print("Email inviata.")
        else:
            print(f"Email NON inviata. Comunica manualmente le credenziali.")

        print(f"\nEngineer '{first_name} {last_name}' creato con successo.")
        print(f"Servizi assegnati: {', '.join(s.name for s in selected)}\n")


if __name__ == "__main__":
    main()
