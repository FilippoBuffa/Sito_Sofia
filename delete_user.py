#!/usr/bin/env python3
"""
Script per cancellare un account (client o engineer).
Uso: python3.10 delete_user.py

Rifiuta la cancellazione se l'account ha richieste di test o commenti
collegati, a meno che non si passi --force (in tal caso le richieste
collegate restano nel DB con un riferimento "orfano" all'utente
cancellato — usalo solo se sai cosa stai facendo).
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app("development")


def main():
    force = "--force" in sys.argv

    with app.app_context():
        print("\n=== Cancellazione account ===\n")

        users = User.query.order_by(User.role, User.email).all()
        if not users:
            print("Nessun account presente.")
            return

        print("Account esistenti:")
        for u in users:
            submitted = u.submitted_requests.count()
            assigned = u.assigned_requests.count()
            comments = u.comments.count()
            flags = []
            if submitted:
                flags.append(f"{submitted} richieste inviate")
            if assigned:
                flags.append(f"{assigned} richieste assegnate")
            if comments:
                flags.append(f"{comments} commenti")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            print(f"  - {u.email} ({u.role}, {u.display_name}){flag_str}")

        email = input("\nEmail dell'account da cancellare: ").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            print("ERRORE: nessun account con questa email.")
            return

        submitted = user.submitted_requests.count()
        assigned = user.assigned_requests.count()
        comments = user.comments.count()

        if (submitted or assigned or comments) and not force:
            print(
                f"\nERRORE: '{user.email}' ha dati collegati "
                f"({submitted} richieste inviate, {assigned} richieste assegnate, {comments} commenti)."
            )
            print(
                "Cancellarlo lascerebbe quelle richieste con un riferimento a un utente inesistente "
                "e romperebbe le pagine che le mostrano."
            )
            print("Se vuoi comunque procedere: python3.10 delete_user.py --force")
            return

        confirm = input(f"\nConfermi la cancellazione di '{user.email}' ({user.role})? Scrivi 'sì' per confermare: ").strip().lower()
        if confirm not in ("si", "sì"):
            print("Annullato.")
            return

        db.session.delete(user)
        db.session.commit()
        print(f"\nAccount '{email}' cancellato.")


if __name__ == "__main__":
    main()
