"""
Quote System
Refactored to use MongoDB for data persistence
"""
import discord
from discord.ext import commands
from discord import app_commands
import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging
from ..utils.ravendb_manager import raven_db

logger = logging.getLogger('DiscordBot.Quote')

QUOTE_PREFIX = "quote"
FONT_PATH_CACHE = None

class DeleteQuoteButton(discord.ui.View):
    """View with a delete button for quotes"""
    def __init__(self, quote_creator_id: int, quoted_user_id: int):
        super().__init__(timeout=None)
        self.quote_creator_id = quote_creator_id
        self.quoted_user_id = quoted_user_id
    
    @discord.ui.button(label="Delete Quote", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.quote_creator_id, self.quoted_user_id]:
            await interaction.response.send_message("❌ Only the quote creator or quoted user can delete this.", ephemeral=True)
            return
        
        try:
            await interaction.message.delete()
            await interaction.response.send_message("✅ Quote deleted!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to delete quote.", ephemeral=True)


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name="Make it a Quote",
            callback=self.quote_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def get_settings(self, guild_id):
        """Load quote settings from RavenDB for a specific guild"""
        return await raven_db.load_document(f"{QUOTE_PREFIX}/{guild_id}") or {}

    async def save_settings(self, guild_id, settings):
        """Save quote settings to RavenDB for a specific guild"""
        await raven_db.save_document(f"{QUOTE_PREFIX}/{guild_id}", settings)

    setup_group = app_commands.Group(name="setup", description="Setup bot features")

    @setup_group.command(name="quote", description="Configure the quote system")
    async def setup_quote(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need Administrator permissions to use this command!", ephemeral=True)
            return

        await interaction.response.defer()
        user = interaction.user
        channel = interaction.channel

        def check(m):
            return m.author == user and m.channel == channel

        # Question 1
        q1 = await channel.send(f"{user.mention}, please mention the **channel** where quoted messages should go.")
        try:
            import asyncio
            msg1 = await self.bot.wait_for('message', check=check, timeout=60)
            target_channel_id = msg1.channel_mentions[0].id if msg1.channel_mentions else None
            if not target_channel_id:
                try: target_channel_id = int(msg1.content)
                except: pass
            
            if not target_channel_id:
                await channel.send("❌ Invalid channel! Setup cancelled.")
                return
        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # Question 2
        q2 = await channel.send(f"Do you want to blacklist an **existing role** from using quotes? \nMention the role, or type `no` to skip.")
        try:
            msg2 = await self.bot.wait_for('message', check=check, timeout=60)
            blacklisted_role_id = msg2.role_mentions[0].id if msg2.role_mentions else None
            if not blacklisted_role_id and msg2.content.lower() != "no":
                try: blacklisted_role_id = int(msg2.content)
                except: pass
        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # Question 3
        q3 = await channel.send(f"Should I **create a new role** for banned users? \nType the **name** of the role to create it, or `no` to skip.")
        try:
            msg3 = await self.bot.wait_for('message', check=check, timeout=60)
            created_role_id = None
            if msg3.content.lower() != "no":
                try:
                    new_role = await interaction.guild.create_role(name=msg3.content, reason="Quote Ban Role created via setup")
                    created_role_id = new_role.id
                    await channel.send(f"✅ Created role **{new_role.name}**.")
                except Exception as e:
                    await channel.send(f"❌ Failed to create role: {e}")
        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # Finalize
        guild_id = str(interaction.guild_id)
        settings = await self.get_settings(guild_id)
        settings["channel_id"] = target_channel_id
        
        roles = settings.get("blacklisted_roles", [])
        if blacklisted_role_id and blacklisted_role_id not in roles: roles.append(blacklisted_role_id)
        if created_role_id and created_role_id not in roles: roles.append(created_role_id)
        settings["blacklisted_roles"] = roles
        
        await self.save_settings(guild_id, settings)

        try:
            to_delete = [q1, msg1, q2, msg2, q3, msg3]
            for m in to_delete:
                try: await m.delete()
                except: pass
            await interaction.edit_original_response(content=f"✅ **Quote Setup Complete!**\nOutput: <#{target_channel_id}>")
        except: pass

    async def quote_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu to quote a message"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            img_buffer, is_gif = await self.generate_quote_image(message)
        except Exception as e:
            logger.error(f"Failed to generate quote image: {e}")
            await interaction.followup.send("❌ Failed to generate quote image.", ephemeral=True)
            return

        target_channel = None
        if interaction.guild_id:
            settings = await self.get_settings(interaction.guild_id)
            if settings:
                if "blacklisted_roles" in settings:
                    member = interaction.guild.get_member(interaction.user.id)
                    if member and any(r.id in settings["blacklisted_roles"] for r in member.roles):
                        await interaction.followup.send("❌ You are banned from using quotes.", ephemeral=True)
                        return
                if "channel_id" in settings:
                    target_channel = self.bot.get_channel(settings["channel_id"])
        
        filename = "quote.gif" if is_gif else "quote.png"
        file = discord.File(fp=img_buffer, filename=filename)
        embed = discord.Embed(description=f"💬 Quote by {interaction.user.mention}", color=discord.Color.blurple())
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"Quoted: {message.author.display_name}", icon_url=message.author.display_avatar.url)
        
        view = DeleteQuoteButton(quote_creator_id=interaction.user.id, quoted_user_id=message.author.id)
        
        if target_channel:
            try:
                await target_channel.send(embed=embed, file=file, view=view)
                await interaction.followup.send(f"✅ Quote sent to {target_channel.mention}!", ephemeral=True)
                return
            except: pass
        
        try:
            await interaction.user.send(embed=embed, file=file, view=view)
            await interaction.followup.send("✅ Quote sent to your DMs!", ephemeral=True)
        except:
            await interaction.followup.send("❌ Could not send quote (Check your DM settings).", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        if message.reference and self.bot.user in message.mentions:
            guild_id = str(message.guild.id)
            settings = await self.get_settings(guild_id)
            if not settings: return
                
            roles = settings.get("blacklisted_roles", [])
            if any(r.id in roles for r in message.author.roles):
                await message.reply("❌ You have been banned from quoting.", delete_after=5)
                return

            try:
                original = await message.channel.fetch_message(message.reference.message_id)
                img_buffer, is_gif = await self.generate_quote_image(original)
                
                output_channel = self.bot.get_channel(settings.get("channel_id"))
                if output_channel:
                    filename = "quote.gif" if is_gif else "quote.png"
                    file = discord.File(fp=img_buffer, filename=filename)
                    embed = discord.Embed(description=f"💬 Quote by {message.author.mention}", color=discord.Color.blurple())
                    embed.set_image(url=f"attachment://{filename}")
                    embed.set_footer(text=f"Quoted: {original.author.display_name}", icon_url=original.author.display_avatar.url)
                    view = DeleteQuoteButton(quote_creator_id=message.author.id, quoted_user_id=original.author.id)
                    await output_channel.send(embed=embed, file=file, view=view)
                    await message.add_reaction("✅")
            except Exception as e:
                logger.error(f"Error in quote on_message: {e}")

    async def generate_quote_image(self, message: discord.Message):
        """
        Generate a quote image with banner background and avatar decorations.
        """
        content = message.content or ("[Image Attachment]" if message.attachments else "[Empty Message]")
        WIDTH, HEIGHT = 900, 375
        TEXT_COLOR = (255, 255, 255)
        NAME_COLOR = (220, 220, 220)
        DATE_COLOR = (180, 180, 180)
        
        try: user = await self.bot.fetch_user(message.author.id)
        except: user = message.author
        
        avatar_asset = message.author.display_avatar.with_size(256)
        avatar_buffer = io.BytesIO()
        await avatar_asset.save(avatar_buffer)
        avatar_buffer.seek(0)
        
        avatar_img = Image.open(avatar_buffer)
        is_animated_avatar = getattr(avatar_img, 'is_animated', False)
        
        avatar_frames = []
        max_frames = 5
        if is_animated_avatar:
            try:
                num = min(avatar_img.n_frames, max_frames)
                for i in range(num):
                    avatar_img.seek(i)
                    avatar_frames.append(avatar_img.convert("RGBA").copy())
            except: avatar_frames = [avatar_img.convert("RGBA")]
        else: avatar_frames = [avatar_img.convert("RGBA")]
        
        banner_img = None
        if hasattr(user, 'banner') and user.banner:
            try:
                banner_asset = user.banner.with_size(512)
                bb = io.BytesIO()
                await banner_asset.save(bb)
                bb.seek(0)
                banner_img = Image.open(bb).convert("RGBA")
            except: pass
        
        decoration_frames = []
        try:
            if hasattr(message.author, 'avatar_decoration') and message.author.avatar_decoration:
                dbuf = io.BytesIO()
                await message.author.avatar_decoration.save(dbuf)
                dbuf.seek(0)
                dimg = Image.open(dbuf)
                dimg.seek(0)
                decoration_frames = [dimg.convert("RGBA")]
        except: pass
        
        is_gif = is_animated_avatar or len(decoration_frames) > 1
        num_frames = max(len(avatar_frames), len(decoration_frames), 1)
        
        def load_font(size):
            global FONT_PATH_CACHE
            
            # 1. Try Cache
            if FONT_PATH_CACHE and os.path.exists(FONT_PATH_CACHE):
                try: return ImageFont.truetype(FONT_PATH_CACHE, size)
                except: pass

            import pathlib
            root = pathlib.Path(__file__).parent.parent.parent
            
            # 2. Try preferred fonts in the fonts folder (FAST)
            preferred = ["Snowman Varsity.ttf", "Richocet Bold.ttf"]
            for name in preferred:
                p = root / "fonts" / name
                if p.exists():
                    try:
                        font = ImageFont.truetype(str(p), size)
                        FONT_PATH_CACHE = str(p)
                        return font
                    except: pass
            
            # 3. Try common system fonts (FAST)
            sys_fonts = ["arial.ttf", "DejaVuSans.ttf", "Verdana.ttf"]
            for name in sys_fonts:
                win_p = pathlib.Path("C:/Windows/Fonts") / name
                if win_p.exists():
                    try:
                        font = ImageFont.truetype(str(win_p), size)
                        FONT_PATH_CACHE = str(win_p)
                        return font
                    except: pass
            
            # 4. Deep search (SLOW, only if cache/preferred fail)
            for p in root.rglob("*.[t|o]tf"):
                try:
                    font = ImageFont.truetype(str(p), size)
                    FONT_PATH_CACHE = str(p)
                    return font
                except: pass

            # 5. Final fallback
            return ImageFont.load_default()

        # Scale fonts even larger for shorter text
        if len(content) < 30: 
            base_size = 100
        elif len(content) < 80: 
            base_size = 80
        else:
            base_size = 60
        
        f_main = load_font(base_size)
        f_small = load_font(int(base_size * 0.7))
        f_name = load_font(45) # Slightly larger name
        f_date = load_font(30) # Slightly larger date
        f_quote_mark = load_font(180) # Large decorative quote
        
        output_frames = []
        
        for i in range(num_frames):
            av_f = avatar_frames[i % len(avatar_frames)]
            dec_f = decoration_frames[i % len(decoration_frames)] if decoration_frames else None
            
            if banner_img: bg = ImageOps.fit(banner_img.copy(), (WIDTH, HEIGHT), centering=(0.5, 0.5))
            else:
                from PIL import ImageFilter
                bg = ImageOps.fit(av_f.copy(), (WIDTH, HEIGHT), centering=(0.5, 0.5))
                bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
            
            overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
            draw_ov = ImageDraw.Draw(overlay)
            for y in range(HEIGHT):
                alpha = int(150 + (80 * (y / HEIGHT)))
                draw_ov.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
            
            bg = Image.alpha_composite(bg, overlay)
            draw = ImageDraw.Draw(bg)
            
            av_size = 180
            av_c = av_f.copy().resize((av_size, av_size))
            mask = Image.new("L", (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
            av_c.putalpha(mask)
            
            ax, ay = 80, (HEIGHT - av_size) // 2
            bg.paste(av_c, (ax, ay), av_c)
            if dec_f:
                dr = dec_f.resize((av_size, av_size))
                bg.paste(dr, (ax, ay), dr)
            
            tx, mw = 300, 550
            lines, cur = [], []
            
            # Determine font and line height based on content length
            if len(content) > 150:
                a_f, l_h = f_small, int(base_size * 0.85)
            else:
                a_f, l_h = f_main, int(base_size * 1.2)
                
            for word in content.split():
                if draw.textbbox((0, 0), ' '.join(cur + [word]), font=a_f)[2] <= mw: 
                    cur.append(word)
                else: 
                    lines.append(' '.join(cur))
                    cur = [word]
            lines.append(' '.join(cur))
            
            # Vertical centering
            total_text_height = len(lines) * l_h
            sy = (HEIGHT - total_text_height) // 2 - 20
            
            # Quote mark
            draw.text((tx - 60, sy - 40), '"', font=f_quote_mark, fill=(255, 255, 255, 30))
            
            cy = sy
            for line in lines[:7]:
                # Shadow
                draw.text((tx + 2, cy + 2), line, font=a_f, fill=(0, 0, 0, 150))
                # Main text
                draw.text((tx, cy), line, font=a_f, fill=TEXT_COLOR)
                cy += l_h
            
            cy += 15
            draw.line([(tx, cy), (tx + 300, cy)], fill=(255, 255, 255, 100), width=2)
            cy += 20
            draw.text((tx, cy), f"{message.author.display_name}", font=f_name, fill=NAME_COLOR)
            draw.text((tx, cy + 45), f"@{message.author.name} • {message.created_at.strftime('%b %d, %Y')}", font=f_date, fill=DATE_COLOR)
            output_frames.append(bg)
        
        buf = io.BytesIO()
        if is_gif and len(output_frames) > 1:
            opts = [f.convert('P', palette=Image.ADAPTIVE, colors=256) for f in output_frames]
            opts[0].save(buf, format='GIF', save_all=True, append_images=opts[1:], duration=100, loop=0, optimize=True, disposal=2)
        else: output_frames[0].save(buf, format='PNG', optimize=True)
        buf.seek(0)
        return buf, is_gif

async def setup(bot):
    await bot.add_cog(Quote(bot))
