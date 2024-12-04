from sqlalchemy import create_engine
from src.models.base import Base
from src.config.config import Config
from src.models import *

def init_db():
    """Initialize the database with all models"""
    config = Config()
    engine = create_engine(config.database_url)
    Base.metadata.create_all(engine)
