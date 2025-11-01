import datetime as datetime

from pydantic import BaseModel, field_validator


class ScheduledTimeInput(BaseModel):
    user: str
    start_time: datetime
    end_time: datetime

    @field_validator("end_time")
    def check_time_order(cls, v, info):
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v
