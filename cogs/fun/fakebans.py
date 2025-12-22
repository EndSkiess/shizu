import discord
from discord.ext import commands
from discord import app_commands
import random


class FakeBans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fake_reasons = [
            "Being too awesome",
            "Winning too many arguments",
            "Excessive meme posting",
            "Making the mods jealous",
            "Being suspiciously cool",
            "Violations of Rule 69: Having too much swag",
            "Illegal levels of charisma",
            "Possession of forbidden dad jokes",
            "Unauthorized use of emojis",
            "Suspected time traveler from the future"
        ]

    @app_commands.command(name="fakeban", description="Pretend to ban a user (for fun)")
    @app_commands.describe(user="The user to fake ban")
    async def fakeban(self, interaction: discord.Interaction, user: discord.Member):
        """Send a fake ban message"""
        reason = random.choice(self.fake_reasons)
        
        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"{user.mention} has been banned from the server!",
            color=discord.Color.red()
        )
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="JK! This is a fake ban. They're still here.")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(FakeBans(bot))