import discord
from discord.ext import commands, tasks
import os
import sys
import random
from pathlib import Path
from dotenv import load_dotenv
import logging

# Setup logging with UTF-8 encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logger = logging.getLogger('DiscordBot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    logger.error("DISCORD_TOKEN not found in .env file!")
    sys.exit(1)

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


async def load_cogs():
    """Dynamically load all cogs from the cogs directory"""
    cogs_path = Path('cogs')
    
    if not cogs_path.exists():
        logger.error(f"Cogs directory not found: {cogs_path}")
        return
    
    loaded = 0
    failed = 0
    
    # Walk through all subdirectories in cogs
    for folder in cogs_path.iterdir():
        if folder.is_dir() and not folder.name.startswith('__') and folder.name != 'utils':
            for file in folder.glob('*.py'):
                if file.stem.startswith('__') or file.stem.endswith('_utils') or file.stem.endswith('_view'):
                    continue
                
                # Construct the cog path: cogs.folder.file
                cog_path = f"cogs.{folder.name}.{file.stem}"
                
                try:
                    await bot.load_extension(cog_path)
                    logger.info(f"✓ Loaded: {cog_path}")
                    loaded += 1
                except Exception as e:
                    logger.error(f"✗ Failed to load {cog_path}: {e}")
                    import traceback
                    traceback.print_exc()
                    failed += 1
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Cog Loading Summary: {loaded} loaded, {failed} failed")
    logger.info(f"{'='*50}\n")


@bot.event
async def on_ready():
    """Event triggered when bot successfully connects"""
    logger.info(f"\n{'='*50}")
    logger.info(f"Bot is online!")
    logger.info(f"Logged in as: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    logger.info(f"{'='*50}\n")
    
    # Sync slash commands globally (DON'T clear - that removes everything!)
    try:
        logger.info("Syncing commands globally...")
        synced = await bot.tree.sync()
        logger.info(f"✓ Synced {len(synced)} global slash command(s)")
        
        # List all synced commands
        if synced:
            logger.info("Available commands:")
            for cmd in synced:
                logger.info(f"  - /{cmd.name}")
        else:
            logger.warning("⚠️ No commands were synced! Check if cogs loaded correctly.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        import traceback
        traceback.print_exc()


@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param.name}")
    else:
        logger.error(f"Unhandled error: {error}")


async def main():
    """Main function to start the bot"""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")