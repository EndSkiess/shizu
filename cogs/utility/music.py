"""
Music bot commands - play, pause, unpause, skip, stop
Supports YouTube URLs, search queries, and Spotify playlists
"""
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import logging
import asyncio
import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from .music_panel_view import MusicControlPanel

load_dotenv()

logger = logging.getLogger('DiscordBot.Music')

# YT-DLP options - Optimized for 192kbps quality
YTDL_OPTIONS = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'extractaudio': True,
    'audioformat': 'opus',  # Better quality than mp3
    'audioquality': 0,  # 0 = best quality
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',  # Optimal for Discord (128kbps limit)
    }],
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000'  # 192kbps bitrate, 48kHz sample rate
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source for YouTube"""
    def __init__(self, source, *, data, volume=1.0):  # Default 100% volume
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        """Create audio source from URL"""
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        
        # Check for FFmpeg in common locations if not in PATH
        ffmpeg_executable = "ffmpeg"
        possible_paths = [
            r"C:\Users\Samuel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
        ]
        
        # If ffmpeg is not in PATH (shutil.which returns None), try to find it
        import shutil
        if not shutil.which("ffmpeg"):
            for path in possible_paths:
                if os.path.exists(path):
                    ffmpeg_executable = path
                    break
        
        return cls(discord.FFmpegPCMAudio(filename, executable=ffmpeg_executable, **FFMPEG_OPTIONS), data=data)


class MusicQueue:
    """Queue system for music tracks"""
    def __init__(self):
        self.queue = []
        self.current = None

    def add(self, track):
        """Add track to queue"""
        self.queue.append(track)

    def next(self):
        """Get next track"""
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        self.current = None
        return None

    def clear(self):
        """Clear queue"""
        self.queue.clear()
        self.current = None

    def is_empty(self):
        """Check if queue is empty"""
        return len(self.queue) == 0


class Music(commands.Cog):
    """Music playback commands"""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Guild ID -> MusicQueue
        self.panel_messages = {}  # Guild ID -> (message, view) for updating
        self.autoplay_enabled = {}  # Guild ID -> True/False for AutoPlay state
        
        # Initialize Spotify client if credentials available
        spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
        spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        if spotify_id and spotify_secret:
            try:
                self.spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                    client_id=spotify_id,
                    client_secret=spotify_secret
                ))
            except Exception as e:
                logger.error(f"Failed to initialize Spotify: {e}")
                self.spotify = None
        else:
            self.spotify = None

    def get_queue(self, guild_id):
        """Get or create queue for guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def play_next(self, ctx):
        """Play next song in queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if queue.is_empty():
            # Check if AutoPlay is enabled
            if self.autoplay_enabled.get(ctx.guild.id, False):
                # Try to get recommendations based on the last played track
                if queue.current and queue.current.get('title'):
                    logger.info(f"AutoPlay: Queue empty, getting recommendations...")
                    recommendations = await self.get_spotify_recommendations(queue.current['title'])
                    
                    if recommendations:
                        # Add recommendations to queue
                        for track_name in recommendations:
                            queue.add({
                                'url': f"ytsearch:{track_name}",
                                'title': track_name,
                                'requester': queue.current.get('requester')  # Use same requester
                            })
                        logger.info(f"AutoPlay: Added {len(recommendations)} recommendations to queue")
                        # Continue to play the next track
                    else:
                        logger.warning("AutoPlay: Failed to get recommendations, disconnecting...")
                        # Queue is empty, disconnect after 5 minutes of inactivity
                        await asyncio.sleep(300)
                        if ctx.voice_client and not ctx.voice_client.is_playing():
                            await ctx.voice_client.disconnect()
                        return
                else:
                    # No previous track to base recommendations on
                    await asyncio.sleep(300)
                    if ctx.voice_client and not ctx.voice_client.is_playing():
                        await ctx.voice_client.disconnect()
                    return
            else:
                # AutoPlay disabled, disconnect after 5 minutes of inactivity
                await asyncio.sleep(300)
                if ctx.voice_client and not ctx.voice_client.is_playing():
                    await ctx.voice_client.disconnect()
                return

        track_info = queue.next()
        
        try:
            player = await YTDLSource.from_url(track_info['url'], loop=self.bot.loop, stream=True)
            
            ctx.voice_client.play(
                player,
                after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
            )

            # Update the panel if it exists
            if ctx.guild.id in self.panel_messages:
                panel_msg, panel_view = self.panel_messages[ctx.guild.id]
                try:
                    updated_embed = panel_view.create_embed()
                    await panel_msg.edit(embed=updated_embed, view=panel_view)
                except discord.errors.NotFound:
                    # Panel message was deleted, remove from tracking
                    del self.panel_messages[ctx.guild.id]
                    logger.info("Panel message deleted, removed from tracking")
                except discord.errors.HTTPException as e:
                    if e.code == 50027 or e.status == 401:
                        # Webhook token expired (after 15 minutes), remove from tracking
                        del self.panel_messages[ctx.guild.id]
                        logger.info("Panel webhook expired, removed from tracking")
                    else:
                        logger.error(f"Failed to update panel: {e}")
                except Exception as e:
                    logger.error(f"Failed to update panel: {e}")
            
        except Exception as e:
            await ctx.send(f"❌ Error playing track: {str(e)}")
            await self.play_next(ctx)

    async def get_spotify_tracks(self, url):
        """Extract tracks from Spotify playlist"""
        if not self.spotify:
            return None

        try:
            if 'playlist' in url:
                results = self.spotify.playlist_tracks(url)
                tracks = []
                for item in results['items']:
                    track = item['track']
                    track_name = f"{track['artists'][0]['name']} - {track['name']}"
                    tracks.append(track_name)
                return tracks
            elif 'track' in url:
                track = self.spotify.track(url)
                track_name = f"{track['artists'][0]['name']} - {track['name']}"
                return [track_name]
        except Exception as e:
            print(f"Spotify error: {e}")
            return None

    async def get_spotify_recommendations(self, track_title):
        """Get Spotify recommendations based on current track"""
        if not self.spotify:
            return None
        
        try:
            # Search for the track on Spotify to get artist info
            search_results = self.spotify.search(q=track_title, type='track', limit=1)
            
            if not search_results['tracks']['items']:
                # Try simplified search if full title doesn't work
                simplified_query = track_title.split('-')[0].strip() if '-' in track_title else track_title
                search_results = self.spotify.search(q=simplified_query, type='track', limit=1)
                
                if not search_results['tracks']['items']:
                    print(f"Could not find track on Spotify: {track_title}")
                    return None
            
            # Get the artist info
            track = search_results['tracks']['items'][0]
            artist_id = track['artists'][0]['id']
            artist_name = track['artists'][0]['name']
            
            print(f"Found track on Spotify: {track['name']} by {artist_name}")
            
            # Get artist's top tracks (more reliable than recommendations API)
            top_tracks = self.spotify.artist_top_tracks(artist_id, country='US')
            
            if not top_tracks or 'tracks' not in top_tracks:
                print("No top tracks found")
                return None
            
            # Extract track names
            recommended_tracks = []
            for rec_track in top_tracks['tracks'][:10]:
                track_name = f"{rec_track['artists'][0]['name']} - {rec_track['name']}"
                recommended_tracks.append(track_name)
            
            print(f"Found {len(recommended_tracks)} top tracks from {artist_name}")
            
            # If we got less than 5 tracks, try to get related artists' tracks too
            if len(recommended_tracks) < 5:
                try:
                    related_artists = self.spotify.artist_related_artists(artist_id)
                    if related_artists and 'artists' in related_artists:
                        for related_artist in related_artists['artists'][:3]:
                            related_top = self.spotify.artist_top_tracks(related_artist['id'], country='US')
                            for track in related_top['tracks'][:3]:
                                track_name = f"{track['artists'][0]['name']} - {track['name']}"
                                if track_name not in recommended_tracks:
                                    recommended_tracks.append(track_name)
                                if len(recommended_tracks) >= 10:
                                    break
                            if len(recommended_tracks) >= 10:
                                break
                        print(f"Added related artists' tracks, total: {len(recommended_tracks)}")
                except Exception as e:
                    print(f"Could not get related artists: {e}")
            
            return recommended_tracks if recommended_tracks else None
            
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def set_autoplay(self, guild_id, enabled):
        """Enable or disable AutoPlay for a guild"""
        self.autoplay_enabled[guild_id] = enabled
        print(f"AutoPlay {'enabled' if enabled else 'disabled'} for guild {guild_id}")

    @app_commands.command(name="music", description="Play music from YouTube or Spotify")
    @app_commands.describe(query="YouTube URL, search query, or Spotify link")
    async def music(self, interaction: discord.Interaction, query: str):
        """Play music and show control panel"""
        await interaction.response.defer()

        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel!", ephemeral=True)
            return

        # Join voice channel if not already
        if not interaction.guild.voice_client:
            try:
                await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to join voice channel: {e}", ephemeral=True)
                return

        queue = self.get_queue(interaction.guild.id)

        # Check if it's a Spotify URL
        if 'spotify.com' in query:
            if not self.spotify:
                await interaction.followup.send("❌ Spotify integration not configured! Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env", ephemeral=True)
                return

            tracks = await self.get_spotify_tracks(query)
            
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

        else:
            # YouTube URL or search query
            if not query.startswith('http'):
                query = f"ytsearch:{query}"

            try:
                # Extract info
                info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
                
                if 'entries' in info:
                    info = info['entries'][0]

                queue.add({
                    'url': info['webpage_url'],
                    'title': info['title'],
                    'requester': interaction.user
                })

            except Exception as e:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
                return

        # Start playing if not already playing
        if not interaction.guild.voice_client.is_playing():
            # Create a context-like object for play_next
            class FakeContext:
                def __init__(self, interaction):
                    self.guild = interaction.guild
                    self.voice_client = interaction.guild.voice_client
                    self.send = interaction.channel.send

            await self.play_next(FakeContext(interaction))
        
        # Show or update the music control panel
        if interaction.guild.id in self.panel_messages:
            # Update existing panel
            panel_msg, panel_view = self.panel_messages[interaction.guild.id]
            try:
                updated_embed = panel_view.create_embed()
                await panel_msg.edit(embed=updated_embed, view=panel_view)
                await interaction.followup.send("✅ Song added to queue!", ephemeral=True)
            except:
                # Panel message was deleted, create new one
                view = MusicControlPanel(self.bot, FakeContext(interaction), timeout=None)
                embed = view.create_embed()
                panel_msg = await interaction.followup.send(embed=embed, view=view)
                view.panel_message = panel_msg
                self.panel_messages[interaction.guild.id] = (panel_msg, view)
        else:
            # Create new panel
            view = MusicControlPanel(self.bot, FakeContext(interaction), timeout=None)
            embed = view.create_embed()
            panel_msg = await interaction.followup.send(embed=embed, view=view)
            view.panel_message = panel_msg
            self.panel_messages[interaction.guild.id] = (panel_msg, view)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.followup.send(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in music command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
