"""Database initialization and Greek alphabet seeding."""
from sqlalchemy.orm import Session
from app.db.database import engine, SessionLocal, Base
from app.db.models import Letter

# Complete Greek alphabet with uppercase and lowercase
GREEK_ALPHABET = [
    {"name": "Alpha", "uppercase": "Α", "lowercase": "α", "position": 1},
    {"name": "Beta", "uppercase": "Β", "lowercase": "β", "position": 2},
    {"name": "Gamma", "uppercase": "Γ", "lowercase": "γ", "position": 3},
    {"name": "Delta", "uppercase": "Δ", "lowercase": "δ", "position": 4},
    {"name": "Epsilon", "uppercase": "Ε", "lowercase": "ε", "position": 5},
    {"name": "Zeta", "uppercase": "Ζ", "lowercase": "ζ", "position": 6},
    {"name": "Eta", "uppercase": "Η", "lowercase": "η", "position": 7},
    {"name": "Theta", "uppercase": "Θ", "lowercase": "θ", "position": 8},
    {"name": "Iota", "uppercase": "Ι", "lowercase": "ι", "position": 9},
    {"name": "Kappa", "uppercase": "Κ", "lowercase": "κ", "position": 10},
    {"name": "Lambda", "uppercase": "Λ", "lowercase": "λ", "position": 11},
    {"name": "Mu", "uppercase": "Μ", "lowercase": "μ", "position": 12},
    {"name": "Nu", "uppercase": "Ν", "lowercase": "ν", "position": 13},
    {"name": "Xi", "uppercase": "Ξ", "lowercase": "ξ", "position": 14},
    {"name": "Omicron", "uppercase": "Ο", "lowercase": "ο", "position": 15},
    {"name": "Pi", "uppercase": "Π", "lowercase": "π", "position": 16},
    {"name": "Rho", "uppercase": "Ρ", "lowercase": "ρ", "position": 17},
    {"name": "Sigma", "uppercase": "Σ", "lowercase": "σ", "position": 18},
    {"name": "Tau", "uppercase": "Τ", "lowercase": "τ", "position": 19},
    {"name": "Upsilon", "uppercase": "Υ", "lowercase": "υ", "position": 20},
    {"name": "Phi", "uppercase": "Φ", "lowercase": "φ", "position": 21},
    {"name": "Chi", "uppercase": "Χ", "lowercase": "χ", "position": 22},
    {"name": "Psi", "uppercase": "Ψ", "lowercase": "ψ", "position": 23},
    {"name": "Omega", "uppercase": "Ω", "lowercase": "ω", "position": 24},
]


def seed_letters(db: Session) -> None:
    """Seed the letters table with the Greek alphabet."""
    # Check if already seeded
    existing_count = db.query(Letter).count()
    if existing_count > 0:
        print(f"Letters table already contains {existing_count} entries. Skipping seed.")
        return

    print("Seeding Greek alphabet...")
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        db.add(letter)

    db.commit()
    print(f"Successfully seeded {len(GREEK_ALPHABET)} Greek letters.")


def init_db() -> None:
    """Initialize database: create all tables and seed data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    db = SessionLocal()
    try:
        seed_letters(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialization complete.")
