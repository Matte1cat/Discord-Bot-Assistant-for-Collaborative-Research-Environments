import random
from xmlrpc import client
import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
#from matplotlib.pyplot import cool

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

description = """Example description here"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='$', description=description, intents=intents)

    async def setup_hook(self):
        slow_counter.start()

bot = MyBot()

@tasks.loop(seconds=5, count=3)
async def slow_counter():
    print(f"Current count: {slow_counter.current_loop}")

@slow_counter.after_loop
async def after_slow_counter():
    print("Counter finished.")

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    await bot.process_commands(message)

@bot.command()
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send('Format has to be in NdN!')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.send(result)

@bot.command()
async def test(ctx, arg):
    await ctx.send(arg)


bot.run(BOT_TOKEN)
