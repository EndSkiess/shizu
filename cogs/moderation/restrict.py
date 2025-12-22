import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from pathlib import Path

logger = logging.getLogger('DiscordBot.Restrict')


class Restrict(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_restrictions_file = Path('data/chat_restrictions.json')
        self.chat_restrictions_file.parent.mkdir(exist_ok=True)
        self.chat_restrictions = self.load_restrictions()

    def load_restrictions(self):
        """Load chat restrictions from JSON file"""
        if self.chat_restrictions_file.exists():
            with open(self.chat_restrictions_file, 'r') as f:
                return json.load(f)
        return {}

    def save_restrictions(self):
        """Save chat restrictions to JSON file"""
        with open(self.chat_restrictions_file, 'w') as f:
            json.dump(self.chat_restrictions, f, indent=4)

    async def get_or_create_no_bots_role(self, guild: discord.Guild) -> discord.Role:
        """Get or create the 'No Bots' role with proper permissions"""
        role_name = "No Bots"
        
        # Check if role already exists
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            return existing_role
        
        # Create the role with permissions that deny bot usage
        try:
            role = await guild.create_role(
                name=role_name,
                color=discord.Color.dark_gray(),
                reason="Auto-created for bot restrictions",
                permissions=discord.Permissions(use_application_commands=False)
            )
            return role
        except discord.Forbidden:
            raise Exception("Bot lacks permission to create roles!")
        except Exception as e:
            logger.error(f"Error creating role: {e}", exc_info=True)
            raise e

    @app_commands.command(name="restrict", description="Restrict a user from all bots or prevent two users from talking")
    @app_commands.describe(
        user1="First user (or the only user to restrict from all bots)",
        user2="Second user (optional - if provided, restricts chat between both users)",
        reason="Reason for the restriction"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def restrict(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None, reason: str = "No reason provided"):
        """Restrict a user from all bots or restrict two users from talking to each other"""
        try:
            # Case 1: Restrict user from ALL bots (only user1 provided)
            if user2 is None:
                if user1.id == interaction.user.id:
                    await interaction.response.send_message("❌ You cannot restrict yourself!", ephemeral=True)
                    return
                
                if user1.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You cannot restrict administrators!", ephemeral=True)
                    return
                
                # Get or create the "No Bots" role
                try:
                    no_bots_role = await self.get_or_create_no_bots_role(interaction.guild)
                except Exception as e:
                    logger.error(f"Error getting/creating role: {e}", exc_info=True)
                    await interaction.response.send_message("❌ An error occurred while setting up restrictions.", ephemeral=True)
                    return
                
                # Check if user already has the role
                if no_bots_role in user1.roles:
                    await interaction.response.send_message(f"❌ {user1.mention} is already restricted from using bots!", ephemeral=True)
                    return
                
                # Assign the role
                await user1.add_roles(no_bots_role, reason=f"{reason} | Restricted by {interaction.user}")
                
                embed = discord.Embed(
                    title="🚫 User Restricted from All Bots",
                    description=f"{user1.mention} has been restricted from using all bots in this server.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Role Assigned", value=no_bots_role.mention, inline=False)
                embed.set_thumbnail(url=user1.display_avatar.url)
                
                await interaction.response.send_message(embed=embed)
            
            # Case 2: Restrict chat between two users (both user1 and user2 provided)
            else:
                if user1.id == user2.id:
                    await interaction.response.send_message("❌ You cannot restrict a user from themselves!", ephemeral=True)
                    return
                
                guild_id = str(interaction.guild.id)
                if guild_id not in self.chat_restrictions:
                    self.chat_restrictions[guild_id] = []
                
                pair = sorted([user1.id, user2.id])
                pair_key = f"{pair[0]}_{pair[1]}"
                
                for restriction in self.chat_restrictions[guild_id]:
                    if restriction['pair'] == pair_key:
                        await interaction.response.send_message("❌ These users are already restricted from each other!", ephemeral=True)
                        return
                
                self.chat_restrictions[guild_id].append({
                    'pair': pair_key,
                    'user1': user1.id,
                    'user2': user2.id,
                    'reason': reason,
                    'moderator': interaction.user.id
                })
                self.save_restrictions()
                
                embed = discord.Embed(
                    title="🚫 Users Restricted from Chatting",
                    description=f"{user1.mention} and {user2.mention} are now restricted from talking to each other.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                
                await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage roles for this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error restricting user: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Check if message violates chat restrictions"""
        if message.author.bot or not message.guild:
            return
        
        guild_id = str(message.guild.id)
        if guild_id not in self.chat_restrictions:
            return
        
        # Check if message mentions any restricted users
        for restriction in self.chat_restrictions[guild_id]:
            user1_id = restriction['user1']
            user2_id = restriction['user2']
            
            if message.author.id == user1_id:
                # Check if mentioning user2
                if any(mention.id == user2_id for mention in message.mentions):
                    await message.delete()
                    await message.channel.send(
                        f"❌ {message.author.mention}, you are restricted from interacting with that user!",
                        delete_after=5
                    )
                    return
            
            elif message.author.id == user2_id:
                # Check if mentioning user1
                if any(mention.id == user1_id for mention in message.mentions):
                    await message.delete()
                    await message.channel.send(
                        f"❌ {message.author.mention}, you are restricted from interacting with that user!",
                        delete_after=5
                    )
                    return

    @app_commands.command(name="unrestrict", description="Remove restriction from user(s)")
    @app_commands.describe(
        user1="First user (or the only user to unrestrict from bots)",
        user2="Second user (optional - if provided, removes chat restriction between both users)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unrestrict(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
        """Remove restriction from user(s)"""
        try:
            # Case 1: Remove bot restriction (only user1 provided)
            if user2 is None:
                role_name = "No Bots"
                no_bots_role = discord.utils.get(interaction.guild.roles, name=role_name)
                
                if not no_bots_role:
                    await interaction.response.send_message("❌ No 'No Bots' role found in this server!", ephemeral=True)
                    return
                
                if no_bots_role not in user1.roles:
                    await interaction.response.send_message(f"❌ {user1.mention} is not restricted from using bots!", ephemeral=True)
                    return
                
                # Remove the role
                await user1.remove_roles(no_bots_role, reason=f"Unrestricted by {interaction.user}")
                
                embed = discord.Embed(
                    title="✅ Bot Restriction Removed",
                    description=f"{user1.mention} can now use bots again.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
                embed.set_thumbnail(url=user1.display_avatar.url)
                
                await interaction.response.send_message(embed=embed)
            
            # Case 2: Remove chat restriction (both users provided)
            else:
                if user1.id == user2.id:
                    await interaction.response.send_message("❌ Invalid user pair!", ephemeral=True)
                    return
                
                guild_id = str(interaction.guild.id)
                if guild_id not in self.chat_restrictions:
                    await interaction.response.send_message("❌ No chat restrictions found for this server!", ephemeral=True)
                    return
                
                pair = sorted([user1.id, user2.id])
                pair_key = f"{pair[0]}_{pair[1]}"
                
                found = False
                for i, restriction in enumerate(self.chat_restrictions[guild_id]):
                    if restriction['pair'] == pair_key:
                        self.chat_restrictions[guild_id].pop(i)
                        found = True
                        break
                
                if not found:
                    await interaction.response.send_message("❌ These users are not restricted from each other!", ephemeral=True)
                    return
                
                self.save_restrictions()
                
                embed = discord.Embed(
                    title="✅ Chat Restriction Removed",
                    description=f"{user1.mention} and {user2.mention} can now interact with each other.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
                
                await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage roles for this user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error unrestricting user: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @app_commands.command(name="restrictions", description="View all restrictions")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def restrictions(self, interaction: discord.Interaction):
        """View all restrictions in the server"""
        try:
            guild_id = str(interaction.guild.id)
            
            # Check for "No Bots" role members
            role_name = "No Bots"
            no_bots_role = discord.utils.get(interaction.guild.roles, name=role_name)
            has_bot_restrictions = no_bots_role and len(no_bots_role.members) > 0
            
            # Check chat restrictions
            has_chat_restrictions = guild_id in self.chat_restrictions and self.chat_restrictions[guild_id]
            
            if not has_bot_restrictions and not has_chat_restrictions:
                await interaction.response.send_message("✅ No restrictions are currently active in this server!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🚫 Active Restrictions",
                description="All active restrictions in this server:",
                color=discord.Color.red()
            )
            
            # Add bot restrictions
            if has_bot_restrictions:
                bot_restrict_text = ""
                for member in no_bots_role.members:
                    bot_restrict_text += f"• {member.mention}\n"
                
                embed.add_field(
                    name="🤖 Bot Restrictions (All Bots)",
                    value=bot_restrict_text or "None",
                    inline=False
                )
            
            # Add chat restrictions
            if has_chat_restrictions:
                chat_restrict_text = ""
                for restriction in self.chat_restrictions[guild_id]:
                    user1 = interaction.guild.get_member(restriction['user1'])
                    user2 = interaction.guild.get_member(restriction['user2'])
                    user1_mention = user1.mention if user1 else f"<@{restriction['user1']}>"
                    user2_mention = user2.mention if user2 else f"<@{restriction['user2']}>"
                    chat_restrict_text += f"• {user1_mention} ↔️ {user2_mention} - {restriction['reason']}\n"
                
                embed.add_field(
                    name="💬 Chat Restrictions",
                    value=chat_restrict_text or "None",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing restrictions: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

    @restrict.error
    async def restrict_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to restrict users!", ephemeral=True)

    @unrestrict.error
    async def unrestrict_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to unrestrict users!", ephemeral=True)

    @restrictions.error
    async def restrictions_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to view restrictions!", ephemeral=True)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in restrict command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Restrict(bot))