from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os


DATABASE_URL = "sqlite:///" + os.getenv("DB_PATH")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
