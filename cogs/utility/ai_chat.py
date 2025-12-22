"""
AI Chat Cog - Conversational AI using Ollama
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from .ai_chat_utils import (
    get_ollama_response,
    start_conversation,
    add_message,
    get_conversation_history,
    clear_conversation,
    set_ai_channel,
    remove_ai_channel,
    get_ai_channels,
    is_ai_enabled_channel
)

logger = logging.getLogger('DiscordBot.AIChat')


class AIChat(commands.Cog):
    """AI Chat functionality using Ollama"""
    
    def __init__(self, bot):
        self.bot = bot
        self.bot_user_id = None
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("AI Chat cog loaded")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Store bot user ID when ready"""
        self.bot_user_id = self.bot.user.id
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for mentions and replies to bot messages"""
        # Ignore bot's own messages
        if message.author.bot:
            return
        
        # Ignore messages without content
        if not message.content:
            return
        
        # In DMs, always respond when mentioned or replied to
        in_dm = not message.guild
        
        # In guilds, check if AI is enabled in this channel
        if not in_dm and not await is_ai_enabled_channel(message.guild.id, message.channel.id):
            return
        
        # Check if bot was mentioned (new conversation)
        bot_mentioned = self.bot.user in message.mentions
        
        # Check if message is a reply to the bot (continue conversation)
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                referenced_msg = await message.channel.fetch_message(message.reference.message_id)
                is_reply_to_bot = referenced_msg.author.id == self.bot.user.id
            except:
                pass
        
        # Only respond if mentioned or replying to bot
        if not (bot_mentioned or is_reply_to_bot):
            return
        
        # Get the message content without the mention
        content = message.content
        if bot_mentioned:
            # Remove bot mention from content
            content = content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
        
        if not content:
            content = "Hello!"
        
        try:
            # Show typing indicator
            async with message.channel.typing():
                # If mentioned, start new conversation
                if bot_mentioned:
                    await start_conversation(message.author.id, content)
                    conversation_history = await get_conversation_history(message.author.id)
                else:
                    # Continue existing conversation
                    conversation_history = await get_conversation_history(message.author.id)
                    # Add user message to history
                    await add_message(message.author.id, 'user', content)
                    # Refresh history
                    conversation_history = await get_conversation_history(message.author.id)
                
                # Get AI response
                # Pass guild_id if in guild, None if in DM
                guild_id = message.guild.id if message.guild else None
                result = await get_ollama_response(content, conversation_history, guild_id)
                
                if result['success']:
                    response_text = result['response']
                    emotion = result['emotion']
                    
                    # Add assistant response to history
                    await add_message(message.author.id, 'assistant', response_text, emotion)
                    
                    # Split response if too long (Discord 2000 char limit)
                    if len(response_text) > 2000:
                        chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                        for chunk in chunks:
                            await message.reply(chunk, mention_author=True)
                    else:
                        await message.reply(response_text, mention_author=True)
                else:
                    # Check if it's a connection error (server offline)
                    error_str = str(result['error']).lower()
                    if any(keyword in error_str for keyword in ['cannot connect', 'connection', 'refused', 'unreachable', 'timeout', 'timed out']):
                        # Send casual offline message
                        offline_msg = "welp looks like my owner is off to bed 💀\nIf u do want it Please contat the owner Miss kitkatorangejuice or the Bot dev Skies Thank you"
                        await message.reply(offline_msg, mention_author=True)
                        logger.warning(f"AI server offline: {result['error']}")
                    else:
                        # Other errors - show technical error
                        error_msg = f"❌ Sorry, I encountered an error: {result['error']}"
                        await message.reply(error_msg, mention_author=True)
                        logger.error(f"AI Chat error: {result['error']}")
        
        except Exception as e:
            logger.error(f"Error in AI chat: {e}", exc_info=True)
            try:
                await message.reply("❌ Oops! Something went wrong while processing your message.", mention_author=True)
            except:
                pass
    
    @app_commands.command(name="setaichannel", description="Set the channel where AI chat is enabled")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_ai_channel_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        """Set the AI chat channel"""
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        try:
            # Check if already enabled
            enabled_channels = await get_ai_channels(interaction.guild.id)
            
            if target_channel.id in enabled_channels:
                await interaction.response.send_message(
                    f"✅ AI chat is already enabled in {target_channel.mention}",
                    ephemeral=True
                )
                return
            
            # Enable AI in the channel
            await set_ai_channel(interaction.guild.id, target_channel.id)
            
            await interaction.response.send_message(
                f"✅ AI chat enabled in {target_channel.mention}!\n"
                f"💡 Mention me or reply to my messages to start chatting!",
                ephemeral=True
            )
            
            logger.info(f"AI chat enabled in channel {target_channel.id} (Guild: {interaction.guild.id})")
        
        except Exception as e:
            logger.error(f"Error setting AI channel: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred while setting the AI channel.",
                ephemeral=True
            )
    
    @app_commands.command(name="removeaichannel", description="Remove AI chat from a channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_ai_channel_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        """Remove AI chat from a channel"""
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        try:
            # Remove AI from the channel
            removed = await remove_ai_channel(interaction.guild.id, target_channel.id)
            
            if removed:
                await interaction.response.send_message(
                    f"✅ AI chat disabled in {target_channel.mention}",
                    ephemeral=True
                )
                logger.info(f"AI chat disabled in channel {target_channel.id} (Guild: {interaction.guild.id})")
            else:
                await interaction.response.send_message(
                    f"ℹ️ AI chat was not enabled in {target_channel.mention}",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"Error removing AI channel: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred while removing the AI channel.",
                ephemeral=True
            )
    
    @app_commands.command(name="aichannels", description="List all AI-enabled channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_ai_channels_command(self, interaction: discord.Interaction):
        """List all AI-enabled channels"""
        try:
            enabled_channels = await get_ai_channels(interaction.guild.id)
            
            if not enabled_channels:
                await interaction.response.send_message(
                    "ℹ️ No AI chat channels configured. Use `/setaichannel` to enable AI chat in a channel.",
                    ephemeral=True
                )
                return
            
            # Build channel list
            channel_mentions = []
            for channel_id in enabled_channels:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"Unknown Channel ({channel_id})")
            
            channels_text = "\n".join(f"• {mention}" for mention in channel_mentions)
            
            await interaction.response.send_message(
                f"🤖 **AI Chat Enabled Channels:**\n{channels_text}",
                ephemeral=True
            )
        
        except Exception as e:
            logger.error(f"Error listing AI channels: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred while listing AI channels.",
                ephemeral=True
            )
    
    @app_commands.command(name="testai", description="Test the Ollama API connection (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_ai_command(self, interaction: discord.Interaction):
        """Test AI connection"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from .ai_chat_utils import OLLAMA_API, OLLAMA_MODEL, get_ollama_response
            
            # Test simple request
            result = await get_ollama_response("Say 'Hello, I'm working!' in one sentence.")
            
            if result['success']:
                await interaction.followup.send(
                    f"✅ **AI Connection Successful!**\n"
                    f"📡 API: `{OLLAMA_API}`\n"
                    f"🤖 Model: `{OLLAMA_MODEL}`\n"
                    f"💬 Response: {result['response'][:200]}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **AI Connection Failed**\n"
                    f"📡 API: `{OLLAMA_API}`\n"
                    f"🤖 Model: `{OLLAMA_MODEL}`\n"
                    f"⚠️ Error: {result['error']}",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ **Test Failed**\n"
                f"Error: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="clearmychat", description="Clear your conversation history with the AI")
    async def clear_my_chat_command(self, interaction: discord.Interaction):
        """Clear user's conversation history"""
        try:
            await clear_conversation(interaction.user.id)
            await interaction.response.send_message(
                "✅ Your conversation history has been cleared! Mention me to start a fresh conversation.",
                ephemeral=True
            )
            logger.info(f"Cleared conversation history for user {interaction.user.id}")
        
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred while clearing your conversation.",
                ephemeral=True
            )



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in ai_chat command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(AIChat(bot))
