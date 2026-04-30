import random
from xmlrpc import client
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
#from matplotlib.pyplot import cool

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DISCORD_TEST_GUILD_ID = os.getenv('DISCORD_TEST_GUILD_ID')

description = """Example description here"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', description=description, intents=intents)

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
    synced = await bot.tree.sync() # 
    #TODO : as of now we wait only for the test guild, but we should also sync globally
    #synced = await bot.tree.sync(guild=discord.Object(id=DISCORD_TEST_GUILD_ID))
    print(f"Bot connected and commands synchronized!")
    print(f"Synced {len(synced)} commands for test guild.")
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    await bot.process_commands(message)

@bot.hybrid_command(name="roll", description="Rolls a dice in NdN format.")
@app_commands.describe(
    dice="The dice to roll, in NdN format (e.g., 2d6)"
    )
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send('Format has to be in NdN!')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.send(result)

@bot.hybrid_command(name="test", description="Test command")
@app_commands.describe(
    arg="A string argument to test the command"
    )
async def test(ctx, arg: str):
    await ctx.send(arg)

bot.run(BOT_TOKEN)
