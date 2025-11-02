from datetime import datetime, timedelta

from models import ScheduledTime


def schedule(db_session, user: str, start_time: datetime, end_time: datetime):
    overlaps = db_session.query(ScheduledTime).filter(
        ScheduledTime.user == user,
        ScheduledTime.start_time < end_time,
        ScheduledTime.end_time > start_time,
    ).all()
    for slot in overlaps:
        s, e = slot.start_time, slot.end_time

        # Case 1: New time is contained in existing time
        if start_time >= s and end_time <= e:
            continue

        # Case 2: New time extends existing time at the end
        if s <= start_time < e and end_time > e:
            slot.end_time = end_time

        # Case 3: New time extends existing time at the start
        if start_time < s and s < end_time <= e:
            slot.start_time = start_time

        # Case 4: New time extends existing time at both ends
        if start_time < s and end_time > e:
            slot.start_time = start_time
            slot.end_time = end_time

    if not overlaps:
        scheduled_time = ScheduledTime(
            user=user, start_time=start_time, end_time=end_time
        )
        db_session.add(scheduled_time)

    db_session.commit()


def cancel(db_session, user: str, start_time: datetime, end_time: datetime):
    overlaps = db_session.query(ScheduledTime).filter(
        ScheduledTime.user == user,
        ScheduledTime.start_time < end_time,
        ScheduledTime.end_time > start_time,
    ).all()
    for slot in overlaps:
        s, e = slot.start_time, slot.end_time

        # Case 1: Busy time contains a scheduled time
        if start_time <= s and end_time >= e:
            db_session.delete(slot)

        # Case 2: Busy time shortens scheduled time
        elif s < start_time < e <= end_time:
            slot.end_time = start_time - timedelta(seconds=1)

        # Case 3: Busy time delays the start of scheduled time
        elif start_time <= s < end_time < e:
            slot.start_time = end_time + timedelta(seconds=1)

        # Case 4: Busy time is inside scheduled time
        elif s < start_time and e > end_time:
            # left part stays
            left_end = start_time - timedelta(seconds=1)

            # right part becomes a new range
            new_slot = ScheduledTime(
                user=user,
                start_time=end_time + timedelta(seconds=1),
                end_time=e,
            )
            db_session.add(new_slot)

            slot.end_time = left_end

    db_session.commit()
