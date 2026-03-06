import discord
from discord.ext import commands
import logging
from discord import app_commands

logger = logging.getLogger('DiscordBot.Kick')


class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for the kick"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a member from the server"""
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
                return
            
            if member.top_role >= interaction.user.top_role:
                await interaction.response.send_message("❌ You cannot kick someone with a higher or equal role!", ephemeral=True)
                return
            
            if member.top_role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot kick someone with a higher or equal role than me!", ephemeral=True)
                return
            
            await member.kick(reason=f"{reason} | Kicked by {interaction.user}")
            
            embed = discord.Embed(
                title="👢 Member Kicked",
                description=f"{member.mention} has been kicked from the server.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error kicking member: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @kick.error
    async def kick_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to kick members!", ephemeral=True)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in kick command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Kick(bot))