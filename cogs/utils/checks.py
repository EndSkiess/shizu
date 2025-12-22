
import discord
from discord import app_commands
import json
import os

SUPERUSERS_FILE = "data/superusers.json"

def is_superuser(interaction: discord.Interaction) -> bool:
    """Check if user is Bot Owner or in Superuser whitelist"""
    # 1. Check Owner
    if interaction.client.application and interaction.client.application.owner:
        if interaction.user.id == interaction.client.application.owner.id:
            return True

    # 2. Check Whitelist
    if os.path.exists(SUPERUSERS_FILE):
        try:
            with open(SUPERUSERS_FILE, 'r') as f:
                mod_ids = json.load(f)
                if interaction.user.id in mod_ids:
                    return True
        except:
            pass
            
    return False

def has_permissions(**perms):
    """
    Custom decorator replacing app_commands.checks.has_permissions.
    Allows Superusers (Owner + Whitelist) to bypass permissions.
    """
    def predicate(interaction: discord.Interaction) -> bool:
        # Check Superuser content
        if is_superuser(interaction):
            return True
            
        # Standard Check
        permissions = interaction.permissions
        missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

        if not missing:
            return True

        raise app_commands.MissingPermissions(missing)

    return app_commands.check(predicate)
