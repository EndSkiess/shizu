"""
Music bot commands - play, pause, unpause, skip, stop
Supports YouTube URLs, search queries, and Spotify playlists
"""
import discord
from discord.ext import commands
from discord import app_commands
try:
    import yt_dlp
    HAS_YTDL = True
except ImportError:
    HAS_YTDL = False

import logging
import asyncio
import os
import shutil
from dotenv import load_dotenv

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False
from .music_panel_view import MusicControlPanel

load_dotenv()

logger = logging.getLogger('DiscordBot.Music')

# ---------------------------------------------------------------------------
# Cookies helper
# ---------------------------------------------------------------------------
COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'cookies.txt')
COOKIES_FILE = os.path.normpath(COOKIES_FILE)

def _cookies_opts() -> dict:
    """Return cookiefile option only when the file actually exists."""
    if os.path.isfile(COOKIES_FILE):
        logger.info(f"Using cookies file: {COOKIES_FILE}")
        return {'cookiefile': COOKIES_FILE}
    return {}

# ---------------------------------------------------------------------------
# yt-dlp options  (hardened for datacenter / Render IPs)
# ---------------------------------------------------------------------------

_extractor_args_youtube = {
    'player_client': ['android', 'ios'],
}

_po_token = os.getenv('YOUTUBE_PO_TOKEN')
_visitor_data = os.getenv('YOUTUBE_VISITOR_DATA')
if _po_token:
    logger.info("Using YOUTUBE_PO_TOKEN from environment")
    _extractor_args_youtube['po_token'] = [_po_token]
if _visitor_data:
    logger.info("Using YOUTUBE_VISITOR_DATA from environment")
    _extractor_args_youtube['visitor_data'] = [_visitor_data]

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioquality': 0,
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    # Impersonate mobile clients to bypass datacenter IP 429 and 152 blocks
    'extractor_args': {
        'youtube': _extractor_args_youtube,
        'youtubetab': {
            'skip': ['authcheck'],
        },
    },
    # Retry network errors automatically before giving up
    'retries': 5,
    'fragment_retries': 5,
    'skip_unavailable_fragments': True,
    **_cookies_opts(),
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000'
}

# ---------------------------------------------------------------------------
# FFmpeg path resolution (works on Render and local Windows dev)
# ---------------------------------------------------------------------------
def _find_ffmpeg() -> str:
    if shutil.which('ffmpeg'):
        return 'ffmpeg'
    candidates = [
        r"C:\Users\Samuel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return 'ffmpeg'  # last resort – will fail with a clear error

FFMPEG_EXECUTABLE = _find_ffmpeg()

if HAS_YTDL:
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
else:
    ytdl = None


# ---------------------------------------------------------------------------
# Retry wrapper – handles YouTube 429 / bot-check errors gracefully
# ---------------------------------------------------------------------------
async def extract_info_with_retry(loop, query: str, *, download=False, retries: int = 3):
    """
    Run ytdl.extract_info in an executor with exponential-backoff retry.
    Raises the last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await loop.run_in_executor(
                None, lambda q=query: ytdl.extract_info(q, download=download)
            )
        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            # Only retry on rate-limit / bot-check / network errors
            if any(k in err for k in ('429', 'rate', 'sign in', 'bot', 'http error 403',
                                       'connection', 'timeout', 'temporarily')):
                wait = 2 ** attempt  # 2 s, 4 s, 8 s …
                logger.warning(f"[yt-dlp] Attempt {attempt}/{retries} failed ({exc}). "
                                f"Retrying in {wait}s…")
                await asyncio.sleep(wait)
            else:
                raise  # non-retryable error, bail immediately
    raise last_exc


class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source for YouTube"""
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        """Create audio source from URL with retry logic."""
        if not HAS_YTDL:
            raise RuntimeError("yt-dlp is not installed. Music features are disabled.")
        loop = loop or asyncio.get_event_loop()

        data = await extract_info_with_retry(loop, url, download=not stream)

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(
            discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE, **FFMPEG_OPTIONS),
            data=data,
        )


