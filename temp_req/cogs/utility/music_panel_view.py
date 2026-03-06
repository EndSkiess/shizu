"""
Music Panel View - Interactive music control panel with buttons
"""
import discord
from discord import ui
from discord.ext import commands
import asyncio
import yt_dlp



class AddSongModal(ui.Modal, title="Add Song to Queue"):
    """Modal for adding songs to the queue"""
    
    song_input = ui.TextInput(
        label="Song Name or URL",
        placeholder="Enter a song name or paste a YouTube/Spotify link...",
        required=True,
        max_length=500,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, music_cog, guild, panel_message, panel_view):
        super().__init__()
        self.music_cog = music_cog
        self.guild = guild
        self.panel_message = panel_message
        self.panel_view = panel_view
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle song submission"""
        await interaction.response.defer(ephemeral=True)
        
        query = self.song_input.value.strip()
        
        if not query:
            await interaction.followup.send("❌ Please enter a song name or URL!", ephemeral=True)
            return
        
        queue = self.music_cog.get_queue(self.guild.id)
        
        # Check if it's a Spotify URL
        if 'spotify.com' in query:
            if not self.music_cog.spotify:
                await interaction.followup.send("❌ Spotify integration not configured!", ephemeral=True)
                return
            
            tracks = await self.music_cog.get_spotify_tracks(query)
            
            if not tracks:
                await interaction.followup.send("❌ Failed to extract Spotify tracks!", ephemeral=True)
                return
            
            # Add all tracks to queue
            for track_name in tracks:
                queue.add({
                    'url': f"ytsearch:{track_name}",
                    'title': track_name,
                    'requester': interaction.user
                })
            
            await interaction.followup.send(f"✅ Added **{len(tracks)}** tracks to queue!", ephemeral=True)
        
        else:
            # YouTube URL or search query
            if not query.startswith('http'):
                query = f"ytsearch:{query}"
            
            try:
                # Extract info
                ytdl = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
                info = await interaction.client.loop.run_in_executor(
                    None, 
                    lambda: ytdl.extract_info(query, download=False)
                )
                
                if 'entries' in info:
                    info = info['entries'][0]
                
                queue.add({
                    'url': info['webpage_url'],
                    'title': info['title'],
                    'requester': interaction.user
                })
                
                await interaction.followup.send(f"✅ Added to queue: **{info['title']}**", ephemeral=True)
            
            except Exception as e:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
                return
        
        # Start playing if not already playing
        if not self.guild.voice_client or not self.guild.voice_client.is_playing():
            # Create a context-like object
            class FakeContext:
                def __init__(self, guild, channel):
                    self.guild = guild
                    self.voice_client = guild.voice_client
                    self.send = channel.send
            
            if self.guild.voice_client:
                await self.music_cog.play_next(FakeContext(self.guild, interaction.channel))


class MusicControlPanel(ui.View):
    """Interactive music control panel with buttons"""
    
    def __init__(self, bot, ctx, panel_message=None, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.ctx = ctx
        self.music_cog = bot.get_cog('Music')
        self.loop_mode = False  # False = off, True = on
        self.panel_message = panel_message  # Store reference to the panel message
        
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        """Handle errors in view interactions"""
        import logging
        logger = logging.getLogger('DiscordBot.MusicPanel')
        logger.error(f"Error in music panel interaction: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred processing this action.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred processing this action.", ephemeral=True)
        except:
            pass
        
    def get_current_info(self):
        """Get current song information"""
        if not self.music_cog:
            return None
        
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        if queue.current:
            return queue.current
        return None
    
    def create_embed(self):
        """Create the music panel embed"""
        current = self.get_current_info()
        
        embed = discord.Embed(
            title="🎵 MUSIC PANEL",
            color=0x2b2d31  # Dark theme color
        )
        
        if current:
            # Song info
            title = current.get('title', 'Unknown')
            requester = current.get('requester')
            
            # Display actual song title
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{title}**",
                inline=False
            )
            
            embed.add_field(
                name="👤 Requested By",
                value=f"{requester.mention}" if requester else "Unknown",
                inline=True
            )
            
            # Get duration if available
            if self.ctx.guild.voice_client and hasattr(self.ctx.guild.voice_client.source, 'duration'):
                duration = self.ctx.guild.voice_client.source.duration
                if duration:
                    mins, secs = divmod(int(duration), 60)
                    embed.add_field(
                        name="⏱️ Music Duration",
                        value=f"{mins}m {secs}s",
                        inline=True
                    )
            
            # Get author/artist from video data if available
            author = "Unknown"
            if self.ctx.guild.voice_client and hasattr(self.ctx.guild.voice_client.source, 'data'):
                data = self.ctx.guild.voice_client.source.data
                # Try to get uploader/channel name
                author = data.get('uploader') or data.get('channel') or data.get('artist') or "Unknown"
            
            embed.add_field(
                name="🎤 Music Author",
                value=author,
                inline=True
            )
        else:
            embed.description = "No music currently playing"
        
        # Add status indicators
        status_text = []
        if self.loop_mode:
            status_text.append("🔁 Loop: ON")
        # Check AutoPlay from Music cog
        if self.music_cog and self.music_cog.autoplay_enabled.get(self.ctx.guild.id, False):
            status_text.append("🎲 AutoPlay: ON")
        
        if status_text:
            embed.set_footer(text=" | ".join(status_text))
        
        return embed
    
    # First row - Playback controls
    @ui.button(label="Down", style=discord.ButtonStyle.secondary, emoji="🔉", row=0)
    async def volume_down(self, interaction: discord.Interaction, button: ui.Button):
        """Decrease volume"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.source:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return
        
        current_volume = interaction.guild.voice_client.source.volume
        new_volume = max(0.0, current_volume - 0.1)
        interaction.guild.voice_client.source.volume = new_volume
        
        await interaction.response.send_message(
            f"🔉 Volume decreased to {int(new_volume * 100)}%",
            ephemeral=True
        )
    
    @ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⏮️", row=0)
    async def previous(self, interaction: discord.Interaction, button: ui.Button):
        """Go to previous song (not implemented in basic queue)"""
        await interaction.response.send_message(
            "⏮️ Previous track feature coming soon!",
            ephemeral=True
        )
    
    @ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: ui.Button):
        """Pause/Resume playback"""
        if not interaction.guild.voice_client:
            await interaction.response.send_message("❌ Not connected to voice!", ephemeral=True)
            return
        
        vc = interaction.guild.voice_client
        
        if vc.is_playing():
            vc.pause()
            button.label = "Resume"
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Paused", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Resumed", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
    
    @ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        """Skip current song"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return
        
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)
        
        # Update embed
        await asyncio.sleep(0.5)
        try:
            await interaction.message.edit(embed=self.create_embed())
        except:
            pass
    
    @ui.button(label="Up", style=discord.ButtonStyle.secondary, emoji="🔊", row=0)
    async def volume_up(self, interaction: discord.Interaction, button: ui.Button):
        """Increase volume"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.source:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return
        
        current_volume = interaction.guild.voice_client.source.volume
        new_volume = min(1.0, current_volume + 0.1)
        interaction.guild.voice_client.source.volume = new_volume
        
        await interaction.response.send_message(
            f"🔊 Volume increased to {int(new_volume * 100)}%",
            ephemeral=True
        )
    
    # Second row - Additional controls
    @ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", row=1)
    async def shuffle(self, interaction: discord.Interaction, button: ui.Button):
        """Shuffle the queue"""
        if not self.music_cog:
            await interaction.response.send_message("❌ Music system not available!", ephemeral=True)
            return
        
        queue = self.music_cog.get_queue(interaction.guild.id)
        
        if queue.is_empty():
            await interaction.response.send_message("❌ Queue is empty!", ephemeral=True)
            return
        
        import random
        random.shuffle(queue.queue)
        
        await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
    
    @ui.button(label="Loop", style=discord.ButtonStyle.secondary, emoji="🔁", row=1)
    async def loop(self, interaction: discord.Interaction, button: ui.Button):
        """Toggle loop mode"""
        self.loop_mode = not self.loop_mode
        
        if self.loop_mode:
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
            await interaction.followup.send("🔁 Loop enabled!", ephemeral=True)
        else:
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
            await interaction.followup.send("🔁 Loop disabled!", ephemeral=True)
    
    @ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=1)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        """Stop playback and clear queue"""
        if not self.music_cog:
            await interaction.response.send_message("❌ Music system not available!", ephemeral=True)
            return
        
        queue = self.music_cog.get_queue(interaction.guild.id)
        queue.clear()
        
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        
        await interaction.response.send_message("⏹️ Stopped and disconnected!", ephemeral=True)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.message.edit(view=self)
    
    @ui.button(label="AutoPlay", style=discord.ButtonStyle.secondary, emoji="🎲", row=1)
    async def autoplay(self, interaction: discord.Interaction, button: ui.Button):
        """Toggle autoplay mode"""
        if not self.music_cog:
            await interaction.response.send_message("❌ Music system not available!", ephemeral=True)
            return
        
        # Check if Spotify is configured
        if not self.music_cog.spotify:
            await interaction.response.send_message(
                "❌ AutoPlay requires Spotify integration! Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env",
                ephemeral=True
            )
            return
        
        # Toggle AutoPlay state in Music cog
        current_state = self.music_cog.autoplay_enabled.get(interaction.guild.id, False)
        new_state = not current_state
        self.music_cog.set_autoplay(interaction.guild.id, new_state)
        
        if new_state:
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
            await interaction.followup.send("🎲 AutoPlay enabled! Similar songs will be added automatically.", ephemeral=True)
        else:
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
            await interaction.followup.send("🎲 AutoPlay disabled!", ephemeral=True)
    
    @ui.button(label="Playlist", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def playlist(self, interaction: discord.Interaction, button: ui.Button):
        """Show current playlist/queue"""
        if not self.music_cog:
            await interaction.response.send_message("❌ Music system not available!", ephemeral=True)
            return
        
        queue = self.music_cog.get_queue(interaction.guild.id)
        
        if queue.current is None and queue.is_empty():
            await interaction.response.send_message("📭 Queue is empty!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📜 Current Playlist",
            color=discord.Color.blue()
        )
        
        if queue.current:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{queue.current['title']}**",
                inline=False
            )
        
        if not queue.is_empty():
            upcoming = "\n".join([f"{i+1}. {track['title']}" for i, track in enumerate(queue.queue[:10])])
            if len(queue.queue) > 10:
                upcoming += f"\n... and {len(queue.queue) - 10} more"
            embed.add_field(
                name=f"⏭️ Up Next ({len(queue.queue)} songs)",
                value=upcoming,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Third row - Add Song button
    @ui.button(label="Add Song", style=discord.ButtonStyle.success, emoji="➕", row=2)
    async def add_song(self, interaction: discord.Interaction, button: ui.Button):
        """Open modal to add a song"""
        if not self.music_cog:
            await interaction.response.send_message("❌ Music system not available!", ephemeral=True)
            return
        
        # Open the modal
        modal = AddSongModal(self.music_cog, interaction.guild, self.panel_message, self)
        await interaction.response.send_modal(modal)


# No setup needed - MusicControlPanel is imported by music.py
