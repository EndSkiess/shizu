
import discord
from discord.ext import commands
from discord import app_commands
import json
import os

SUPERUSERS_FILE = "data/superusers.json"

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.client.application and interaction.client.application.owner:
            return interaction.user.id == interaction.client.application.owner.id
        return False

    def load_superusers(self):
        if not os.path.exists(SUPERUSERS_FILE):
            return []
        try:
            with open(SUPERUSERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []

    def save_superusers(self, users):
        with open(SUPERUSERS_FILE, 'w') as f:
            json.dump(users, f)

    group = app_commands.Group(name="admin", description="Bot Administration")

    @group.command(name="adduser", description="Add a user to the superuser whitelist")
    @app_commands.describe(user_id="The ID of the user to adding")
    async def add_user(self, interaction: discord.Interaction, user_id: str):
        # Only Owner can add superusers
        if not self.is_owner(interaction):
            await interaction.response.send_message("❌ Only the Bot Owner can use this command.", ephemeral=True)
            return

        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid User ID.", ephemeral=True)
            return

        users = self.load_superusers()
        if uid not in users:
            users.append(uid)
            self.save_superusers(users)
            await interaction.response.send_message(f"✅ Added user `{uid}` to superusers.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ User `{uid}` is already a superuser.", ephemeral=True)

    @group.command(name="removeuser", description="Remove a user from the superuser whitelist")
    @app_commands.describe(user_id="The ID of the user to remove")
    async def remove_user(self, interaction: discord.Interaction, user_id: str):
         # Only Owner can remove superusers
        if not self.is_owner(interaction):
            await interaction.response.send_message("❌ Only the Bot Owner can use this command.", ephemeral=True)
            return
            
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid User ID.", ephemeral=True)
            return

        users = self.load_superusers()
        if uid in users:
            users.remove(uid)
            self.save_superusers(users)
            await interaction.response.send_message(f"✅ Removed user `{uid}` from superusers.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ User `{uid}` is not a superuser.", ephemeral=True)

    @group.command(name="listusers", description="List all superusers")
    async def list_users(self, interaction: discord.Interaction):
        # Only Owner can list superusers (security)
        if not self.is_owner(interaction):
             await interaction.response.send_message("❌ Only the Bot Owner can use this command.", ephemeral=True)
             return

        users = self.load_superusers()
        if not users:
            await interaction.response.send_message("No superusers configured.", ephemeral=True)
        else:
            txt = "\n".join([f"- <@{uid}> ({uid})" for uid in users])
            embed = discord.Embed(title="👑 Superusers", description=txt, color=discord.Color.gold())
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