class MusicQueue:
    """Queue system for music tracks"""
    def __init__(self):
        self.queue = []
        self.current = None

    def add(self, track):
        self.queue.append(track)

    def next(self):
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        self.current = None
        return None

    def clear(self):
        self.queue.clear()
        self.current = None

    def is_empty(self):
        return len(self.queue) == 0


class Music(commands.Cog):
    """Music playback commands"""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.panel_messages = {}
        self.autoplay_enabled = {}

        spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
        spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

        if HAS_SPOTIPY and spotify_id and spotify_secret:
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
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def play_next(self, ctx):
        """Play next song in queue"""
        queue = self.get_queue(ctx.guild.id)

        if queue.is_empty():
            if self.autoplay_enabled.get(ctx.guild.id, False):
                if queue.current and queue.current.get('title'):
                    logger.info("AutoPlay: Queue empty, getting recommendations…")
                    recommendations = await self.get_spotify_recommendations(queue.current['title'])
                    if recommendations:
                        for track_name in recommendations:
                            queue.add({
                                'url': f"ytsearch:{track_name}",
                                'title': track_name,
                                'requester': queue.current.get('requester'),
                            })
                        logger.info(f"AutoPlay: Added {len(recommendations)} recommendations")
                    else:
                        logger.warning("AutoPlay: No recommendations, waiting to disconnect…")
                        await asyncio.sleep(300)
                        if ctx.voice_client and not ctx.voice_client.is_playing():
                            await ctx.voice_client.disconnect()
                        return
                else:
                    await asyncio.sleep(300)
                    if ctx.voice_client and not ctx.voice_client.is_playing():
                        await ctx.voice_client.disconnect()
                    return
            else:
                await asyncio.sleep(300)
                if ctx.voice_client and not ctx.voice_client.is_playing():
                    await ctx.voice_client.disconnect()
                return

        track_info = queue.next()

        try:
            player = await YTDLSource.from_url(track_info['url'], loop=self.bot.loop, stream=True)
            ctx.voice_client.play(
                player,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(ctx), self.bot.loop
                ),
            )

            if ctx.guild.id in self.panel_messages:
                panel_msg, panel_view = self.panel_messages[ctx.guild.id]
                try:
                    await panel_msg.edit(embed=panel_view.create_embed(), view=panel_view)
                except discord.errors.NotFound:
                    del self.panel_messages[ctx.guild.id]
                except discord.errors.HTTPException as e:
                    if e.code in (50027,) or e.status == 401:
                        del self.panel_messages[ctx.guild.id]
                    else:
                        logger.error(f"Failed to update panel: {e}")
                except Exception as e:
                    logger.error(f"Failed to update panel: {e}")

        except Exception as e:
            logger.error(f"Error playing track '{track_info.get('title')}': {e}")
            await ctx.send(f"❌ Error playing track: {str(e)}")
            await self.play_next(ctx)

    async def get_spotify_tracks(self, url):
        if not HAS_SPOTIPY or not self.spotify:
            return None
        try:
            if 'playlist' in url:
                results = self.spotify.playlist_tracks(url)
                tracks = []
                for item in results['items']:
                    track = item['track']
                    tracks.append(f"{track['artists'][0]['name']} - {track['name']}")
                return tracks
            elif 'track' in url:
                track = self.spotify.track(url)
                return [f"{track['artists'][0]['name']} - {track['name']}"]
        except Exception as e:
            logger.error(f"Spotify error: {e}")
            return None

    async def get_spotify_recommendations(self, track_title):
        if not self.spotify:
            return None
        try:
            search = self.spotify.search(q=track_title, type='track', limit=1)
            if not search['tracks']['items']:
                simplified = track_title.split('-')[0].strip() if '-' in track_title else track_title
                search = self.spotify.search(q=simplified, type='track', limit=1)
                if not search['tracks']['items']:
                    return None

            track = search['tracks']['items'][0]
            artist_id = track['artists'][0]['id']
            artist_name = track['artists'][0]['name']
            logger.info(f"AutoPlay: Using artist '{artist_name}' for recommendations")

            top_tracks = self.spotify.artist_top_tracks(artist_id, country='US')
            if not top_tracks or 'tracks' not in top_tracks:
                return None

            recommended = [
                f"{t['artists'][0]['name']} - {t['name']}"
                for t in top_tracks['tracks'][:10]
            ]

            if len(recommended) < 5:
                try:
                    related = self.spotify.artist_related_artists(artist_id)
                    for ra in (related or {}).get('artists', [])[:3]:
                        for t in self.spotify.artist_top_tracks(ra['id'], country='US')['tracks'][:3]:
                            name = f"{t['artists'][0]['name']} - {t['name']}"
                            if name not in recommended:
                                recommended.append(name)
                        if len(recommended) >= 10:
                            break
                except Exception:
                    pass

            return recommended or None
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return None

    def set_autoplay(self, guild_id, enabled):
        self.autoplay_enabled[guild_id] = enabled
        logger.info(f"AutoPlay {'enabled' if enabled else 'disabled'} for guild {guild_id}")

    @app_commands.command(name="music", description="Play music from YouTube or Spotify")
    @app_commands.describe(query="YouTube URL, search query, or Spotify link")
    async def music(self, interaction: discord.Interaction, query: str):
        """Play music and show control panel"""
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.HTTPException):
            return

        if not HAS_YTDL:
            await interaction.followup.send(
                "❌ Music features are disabled – `yt-dlp` is not installed.", ephemeral=True
            )
            return

        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel!", ephemeral=True)
            return

        if not interaction.guild.voice_client:
            try:
                await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to join voice channel: {e}", ephemeral=True)
                return
        elif interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.followup.send(
                f"❌ You must be in {interaction.guild.voice_client.channel.mention}!", ephemeral=True
            )
            return

        queue = self.get_queue(interaction.guild.id)

        if 'spotify.com' in query:
            if not self.spotify:
                await interaction.followup.send(
                    "❌ Spotify not configured! Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env",
                    ephemeral=True,
                )
                return
            tracks = await self.get_spotify_tracks(query)
            if not tracks:
                await interaction.followup.send("❌ Failed to extract Spotify tracks!", ephemeral=True)
                return
            for track_name in tracks:
                queue.add({'url': f"ytsearch:{track_name}", 'title': track_name, 'requester': interaction.user})
        else:
            if not query.startswith('http'):
                query = f"ytsearch:{query}"
            try:
                info = await extract_info_with_retry(self.bot.loop, query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                queue.add({'url': info['webpage_url'], 'title': info['title'], 'requester': interaction.user})
            except Exception as e:
                err = str(e)
                msg = "❌ An error occurred while adding that track."
                if any(k in err.lower() for k in ('sign in', 'bot', '403', '429', 'rate')):
                    msg = (
                        "❌ YouTube is rate-limiting the bot. "
                        "Add a `cookies.txt` to the bot root, or wait a few minutes and try again."
                    )
                await interaction.followup.send(msg, ephemeral=True)
                return

        class FakeContext:
            def __init__(self, interaction):
                self.guild = interaction.guild
                self.voice_client = interaction.guild.voice_client
                self.send = interaction.channel.send

        fake_ctx = FakeContext(interaction)

        if not interaction.guild.voice_client.is_playing():
            await self.play_next(fake_ctx)

        if interaction.guild.id in self.panel_messages:
            panel_msg, panel_view = self.panel_messages[interaction.guild.id]
            try:
                await panel_msg.edit(embed=panel_view.create_embed(), view=panel_view)
                await interaction.followup.send("✅ Song added to queue!", ephemeral=True)
                return
            except Exception:
                pass  # Panel gone – fall through to create a new one

        view = MusicControlPanel(self.bot, fake_ctx, timeout=None)
        embed = view.create_embed()
        panel_msg = await interaction.followup.send(embed=embed, view=view)
        view.panel_message = panel_msg
        self.panel_messages[interaction.guild.id] = (panel_msg, view)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Cooldown – retry in {error.retry_after:.2f}s."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You don't have permission to use this command."
        else:
            logger.error(f"Error in music command: {error}", exc_info=True)
            err_str = str(error)
            if any(k in err_str.lower() for k in ('sign in', 'bot', '403', '429')):
                msg = "❌ YouTube is blocking the bot. Upload a valid `cookies.txt` to the bot root."
            else:
                msg = "❌ An error occurred while processing this command."

        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Music(bot))
