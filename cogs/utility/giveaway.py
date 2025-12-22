import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import random
import datetime
import logging
from pathlib import Path

logger = logging.getLogger('DiscordBot.Giveaway')

class GiveawayView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.primary, custom_id="join_giveaway")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We don't need to store the user in a list here if we just fetch reactions or use the interaction to verify.
        # However, for a persistent button, we usually want to track entries.
        # A simple way is to just acknowledge the interaction.
        # But to pick a winner, we need a list of entrants.
        # We can store entrants in the JSON or fetch them from the message reactions/interaction history (harder).
        # Let's store entrants in the JSON for persistence.
        
        cog = self.bot.get_cog("Giveaway")
        if not cog:
            await interaction.response.send_message("❌ Giveaway system error.", ephemeral=True)
            return

        message_id = str(interaction.message.id)
        if message_id not in cog.giveaways:
            await interaction.response.send_message("❌ This giveaway is invalid.", ephemeral=True)
            return

        giveaway = cog.giveaways[message_id]
        
        if giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway.get("entrants", []):
            # Optional: Allow leaving? For now, just say they joined.
            await interaction.response.send_message("You have already joined this giveaway!", ephemeral=True)
            return

        # Check requirements
        if "requirements" in giveaway and giveaway["requirements"]:
            req = giveaway["requirements"]
            if req.get("type") == "messages_per_day":
                min_messages = req.get("min_messages", 0)
                user_msg_count = await cog.get_user_message_count(interaction.guild_id, interaction.user.id)
                
                if user_msg_count < min_messages:
                    await interaction.response.send_message(
                        f"❌ You need to send at least **{min_messages}** messages today to join!\n"
                        f"You have sent **{user_msg_count}** messages today.",
                        ephemeral=True
                    )
                    return

        if "entrants" not in giveaway:
            giveaway["entrants"] = []
        
        giveaway["entrants"].append(interaction.user.id)
        cog.save_giveaways()
        
        await interaction.response.send_message("✅ You have joined the giveaway!", ephemeral=True)
        
        # Update the embed entry count
        try:
            embed = interaction.message.embeds[0]
            embed.set_field_at(2, name="Entries", value=str(len(giveaway["entrants"])), inline=True)
            await interaction.message.edit(embed=embed)
        except:
            pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions"""
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
        self.data_path = Path("data/giveaways.json")
        self.message_data_path = Path("data/user_messages.json")
        self.giveaways = self.load_giveaways()
        self.message_data = self.load_message_data()
        self.check_giveaways.start()
        
        # Register the view for persistence
        self.bot.add_view(GiveawayView(self.bot))

    def load_giveaways(self):
        if not self.data_path.exists():
            return {}
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load giveaways: {e}")
            return {}

    def save_giveaways(self):
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.giveaways, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save giveaways: {e}")

    def load_message_data(self):
        if not self.message_data_path.exists():
            return {}
        try:
            with open(self.message_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load message data: {e}")
            return {}

    def save_message_data(self):
        try:
            with open(self.message_data_path, "w", encoding="utf-8") as f:
                json.dump(self.message_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save message data: {e}")

    async def increment_message_count(self, guild_id, user_id):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        guild_str = str(guild_id)
        user_str = str(user_id)
        
        if guild_str not in self.message_data:
            self.message_data[guild_str] = {}
        
        if user_str not in self.message_data[guild_str]:
            self.message_data[guild_str][user_str] = {
                "date": today,
                "count": 0
            }
        
        user_data = self.message_data[guild_str][user_str]
        
        # Reset if new day
        if user_data["date"] != today:
            user_data["date"] = today
            user_data["count"] = 0
        
        user_data["count"] += 1
        self.save_message_data()

    async def get_user_message_count(self, guild_id, user_id):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        guild_str = str(guild_id)
        user_str = str(user_id)
        
        if guild_str not in self.message_data:
            return 0
        if user_str not in self.message_data[guild_str]:
            return 0
        
        user_data = self.message_data[guild_str][user_str]
        
        # Return 0 if data is from a different day
        if user_data["date"] != today:
            return 0
        
        return user_data["count"]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        # Update message count for user
        await self.increment_message_count(
            message.guild.id,
            message.author.id
        )

    def cog_unload(self):
        self.check_giveaways.cancel()

    def convert_duration(self, duration: str) -> int:
        """Convert duration string (e.g. 1m, 1h, 1d) to seconds"""
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
        end_dt = datetime.datetime.fromtimestamp(end_time)
        
        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize**: {prize}\n**Hosted by**: {interaction.user.mention}", color=discord.Color.gold())
        embed.add_field(name="Ends", value=f"<t:{int(end_time)}:R>", inline=True)
        embed.add_field(name="Winners", value=str(winners), inline=True)
        embed.add_field(name="Entries", value="0", inline=True)
        
        if min_messages_per_day > 0:
            embed.add_field(
                name="📋 Requirements",
                value=f"Must send at least {min_messages_per_day} messages today",
                inline=False
            )
            
        embed.set_footer(text="Click the button below to join!")

        await interaction.response.send_message("🎉 Giveaway created!", ephemeral=True)
        message = await interaction.channel.send(embed=embed, view=GiveawayView(self.bot))

        self.giveaways[str(message.id)] = {
            "channel_id": interaction.channel_id,
            "guild_id": interaction.guild_id,
            "prize": prize,
            "winners": winners,
            "end_time": end_time,
            "host_id": interaction.user.id,
            "entrants": [],
            "requirements": {
                "type": "messages_per_day",
                "min_messages": min_messages_per_day
            } if min_messages_per_day > 0 else None
        }
        self.save_giveaways()

    @app_commands.command(name="giveawayend", description="End a giveaway immediately")
    @app_commands.describe(message_id="The ID of the giveaway message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end(self, interaction: discord.Interaction, message_id: str):
        if message_id not in self.giveaways:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        await self.end_giveaway(message_id)
        await interaction.response.send_message("✅ Giveaway ended.", ephemeral=True)

    @app_commands.command(name="giveawayedit", description="Edit an active giveaway")
    @app_commands.describe(message_id="The ID of the giveaway message", new_prize="New prize name", new_winners="New number of winners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit(self, interaction: discord.Interaction, message_id: str, new_prize: str = None, new_winners: int = None):
        if message_id not in self.giveaways:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        giveaway = self.giveaways[message_id]
        
        if new_prize:
            giveaway["prize"] = new_prize
        if new_winners:
            giveaway["winners"] = new_winners
            
        self.save_giveaways()
        
        # Update message
        try:
            channel = self.bot.get_channel(giveaway["channel_id"])
            if channel:
                message = await channel.fetch_message(int(message_id))
                embed = message.embeds[0]
                embed.description = f"**Prize**: {giveaway['prize']}\n**Hosted by**: <@{giveaway['host_id']}>"
                embed.set_field_at(1, name="Winners", value=str(giveaway["winners"]), inline=True)
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
        # For reroll, we need to know the entrants even after it ends.
        # Currently, my 'end_giveaway' removes it from self.giveaways.
        # I should probably keep it but mark it as ended, OR rely on the message reactions if I wasn't using buttons.
        # Since I'm using buttons and storing entrants, deleting it makes reroll hard.
        # Let's just say "Giveaway not found" if it's deleted, or we implement a "ended_giveaways" list.
        # For simplicity, I will NOT support reroll for deleted giveaways in this iteration unless I change the architecture.
        # Actually, I'll check if it exists.
        
        if message_id not in self.giveaways:
             await interaction.response.send_message("❌ Giveaway data not found (it might have been cleared).", ephemeral=True)
             return

        giveaway = self.giveaways[message_id]
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
        if message_id not in self.giveaways:
            return

        giveaway = self.giveaways[message_id]
        
        # If already ended, don't end again (unless forced? No, just return)
        if giveaway.get("ended", False):
            return

        channel = self.bot.get_channel(giveaway["channel_id"])
        
        if not channel:
            # Channel deleted? Mark as ended so we don't retry
            giveaway["ended"] = True
            self.save_giveaways()
            return

        try:
            message = await channel.fetch_message(int(message_id))
        except:
            # Message deleted? Mark as ended
            giveaway["ended"] = True
            self.save_giveaways()
            return

        entrants = giveaway.get("entrants", [])
        winners_count = giveaway["winners"]
        prize = giveaway["prize"]
        host_id = giveaway["host_id"]

        if not entrants:
            await channel.send(f"❌ Giveaway for **{prize}** ended with no entrants.")
            embed = message.embeds[0]
            embed.title = "🎉 GIVEAWAY ENDED 🎉"
            embed.color = discord.Color.dark_gray()
            embed.set_footer(text="Ended")
            await message.edit(embed=embed, view=None)
        else:
            # Pick winners
            if len(entrants) <= winners_count:
                winners = entrants
            else:
                winners = random.sample(entrants, winners_count)
            
            winner_mentions = ", ".join([f"<@{w}>" for w in winners])
            
            await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**!")
            
            embed = message.embeds[0]
            embed.title = "🎉 GIVEAWAY ENDED 🎉"
            embed.color = discord.Color.green()
            embed.add_field(name="Winners", value=winner_mentions, inline=False)
            embed.set_footer(text="Ended")
            await message.edit(embed=embed, view=None)

        # Mark as ended instead of deleting
        giveaway["ended"] = True
        self.save_giveaways()

    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        now = datetime.datetime.now().timestamp()
        # Create a list to avoid modifying dictionary during iteration
        # We only want to check active giveaways
        active_giveaways = [
            mid for mid, data in self.giveaways.items() 
            if not data.get("ended", False) and data["end_time"] <= now
        ]
        
        for message_id in active_giveaways:
            await self.end_giveaway(message_id)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()


    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in giveaway command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
