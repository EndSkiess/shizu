import discord
from discord.ext import commands
import logging
from datetime import timedelta
from discord import app_commands

logger = logging.getLogger('DiscordBot.Mute')


class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mute", description="Mute a user (timeout)")
    @app_commands.describe(
        member="The member to mute",
        duration="Duration in minutes",
        reason="Reason for the mute"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        """Mute a member using Discord's timeout feature"""
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message("❌ You cannot mute yourself!", ephemeral=True)
                return
            
            if member.top_role >= interaction.user.top_role:
                await interaction.response.send_message("❌ You cannot mute someone with a higher or equal role!", ephemeral=True)
                return
            
            if member.top_role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot mute someone with a higher or equal role than me!", ephemeral=True)
                return
            
            if duration <= 0:
                await interaction.response.send_message("❌ Duration must be greater than 0!", ephemeral=True)
                return
            
            if duration > 40320:  # 28 days in minutes (Discord's max timeout)
                await interaction.response.send_message("❌ Duration cannot exceed 28 days (40320 minutes)!", ephemeral=True)
                return
            
            # Check if member is already muted
            if member.is_timed_out():
                await interaction.response.send_message(f"❌ {member.mention} is already muted!", ephemeral=True)
                return
            
            # Mute the member
            timeout_duration = timedelta(minutes=duration)
            await member.timeout(timeout_duration, reason=f"{reason} | Muted by {interaction.user}")
            
            # Calculate hours and minutes for display
            hours = duration // 60
            minutes = duration % 60
            duration_str = ""
            if hours > 0:
                duration_str += f"{hours}h "
            if minutes > 0 or hours == 0:
                duration_str += f"{minutes}m"
            
            embed = discord.Embed(
                title="🔇 Member Muted",
                description=f"{member.mention} has been muted.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=duration_str.strip(), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to mute this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error muting member: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a user")
    @app_commands.describe(
        member="The member to unmute"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        """Unmute a member by removing their timeout"""
        try:
            if not member.is_timed_out():
                await interaction.response.send_message(f"❌ {member.mention} is not muted!", ephemeral=True)
                return
            
            # Unmute the member
            await member.timeout(None, reason=f"Unmuted by {interaction.user}")
            
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                description=f"{member.mention} has been unmuted.",
                color=discord.Color.green()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unmute this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error unmuting member: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @mute.error
    async def mute_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to mute members!", ephemeral=True)

    @unmute.error
    async def unmute_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to unmute members!", ephemeral=True)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            if interaction.response.is_done():
                await interaction.followup.send(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
            else:
                await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                 await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in mute command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Mute(bot))
