from datetime import datetime, timedelta
import os
import logging

import discord
from discord.ext import commands
from sqlalchemy import MetaData, Table, func, select, literal

from db import SessionLocal
from models import ScheduledTime
from utils import parse_date, validate_timespan, build_calendar_string, InvalidDateFormatError, InvalidTimespanError


token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready!")


@bot.command()
async def gaming(ctx, date, timespan):
    try:
        parsed_date = parse_date(date)
        start, end = validate_timespan(timespan)
    except InvalidDateFormatError:
        await ctx.message.reply("Give a proper date, dumbass (YYYY-MM-DD or DD.MM.YYYY)")
    except InvalidTimespanError:
        await ctx.message.reply("Give a valid timespan, dumbass (between 9:00 and 00:00)")

    start_time = parsed_date + timedelta(hours=start)
    end_time = parsed_date + timedelta(hours=end) - timedelta(seconds=1)
    with SessionLocal() as session:
        scheduled_time = ScheduledTime(
            user=ctx.author.name, start_time=start_time, end_time=end_time
        )
        # TODO: check for overlap in existing times
        session.add(scheduled_time)
        session.commit()
    await ctx.send(f"{ctx.author.display_name} is a certified gamer on {date} at {timespan}.")


@bot.command()
async def busy(ctx, date, timespan):
    try:
        parsed_date = parse_date(date)
        start, end = validate_timespan(timespan)
    except InvalidDateFormatError:
        await ctx.message.reply("Give a proper date, dumbass (YYYY-MM-DD or DD.MM.YYYY)")
    except InvalidTimespanError:
        await ctx.message.reply("Give a valid timespan, dumbass (between 9:00 and 00:00)")

    start_time = parsed_date + timedelta(hours=start)
    end_time = parsed_date + timedelta(hours=end) - timedelta(seconds=1)
    # Find the overlapping time spans that have been marked as available time
    with SessionLocal() as session:
        overlaps = session.query(ScheduledTime).filter(
            ScheduledTime.user == ctx.author.name,
            ScheduledTime.start_time < end_time,
            ScheduledTime.end_time > start_time,
        ).all()
        for slot in overlaps:
            s, e = slot.start_time, slot.end_time

            # Case 1: Entire slot removed
            if start_time <= s and end_time >= e:
                session.delete(slot)

            # Case 2: Trim left part
            elif s < start_time < e <= end_time:
                slot.end_time = start_time - timedelta(seconds=1)

            # Case 3: Trim right part
            elif start_time <= s < end_time < e:
                slot.start_time = end_time + timedelta(seconds=1)

            # Case 4: Split into two
            elif s < start_time and e > end_time:
                # left part stays
                left_end = start_time - timedelta(seconds=1)

                # right part becomes a new range
                new_slot = ScheduledTime(
                    user=ctx.author.name,
                    start_time=end_time + timedelta(seconds=1),
                    end_time=e,
                )
                session.add(new_slot)

                slot.end_time = left_end

        session.commit()


@bot.command()
async def calendar(ctx):
    with SessionLocal() as session:
        window_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = window_start + timedelta(days=7)

        metadata = MetaData()
        availability = Table("times", metadata, autoload_with=session.bind)

        # Recursive CTE to generate hourly slots
        slots = (
            select(literal(window_start).label("slot_start"))
            .cte("slots", recursive=True)
        )

        slots = slots.union_all(
            select(func.datetime(slots.c.slot_start, "+1 hour"))
            .where(slots.c.slot_start < window_end)
        )

        q = (
            select(
                slots.c.slot_start,
                func.count(func.distinct(availability.c.user)).label("available"),
            )
            .select_from(
                slots.outerjoin(
                    availability,
                    (availability.c.start_time < func.datetime(slots.c.slot_start, "+1 hour"))
                    & (availability.c.end_time > slots.c.slot_start),
                )
            )
            .group_by(slots.c.slot_start)
            .order_by(slots.c.slot_start)
        )

        rows = session.execute(q).all()
        user_counts = {dt: count for dt, count in rows}
        result = build_calendar_string(user_counts)
        await ctx.send(result)


def run():
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
