from datetime import datetime
import pytz
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Substitua pelos seus dados do XAMPP/MySQL
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/prjgogift"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

TIMEZONE = pytz.timezone('America/Sao_Paulo')

def now_brt():
    """Retorna o datetime atual no fuso horário de São Paulo (BRT)."""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return utc_now.astimezone(TIMEZONE)
 