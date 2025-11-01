from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class ScheduledTime(Base):
    __tablename__ = "times"

    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped[str] = mapped_column(String(length=255))
    start_time: Mapped[datetime]
    end_time: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
