import discord
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ DISCORD_TOKEN not found in .env file!")
    exit(1)

# Create a simple bot just to clear commands
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    print(f"✓ Logged in as {bot.user}")
    print(f"✓ Connected to {len(bot.guilds)} guild(s)")
    
    try:
        # Get all current commands first
        print(f"\n🔍 Checking current commands...")
        global_commands = await bot.http.get_global_commands(bot.user.id)
        print(f"  Found {len(global_commands)} global commands")
        
        # Get all guilds
        for guild in bot.guilds:
            print(f"\n🔧 Clearing commands in: {guild.name}")
            
            # Get guild commands
            try:
                guild_commands = await bot.http.get_guild_commands(bot.user.id, guild.id)
                print(f"  Found {len(guild_commands)} guild commands")
            except:
                print(f"  No guild commands to clear")
            
            # Clear guild-specific commands
            tree.clear_commands(guild=guild)
            await tree.sync(guild=guild)
            print(f"  ✓ Cleared guild commands for {guild.name}")
        
        # Clear global commands
        print(f"\n🔧 Clearing global commands...")
        tree.clear_commands(guild=None)
        await tree.sync()
        print(f"  ✓ Cleared global commands")
        
        # Verify cleanup
        print(f"\n🔍 Verifying cleanup...")
        global_commands_after = await bot.http.get_global_commands(bot.user.id)
        print(f"  Remaining global commands: {len(global_commands_after)}")
        
        print("\n✅ All commands cleared successfully!")
        print("\n📝 Next steps:")
        print("1. Close this script (it will auto-close in 5 seconds)")
        print("2. Start your main bot: python main.py")
        print("3. Commands will be registered fresh on startup")
        print("4. No duplicates!")
        
        await asyncio.sleep(5)
        await bot.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await bot.close()

print("🚀 Starting command cleanup script...")
print("This will remove ALL registered commands from Discord")
print("=" * 50)

try:
    bot.run(TOKEN)
except KeyboardInterrupt:
    print("\n⚠️ Script interrupted by user")
except Exception as e:
    print(f"\n❌ Error: {e}")