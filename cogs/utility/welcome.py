"""
Welcome and Goodbye system - Send messages when members join or leave
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
import re
import logging

logger = logging.getLogger('DiscordBot.Welcome')


class Welcome(commands.Cog):
    """Welcome and goodbye message system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config_file = Path('data/welcome_goodbye.json')
        self.config_file.parent.mkdir(exist_ok=True)
        self.pending_messages = {}  # Store pending message setups
    
    def load_config(self):
        """Load welcome/goodbye configuration"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    
    def save_config(self, data):
        """Save welcome/goodbye configuration"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def replace_tags(self, message: str, member: discord.Member, guild: discord.Guild) -> str:
        """Replace tags in message with actual values"""
        # Replace {user} with display name
        message = message.replace("{user}", member.display_name)
        
        # Replace {user-mention} with mention
        message = message.replace("{user-mention}", member.mention)
        
        # Replace {channel-ID} with channel mention
        # Find all {channel-123456789} patterns
        channel_pattern = r'\{channel-(\d+)\}'
        matches = re.finditer(channel_pattern, message)
        
        for match in matches:
            channel_id = int(match.group(1))
            channel = guild.get_channel(channel_id)
            if channel:
                message = message.replace(match.group(0), channel.mention)
            else:
                # If channel not found, leave the tag as is
                pass
        
        return message
    
    @app_commands.command(name="setwelcome", description="Set welcome message for new members")
    @app_commands.describe(channel="Channel to send welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set welcome message"""
        # Store pending setup
        self.pending_messages[interaction.user.id] = {
            'type': 'welcome',
            'channel_id': channel.id,
            'guild_id': interaction.guild.id
        }
        
        embed = discord.Embed(
            title="📝 Welcome Message Setup",
            description=f"Please send the welcome message you want to use in this channel.\n\n"
                       f"**Available tags:**\n"
                       f"`{{user}}` - User's display name\n"
                       f"`{{user-mention}}` - Mention the user\n"
                       f"`{{channel-ID}}` - Link to a channel (replace ID with actual channel ID)\n\n"
                       f"**Example:** Welcome {{user-mention}} to the server! Check out {{channel-123456789}}",
            color=discord.Color.green()
        )
        embed.add_field(name="Target Channel", value=channel.mention, inline=False)
        embed.set_footer(text="You have 60 seconds to send your message")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="setgoodbye", description="Set goodbye message for leaving members")
    @app_commands.describe(channel="Channel to send goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setgoodbye(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set goodbye message"""
        # Store pending setup
        self.pending_messages[interaction.user.id] = {
            'type': 'goodbye',
            'channel_id': channel.id,
            'guild_id': interaction.guild.id
        }
        
        embed = discord.Embed(
            title="📝 Goodbye Message Setup",
            description=f"Please send the goodbye message you want to use in this channel.\n\n"
                       f"**Available tags:**\n"
                       f"`{{user}}` - User's display name\n"
                       f"`{{user-mention}}` - Mention the user\n"
                       f"`{{channel-ID}}` - Link to a channel (replace ID with actual channel ID)\n\n"
                       f"**Example:** Goodbye {{user}}! We'll miss you.",
            color=discord.Color.red()
        )
        embed.add_field(name="Target Channel", value=channel.mention, inline=False)
        embed.set_footer(text="You have 60 seconds to send your message")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for welcome/goodbye message setup"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if user has pending setup
        if message.author.id not in self.pending_messages:
            return
        
        pending = self.pending_messages[message.author.id]
        
        # Verify it's the same guild
        if message.guild.id != pending['guild_id']:
            return
        
        # Get the message content
        welcome_message = message.content
        
        # Delete the user's message for cleanliness
        try:
            await message.delete()
        except:
            pass
        
        # Save configuration
        config = self.load_config()
        guild_id_str = str(pending['guild_id'])
        
        if guild_id_str not in config:
            config[guild_id_str] = {}
        
        config[guild_id_str][pending['type']] = {
            'channel_id': pending['channel_id'],
            'message': welcome_message
        }
        
        self.save_config(config)
        
        # Remove pending setup
        del self.pending_messages[message.author.id]
        
        # Send confirmation
        channel = message.guild.get_channel(pending['channel_id'])
        embed = discord.Embed(
            title=f"✅ {pending['type'].capitalize()} Message Set!",
            description=f"**Channel:** {channel.mention}\n**Message:** {welcome_message}",
            color=discord.Color.green()
        )
        
        await message.channel.send(embed=embed, delete_after=10)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send welcome message when member joins"""
        config = self.load_config()
        guild_id_str = str(member.guild.id)
        
        if guild_id_str not in config:
            return
        
        if 'welcome' not in config[guild_id_str]:
            return
        
        welcome_config = config[guild_id_str]['welcome']
        channel = member.guild.get_channel(welcome_config['channel_id'])
        
        if not channel:
            return
        
        # Replace tags in message
        message = self.replace_tags(welcome_config['message'], member, member.guild)
        
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass  # Bot doesn't have permission to send messages
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send goodbye message when member leaves"""
        config = self.load_config()
        guild_id_str = str(member.guild.id)
        
        if guild_id_str not in config:
            return
        
        if 'goodbye' not in config[guild_id_str]:
            return
        
        goodbye_config = config[guild_id_str]['goodbye']
        channel = member.guild.get_channel(goodbye_config['channel_id'])
        
        if not channel:
            return
        
        # Replace tags in message
        message = self.replace_tags(goodbye_config['message'], member, member.guild)
        
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass  # Bot doesn't have permission to send messages
    
    @setwelcome.error
    async def setwelcome_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Manage Server permission to set welcome messages!", ephemeral=True)
    
    @setgoodbye.error
    async def setgoodbye_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Manage Server permission to set goodbye messages!", ephemeral=True)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in welcome/goodbye command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
