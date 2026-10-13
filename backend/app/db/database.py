import os
from sqlmodel import SQLModel, create_engine, Session, select
from backend.app.db.models import SchemaVersion

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DB_PATH = os.path.join(ROOT_DIR, "artifacts", "synera.db")
os.makedirs(os.path.join(ROOT_DIR, "artifacts"), exist_ok=True)
sqlite_url = f"sqlite:///{DB_PATH}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def migrate_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        version = session.exec(select(SchemaVersion)).first()
        if not version:
            session.add(SchemaVersion(version=1))
            session.commit()

def get_session():
    with Session(engine) as session:
        yield session
