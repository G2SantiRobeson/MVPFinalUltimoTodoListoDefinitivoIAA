from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import engine
from app.services.seed import seed_demo_data


def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    seed_demo_data(db)
