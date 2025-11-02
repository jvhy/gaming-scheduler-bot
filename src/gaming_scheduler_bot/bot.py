from datetime import datetime, timedelta
import os
import logging

import discord
from discord.ext import commands
from discord.ui import Button, View
from sqlalchemy import MetaData, Table, func, select, literal

from db import SessionLocal
from models import ScheduledTime
from scheduling import schedule, cancel
from utils import parse_date, validate_timespan, build_calendar_string, collapse_hours, interpret_relative_date, InvalidDateFormatError, InvalidTimespanError


token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready!")


@bot.command()
async def gaming(ctx, date, timespan=None):
    """Schedule gaming time. Example: !gaming 2023-04-05 18-20"""
    if timespan is None:
        timespan = "09-00"
    try:
        if date.isalpha():
            parsed_date = interpret_relative_date(date)
        else:
            parsed_date = parse_date(date)
        start, end = validate_timespan(timespan)
    except InvalidDateFormatError:
        await ctx.message.reply("Give a proper date, dumbass (YYYY-MM-DD or DD.MM.YYYY)")
    except InvalidTimespanError:
        await ctx.message.reply("Give a valid timespan, dumbass (between 9:00 and 00:00)")

    start_time = parsed_date + timedelta(hours=start)
    end_time = parsed_date + timedelta(hours=end) - timedelta(seconds=1)
    with SessionLocal() as session:
        schedule(session, ctx.author.name, start_time, end_time)
    await ctx.message.reply(f"{ctx.author.display_name} is a certified gamer on {parsed_date.date().strftime('%d.%m.%Y')} at {timespan}.")


@bot.command()
async def busy(ctx, date, timespan=None):
    """Mark busy time. Example: !busy 2023-04-05 14-16"""
    if timespan is None:
        timespan = "09-00"
    try:
        if date.isalpha():
            parsed_date = interpret_relative_date(date)
        else:
            parsed_date = parse_date(date)
        start, end = validate_timespan(timespan)
    except InvalidDateFormatError:
        await ctx.message.reply("Give a proper date, dumbass (YYYY-MM-DD or DD.MM.YYYY)")
    except InvalidTimespanError:
        await ctx.message.reply("Give a valid timespan, dumbass (between 9:00 and 00:00)")

    start_time = parsed_date + timedelta(hours=start)
    end_time = parsed_date + timedelta(hours=end) - timedelta(seconds=1)
    with SessionLocal() as session:
        cancel(session, ctx.author.name, start_time, end_time)
    await ctx.message.reply(f"{ctx.author.display_name} cancelled any planned gaming on {parsed_date.date().strftime('%d.%m.%Y')} at {timespan}.")


@bot.command()
async def calendar(ctx):
    """Show calendar with group availability. Red = bad, Green = good"""
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
        await ctx.message.reply(result)


class HourButton(Button):
    def __init__(self, time_slot, selected):
        label = time_slot.strftime("%H:00")
        style = discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style)
        self.time_slot = time_slot

    async def callback(self, interaction):
        if self.style == discord.ButtonStyle.success:
            with SessionLocal() as session:
                cancel(session, self.view.user, self.time_slot, self.time_slot + timedelta(minutes=59, seconds=59))
            self.style = discord.ButtonStyle.secondary
        else:
            with SessionLocal() as session:
                schedule(session, self.view.user, self.time_slot, self.time_slot + timedelta(minutes=59, seconds=59))
            self.style = discord.ButtonStyle.success
        await interaction.response.edit_message(view=self.view)


class PrevDayButton(Button):
    def __init__(self, disable=False):
        super().__init__(label="⬅️ Prev")
        if disable:
            self.disabled = True

    async def callback(self, interaction):
        view = self.view
        view.day_index -= 1
        view.load_day()
        await view.update_message(interaction)


class NextDayButton(Button):
    def __init__(self, disable=False):
        super().__init__(label="Next ➡️")
        if disable:
            self.disabled = True

    async def callback(self, interaction):
        view = self.view
        view.day_index += 1
        view.load_day()
        await view.update_message(interaction)


class SchedulerView(View):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.day_index = 0
        self.day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.set_message()
        self.load_day()

    def load_day(self):
        # Clear old items
        self.clear_items()

        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.day_start = now + timedelta(days=self.day_index)

        with SessionLocal() as session:
            user_scheduled_times = session.query(ScheduledTime).filter(
                ScheduledTime.user == self.user,
                ScheduledTime.start_time >= self.day_start,
                ScheduledTime.end_time <= self.day_start + timedelta(hours=23, minutes=59, seconds=59)
            ).all()

        scheduled_slots = []
        for time in user_scheduled_times:
            current = time.start_time
            end = time.end_time + timedelta(seconds=1)
            while current < end:
                bucket_end = min(current + timedelta(hours=1), end)
                scheduled_slots.append(current)
                current = bucket_end

        # Add hour buttons for 09:00 → 24:00
        for h in range(9, 24):
            time_slot = self.day_start.replace(hour=h)
            selected = time_slot in scheduled_slots
            self.add_item(HourButton(time_slot, selected))

        # Pagination buttons
        if self.day_index == 0:
            self.add_item(PrevDayButton(disable=True))
            self.add_item(NextDayButton())
        elif self.day_index == 6:
            self.add_item(PrevDayButton())
            self.add_item(NextDayButton(disable=True))
        else:
            self.add_item(PrevDayButton())
            self.add_item(NextDayButton())

    def set_message(self):
        weekday = self.day_start.strftime("%A")
        date_str = self.day_start.strftime("%d.%m.%Y")
        text = f"{weekday}, {date_str}"
        self.message = text

    async def update_message(self, interaction):
        """Updates both buttons and the message text."""
        self.set_message()
        await interaction.response.edit_message(content=self.message, view=self)


@bot.command()
async def scheduler(ctx):
    """Open scheduler UI (works in DMs only)"""
    if isinstance(ctx.message.channel, discord.channel.DMChannel):
        view = SchedulerView(user=ctx.author.name)
        await ctx.send(view.message, view=view, delete_after=120)
    else:
        await ctx.message.reply("Not here dumbass, in DMs")


@bot.command()
async def gamers(ctx, date=None):
    """Show who's gaming. Example: !gamers tomorrow"""
    if date is None:
        date = datetime.today().date()
    else:
        if date.isalpha():
            try:
                date = interpret_relative_date(date).date()
            except InvalidDateFormatError:
                await ctx.message.reply("Give a proper date, dumbass")
                return
        else:
            try:
                date = parse_date(date).date()
            except InvalidDateFormatError:
                await ctx.message.reply("Give a proper date, dumbass")
                return
    with SessionLocal() as session:
        scheduled_times = session.query(ScheduledTime.user, ScheduledTime.start_time, ScheduledTime.end_time).filter(
            func.date(ScheduledTime.start_time) == date
        ).all()
    user_ranges = collapse_hours(scheduled_times)
    date_str = f"{datetime.strftime(date, "%A")}, {datetime.strftime(date, "%d.%m.%Y")}"
    if not user_ranges:
        await ctx.send(f"No gamers on {date_str} :(")
        return
    msg = [f"Gamers on {date_str}:"]
    for user, ranges in user_ranges.items():
        msg.append(f"• **{user}**: {', '.join(ranges)}")
    await ctx.message.reply("\n".join(msg))


def run():
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
