"""
Emergency script to force sync commands to a specific guild
Run this if /sync_guild command is not showing up
"""
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# CHANGE THIS to your server ID
GUILD_ID = 0  # Replace with your Discord server ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    
    # Get the guild
    guild = discord.Object(id=GUILD_ID)
    
    # Copy global commands to guild
    bot.tree.copy_global_to(guild=guild)
    
    # Sync to guild
    synced = await bot.tree.sync(guild=guild)
    print(f'Synced {len(synced)} commands to guild {GUILD_ID}')
    
    for cmd in synced:
        print(f'  - /{cmd.name}')
    
    print('\nCommands should now appear in your server!')
    await bot.close()

if __name__ == '__main__':
    if GUILD_ID == 0:
        print("ERROR: Please set GUILD_ID in the script first!")
        print("To find your server ID:")
        print("1. Enable Developer Mode in Discord (User Settings > Advanced)")
        print("2. Right-click your server icon")
        print("3. Click 'Copy Server ID'")
    else:
        asyncio.run(bot.start(TOKEN))
