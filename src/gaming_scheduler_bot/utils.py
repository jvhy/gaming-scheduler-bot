import calendar
from datetime import date, datetime, timedelta

from models import ScheduledTime


class InvalidDateFormatError(ValueError):
    pass


class InvalidTimespanError(ValueError):
    pass


def parse_date(date_str: str) -> datetime:
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        try:
            parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            raise InvalidDateFormatError("Invalid date format. Please use YYYY-MM-DD or DD.MM.YYYY.")
    parsed_date = datetime.combine(parsed_date, datetime.min.time())
    return parsed_date


def validate_timespan(timespan: str) -> str:
    try:
        start, end = timespan.split("-")
    except ValueError:
        raise InvalidTimespanError("Invalid timespan format. Please use 'start-end'.")
    try:
        start, end = int(start), int(end)
    except ValueError:
        raise InvalidTimespanError("Invalid timespan values. Please provide integers.")
    if start >= end and end != 0:
        raise InvalidTimespanError("Start time must be before the end time.")
    if start < 9 or start > 23:
        raise InvalidTimespanError("Start time must be between 09:00 and 23:00.")
    if (end < 10 or end > 23) and end != 0:
        raise InvalidTimespanError("End time must be between 10:00 and 00:00.")
    if end == 0:
        end = 24
    return start, end


def daterange(start_date: date, end_date: date):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)


def build_calendar_string(hourly_user_counts: dict[datetime, int]) -> str:
    """
    Build a pretty string representing hourly user availability in the next 7 days.

    Args:
        hourly_user_counts: dict that maps hourly datetime-stamps to the number of available users at that time.

    Returns:
        Pretty calendar grid with color coded hourly availability slots:
          - Black  = No users available
          - Red    = 1 user available
          - Yellow = 2-3 users available
          - Green  = 4+ users available 
    """
    today = datetime.today()
    # Get 3-letter weekday name abbreviations for the next 7 days to use as x-axis labels
    weekdays = [(today + timedelta(days=i)).strftime("%a") for i in range(7)]

    calendar_str = " " * 6 + " ".join(weekdays[:4]) + "  " + " ".join(weekdays[4:]) + "\n"

    start = today.date()
    end = start + timedelta(days=7)
    for hour in range(9, 24):
        if hour % 3 == 0:
            calendar_str += f"{hour:02d}:00 "
        else:
            calendar_str += " "*6

        for single_date in daterange(start, end):
            dt = datetime.combine(single_date, datetime.min.time()) + timedelta(hours=hour)
            count = hourly_user_counts.get(dt, 0)
            if count == 0:
                calendar_str += "\U00002B1B"  # black square
            elif count == 1:
                calendar_str += "\U0001F7E5"  # red square
            elif count in [2, 3]:
                calendar_str += "\U0001F7E8"  # yellow square
            elif count >= 4:
                calendar_str += "\U0001F7E9"  # green square

            if single_date == end - timedelta(days=1):
                calendar_str += "\n"
            else:
                calendar_str += "  "
    return "```\n" + calendar_str + "\n```"
