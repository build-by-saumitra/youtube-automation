import bcrypt
from app.db.database import init_db, SessionLocal
from app.db.models import User

init_db()

db = SessionLocal()
if not db.query(User).filter_by(username='admin').first():
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw('Mdnisdas@23'.encode('utf-8'), salt).decode('utf-8')
    admin = User(username='admin', name='Admin User', password_hash=hashed_password)
    db.add(admin)
    db.commit()
    print("Created default admin user (admin / password123)")
else:
    print("Admin user already exists")
db.close()
