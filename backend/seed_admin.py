from app.database import SessionLocal, Base, engine
from app.models import User, UserRole
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

ADMIN_EMAIL = "admin@eduai.com"
ADMIN_PASSWORD = "1234567890"

existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
if existing:
    print(f"Admin already exists: {ADMIN_EMAIL}")
else:
    admin = User(
        name="Platform admin",
        email=ADMIN_EMAIL,
        hashed_password=hash_password(ADMIN_PASSWORD),
        role=UserRole.admin,
    )
    db.add(admin)
    db.commit()
    print(f"Created admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

db.close()