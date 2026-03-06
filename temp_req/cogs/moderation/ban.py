import discord
from discord.ext import commands
import logging
from discord import app_commands

logger = logging.getLogger('DiscordBot.Ban')


class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Ban a member from the server"""
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
                return
            
            if member.top_role >= interaction.user.top_role:
                await interaction.response.send_message("❌ You cannot ban someone with a higher or equal role!", ephemeral=True)
                return
            
            if member.top_role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot ban someone with a higher or equal role than me!", ephemeral=True)
                return
            
            await member.ban(reason=f"{reason} | Banned by {interaction.user}")
            
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"{member.mention} has been banned from the server.",
                color=discord.Color.red()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error banning member: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @ban.error
    async def ban_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in ban command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Ban(bot))