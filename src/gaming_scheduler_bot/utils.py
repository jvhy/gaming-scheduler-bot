from datetime import datetime


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
    if (end < 10 or end < 23) and end != 0:
        raise InvalidTimespanError("End time must be between 10:00 and 00:00.")
    return timespan
