import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import logging
import asyncio

logger = logging.getLogger('DiscordBot.TempBan')
from datetime import datetime, timedelta
from pathlib import Path


class TempBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tempbans_file = Path('data/tempbans.json')
        self.tempbans_file.parent.mkdir(exist_ok=True)
        self.tempbans = self.load_tempbans()
        self.check_tempbans.start()

    def load_tempbans(self):
        """Load tempbans from JSON file"""
        if self.tempbans_file.exists():
            with open(self.tempbans_file, 'r') as f:
                return json.load(f)
        return {}

    def save_tempbans(self):
        """Save tempbans to JSON file"""
        with open(self.tempbans_file, 'w') as f:
            json.dump(self.tempbans, f, indent=4)

    @app_commands.command(name="tempban", description="Temporarily ban a user")
    @app_commands.describe(
        member="The member to temporarily ban",
        duration="Duration in hours",
        reason="Reason for the ban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def tempban(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        """Temporarily ban a member"""
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message("❌ You cannot tempban yourself!", ephemeral=True)
                return
            
            if member.top_role >= interaction.user.top_role:
                await interaction.response.send_message("❌ You cannot tempban someone with a higher or equal role!", ephemeral=True)
                return
            
            if member.top_role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot tempban someone with a higher or equal role than me!", ephemeral=True)
                return
            
            if duration <= 0:
                await interaction.response.send_message("❌ Duration must be greater than 0!", ephemeral=True)
                return
            
            unban_time = (datetime.utcnow() + timedelta(hours=duration)).isoformat()
            
            await member.ban(reason=f"[TEMPBAN] {reason} | Banned by {interaction.user}")
            
            key = f"{interaction.guild.id}_{member.id}"
            self.tempbans[key] = {
                'guild_id': interaction.guild.id,
                'user_id': member.id,
                'unban_time': unban_time,
                'reason': reason,
                'moderator': str(interaction.user)
            }
            self.save_tempbans()
            
            embed = discord.Embed(
                title="⏱️ Member Temporarily Banned",
                description=f"{member.mention} has been temporarily banned.",
                color=discord.Color.red()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=f"{duration} hours", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error tempbanning member: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_tempbans(self):
        """Check for expired tempbans and unban users"""
        now = datetime.utcnow()
        to_remove = []
        
        for key, data in self.tempbans.items():
            unban_time = datetime.fromisoformat(data['unban_time'])
            
            if now >= unban_time:
                guild = self.bot.get_guild(data['guild_id'])
                if guild:
                    try:
                        user = await self.bot.fetch_user(data['user_id'])
                        await guild.unban(user, reason="Tempban expired")
                        to_remove.append(key)
                    except Exception as e:
                        logger.error(f"Failed to unban {data['user_id']}: {e}", exc_info=True)
        
        for key in to_remove:
            del self.tempbans[key]
        
        if to_remove:
            self.save_tempbans()

    @check_tempbans.before_loop
    async def before_check_tempbans(self):
        await self.bot.wait_until_ready()

    @tempban.error
    async def tempban_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)

    def cog_unload(self):
        self.check_tempbans.cancel()



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in tempban command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TempBan(bot))