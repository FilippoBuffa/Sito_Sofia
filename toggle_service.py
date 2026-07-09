#!/usr/bin/env python3
"""
Script per abilitare/disabilitare l'accettazione di nuove richieste per un servizio.
Uso: python3.10 toggle_service.py

Il servizio resta visibile nel catalogo ma appare grigio e non cliccabile
quando disabilitato — non nasconde il servizio (per quello serve il campo
'active', non gestito da questo script).
"""
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import TestService

app = create_app("development")


def main():
    with app.app_context():
        print("\n=== Abilita/disabilita richieste per un servizio ===\n")

        services = TestService.query.order_by(TestService.name).all()
        if not services:
            print("Nessun servizio presente.")
            return

        for i, s in enumerate(services, 1):
            state = "accetta richieste" if s.accepting_requests else "NON accetta richieste (grigio)"
            print(f"  {i}. {s.name} — {state}")

        raw = input("\nNumero del servizio da modificare: ").strip()
        try:
            idx = int(raw) - 1
            service = services[idx]
        except (ValueError, IndexError):
            print("ERRORE: numero non valido.")
            return

        new_state = not service.accepting_requests
        label = "accetterà" if new_state else "NON accetterà (grigio, non cliccabile)"
        confirm = input(f"'{service.name}' {label} nuove richieste. Confermi? (s/n): ").strip().lower()
        if confirm not in ("s", "si", "sì"):
            print("Annullato.")
            return

        service.accepting_requests = new_state
        db.session.commit()
        print(f"\nFatto: '{service.name}' ora {'accetta' if new_state else 'non accetta'} nuove richieste.")


if __name__ == "__main__":
    main()
