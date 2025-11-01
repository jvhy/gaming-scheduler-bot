from datetime import datetime, timedelta
import os
import logging

import discord
from discord.ext import commands

from db import SessionLocal
from models import ScheduledTime
from utils import parse_date, validate_timespan, InvalidDateFormatError, InvalidTimespanError


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


def run():
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
