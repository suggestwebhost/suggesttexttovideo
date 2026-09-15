import os
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Render provides this via Environment Variables automatically
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")

# Fix for Render/Heroku postgresql:// vs postgres:// URL quirk
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Our Data Schema for Videos
class VideoTask(Base):
    __tablename__ = "video_tasks"
    
    id = Column(String, primary_key=True, index=True) # Unique ID (e.g. UUID)
    text = Column(Text, nullable=False)               # The actual heavy text payload
    headline = Column(String, default="")
    num_images = Column(Integer, default=3)
    duration_per_image = Column(Integer, default=3)

# Create the tables in the database if they don't exist
Base.metadata.create_all(bind=engine)
