import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import datetime
import logging
from ..utils.db import db

logger = logging.getLogger('DiscordBot.Giveaway')

GIVEAWAYS_COLLECTION = "giveaways"
MESSAGES_COLLECTION = "user_messages"

class GiveawayView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.primary, custom_id="join_giveaway")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = str(interaction.message.id)
        giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
        
        if not giveaway:
            await interaction.response.send_message("❌ This giveaway is invalid or lacks data.", ephemeral=True)
            return

        if giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway.get("entrants", []):
            await interaction.response.send_message("You have already joined this giveaway!", ephemeral=True)
            return

        # Check requirements
        if "requirements" in giveaway and giveaway["requirements"]:
            req = giveaway["requirements"]
            if req.get("type") == "messages_per_day":
                min_messages = req.get("min_messages", 0)
                
                # Get message count from DB
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                user_str = str(interaction.user.id)
                guild_str = str(interaction.guild_id)
                msg_data = await db.find_one(MESSAGES_COLLECTION, {'_id': f"{guild_str}:{user_str}"})
                
                user_msg_count = 0
                if msg_data and msg_data.get("date") == today:
                    user_msg_count = msg_data.get("count", 0)
                
                if user_msg_count < min_messages:
                    await interaction.response.send_message(
                        f"❌ You need to send at least **{min_messages}** messages today to join!\n"
                        f"You have sent **{user_msg_count}** messages today.",
                        ephemeral=True
                    )
                    return

        # Add to entrants
        await db.update_one(
            GIVEAWAYS_COLLECTION,
            {'_id': message_id},
            {'$addToSet': {"entrants": interaction.user.id}}
        )
        
        await interaction.response.send_message("✅ You have joined the giveaway!", ephemeral=True)
        
        # Update the embed entry count
        try:
            # Refresh data to get count
            giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
            embed = interaction.message.embeds[0]
            embed.set_field_at(2, name="Entries", value=str(len(giveaway.get("entrants", []))), inline=True)
            await interaction.message.edit(embed=embed)
        except:
            pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"Error in giveaway view: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred connecting to the giveaway.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred connecting to the giveaway.", ephemeral=True)
        except:
            pass

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()
        # Register the view for persistence
        self.bot.add_view(GiveawayView(self.bot))

    async def increment_message_count(self, guild_id, user_id):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        guild_str = str(guild_id)
        user_str = str(user_id)
        doc_id = f"{guild_str}:{user_str}"
        
        msg_data = await db.find_one(MESSAGES_COLLECTION, {'_id': doc_id})
        
        if not msg_data or msg_data.get("date") != today:
            await db.update_one(
                MESSAGES_COLLECTION,
                {'_id': doc_id},
                {'$set': {"date": today, "count": 1}},
                upsert=True
            )
        else:
            await db.update_one(
                MESSAGES_COLLECTION,
                {'_id': doc_id},
                {'$inc': {"count": 1}}
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        await self.increment_message_count(message.guild.id, message.author.id)

    def cog_unload(self):
        self.check_giveaways.cancel()

    def convert_duration(self, duration: str) -> int:
        units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        unit = duration[-1].lower()
        if unit not in units:
            return -1
        try:
            val = int(duration[:-1])
            return val * units[unit]
        except:
            return -1

    @app_commands.command(name="giveawaycreate", description="Start a new giveaway")
    @app_commands.describe(
        prize="What is being given away?", 
        winners="Number of winners", 
        duration="Duration (e.g. 1m, 1h, 1d)",
        min_messages_per_day="Minimum messages per day required to join (optional)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction, prize: str, winners: int, duration: str, min_messages_per_day: int = 0):
        seconds = self.convert_duration(duration)
        if seconds < 1:
            await interaction.response.send_message("❌ Invalid duration format! Use 1m, 1h, 1d etc.", ephemeral=True)
            return

        end_time = datetime.datetime.now().timestamp() + seconds
        
        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize**: {prize}\n**Hosted by**: {interaction.user.mention}", color=discord.Color.gold())
        embed.add_field(name="Ends", value=f"<t:{int(end_time)}:R>", inline=True)
        embed.add_field(name="Winners", value=str(winners), inline=True)
        embed.add_field(name="Entries", value="0", inline=True)
        
        if min_messages_per_day > 0:
            embed.add_field(name="📋 Requirements", value=f"Must send at least {min_messages_per_day} messages today", inline=False)
            
        embed.set_footer(text="Click the button below to join!")

        await interaction.response.send_message("🎉 Giveaway created!", ephemeral=True)
        message = await interaction.channel.send(embed=embed, view=GiveawayView(self.bot))

        await db.insert_one(GIVEAWAYS_COLLECTION, {
            "_id": str(message.id),
            "channel_id": interaction.channel_id,
            "guild_id": interaction.guild_id,
            "prize": prize,
            "winners": winners,
            "end_time": end_time,
            "host_id": interaction.user.id,
            "entrants": [],
            "ended": False,
            "requirements": {
                "type": "messages_per_day",
                "min_messages": min_messages_per_day
            } if min_messages_per_day > 0 else None
        })

    @app_commands.command(name="giveawayend", description="End a giveaway immediately")
    @app_commands.describe(message_id="The ID of the giveaway message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end(self, interaction: discord.Interaction, message_id: str):
        giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
        if not giveaway:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        await self.end_giveaway(message_id)
        await interaction.response.send_message("✅ Giveaway ended.", ephemeral=True)

    @app_commands.command(name="giveawayedit", description="Edit an active giveaway")
    @app_commands.describe(message_id="The ID of the giveaway message", new_prize="New prize name", new_winners="New number of winners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit(self, interaction: discord.Interaction, message_id: str, new_prize: str = None, new_winners: int = None):
        giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
        if not giveaway:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        update = {}
        if new_prize: update["prize"] = new_prize
        if new_winners: update["winners"] = new_winners
            
        if update:
            await db.update_one(GIVEAWAYS_COLLECTION, {'_id': message_id}, {'$set': update})
        
        # Update message
        try:
            channel = self.bot.get_channel(giveaway["channel_id"])
            if channel:
                message = await channel.fetch_message(int(message_id))
                embed = message.embeds[0]
                prize_name = new_prize if new_prize else giveaway['prize']
                winners_val = new_winners if new_winners else giveaway['winners']
                embed.description = f"**Prize**: {prize_name}\n**Hosted by**: <@{giveaway['host_id']}>"
                embed.set_field_at(1, name="Winners", value=str(winners_val), inline=True)
                await message.edit(embed=embed)
                await interaction.response.send_message("✅ Giveaway updated!", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ Giveaway updated, but channel not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to update message: {e}", ephemeral=True)

    @app_commands.command(name="giveawayreroll", description="Reroll a giveaway winner")
    @app_commands.describe(message_id="The ID of the giveaway message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, message_id: str):
        giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
        if not giveaway:
             await interaction.response.send_message("❌ Giveaway data not found.", ephemeral=True)
             return

        entrants = giveaway.get("entrants", [])
        if not entrants:
             await interaction.response.send_message("❌ No entrants to reroll from.", ephemeral=True)
             return
             
        winner_id = random.choice(entrants)
        channel = self.bot.get_channel(giveaway["channel_id"])
        if channel:
            await channel.send(f"🎉 New winner is <@{winner_id}>! Congratulations!")
            await interaction.response.send_message("✅ Rerolled!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

    async def end_giveaway(self, message_id):
        giveaway = await db.find_one(GIVEAWAYS_COLLECTION, {'_id': message_id})
        if not giveaway or giveaway.get("ended", False):
            return

        channel = self.bot.get_channel(giveaway["channel_id"])
        if not channel:
            await db.update_one(GIVEAWAYS_COLLECTION, {'_id': message_id}, {'$set': {"ended": True}})
            return

        try:
            message = await channel.fetch_message(int(message_id))
        except:
            await db.update_one(GIVEAWAYS_COLLECTION, {'_id': message_id}, {'$set': {"ended": True}})
            return

        entrants = giveaway.get("entrants", [])
        winners_count = giveaway["winners"]
        prize = giveaway["prize"]

        if not entrants:
            await channel.send(f"❌ Giveaway for **{prize}** ended with no entrants.")
            embed = message.embeds[0]
            embed.title = "🎉 GIVEAWAY ENDED 🎉"
            embed.color = discord.Color.dark_gray()
            embed.set_footer(text="Ended")
            await message.edit(embed=embed, view=None)
        else:
            winners = random.sample(entrants, min(len(entrants), winners_count))
            winner_mentions = ", ".join([f"<@{w}>" for w in winners])
            await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**!")
            
            embed = message.embeds[0]
            embed.title = "🎉 GIVEAWAY ENDED 🎉"
            embed.color = discord.Color.green()
            embed.add_field(name="Winners", value=winner_mentions, inline=False)
            embed.set_footer(text="Ended")
            await message.edit(embed=embed, view=None)

        await db.update_one(GIVEAWAYS_COLLECTION, {'_id': message_id}, {'$set': {"ended": True}})

    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        now = datetime.datetime.now().timestamp()
        col = await db.get_collection(GIVEAWAYS_COLLECTION)
        if col is None: return
        
        cursor = col.find({"ended": False, "end_time": {"$lte": now}})
        to_end = await cursor.to_list(length=None)
        
        for giveaway in to_end:
            await self.end_giveaway(giveaway['_id'])

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
