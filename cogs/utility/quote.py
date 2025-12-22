"""
Quote System
Triggers when a user replies to a message and pings the bot.
Generates an image of the quoted message and sends it to a configured channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging

logger = logging.getLogger('DiscordBot.Quote')

QUOTE_SETTINGS_FILE = "data/quote_settings.json"

class DeleteQuoteButton(discord.ui.View):
    """View with a delete button for quotes"""
    def __init__(self, quote_creator_id: int, quoted_user_id: int):
        super().__init__(timeout=None)  # No timeout
        self.quote_creator_id = quote_creator_id
        self.quoted_user_id = quoted_user_id
    
    @discord.ui.button(label="Delete Quote", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is authorized to delete
        if interaction.user.id not in [self.quote_creator_id, self.quoted_user_id]:
            await interaction.response.send_message("❌ Only the quote creator or quoted user can delete this.", ephemeral=True)
            return
        
        # Delete the message
        try:
            await interaction.message.delete()
            await interaction.response.send_message("✅ Quote deleted!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to delete quote.", ephemeral=True)


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = self.load_settings()
        
        # Add context menu
        self.ctx_menu = app_commands.ContextMenu(
            name="Make it a Quote",
            callback=self.quote_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    def load_settings(self):
        if not os.path.exists(QUOTE_SETTINGS_FILE):
            return {}
        try:
            with open(QUOTE_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_settings(self):
        with open(QUOTE_SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f, indent=4)

    # Setup Group
    setup_group = app_commands.Group(name="setup", description="Setup bot features")

    @setup_group.command(name="quote", description="Configure the quote system")
    async def setup_quote(self, interaction: discord.Interaction):
        # Check permissions (Admin only)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need Administrator permissions to use this command!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False) # Not ephemeral so we can delete later easily if needed, or stick to channel context
        
        user = interaction.user
        channel = interaction.channel

        # Helper to wait for message
        def check(m):
            return m.author == user and m.channel == channel

        # 1. Ask for Channel
        q1 = await channel.send(f"{user.mention}, please mention the **channel** where quoted messages should go.")
        try:
            msg1 = await self.bot.wait_for('message', check=check, timeout=60)
            
            # Parse channel
            target_channel_id = None
            if msg1.channel_mentions:
                target_channel_id = msg1.channel_mentions[0].id
            else:
                try:
                    target_channel_id = int(msg1.content)
                except:
                    pass
            
            if not target_channel_id:
                await channel.send("❌ Invalid channel! Setup cancelled.")
                return

        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # 2. Ask for Blacklisted Role
        q2 = await channel.send(f"Do you want to blacklist an **existing role** from using quotes? \nMention the role, or type `no` to skip.")
        try:
            msg2 = await self.bot.wait_for('message', check=check, timeout=60)
            
            blacklisted_role_id = None
            if msg2.content.lower() != "no":
                if msg2.role_mentions:
                    blacklisted_role_id = msg2.role_mentions[0].id
                else:
                    # Try by ID
                    try:
                        blacklisted_role_id = int(msg2.content)
                    except:
                        pass
        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # 3. Create New Banned Role
        q3 = await channel.send(f"Should I **create a new role** for banned users? \nType the **name** of the role to create it, or `no` to skip.")
        try:
            msg3 = await self.bot.wait_for('message', check=check, timeout=60)
            
            created_role_id = None
            if msg3.content.lower() != "no":
                role_name = msg3.content
                try:
                    new_role = await interaction.guild.create_role(name=role_name, reason="Quote Ban Role created via setup")
                    created_role_id = new_role.id
                    await channel.send(f"✅ Created role **{new_role.name}**.")
                except Exception as e:
                    await channel.send(f"❌ Failed to create role: {e}")
                    pass

        except asyncio.TimeoutError:
            await channel.send("⏰ Setup timed out.")
            return

        # Save Settings
        guild_id = str(interaction.guild_id)
        if guild_id not in self.settings:
            self.settings[guild_id] = {}
        
        self.settings[guild_id]["channel_id"] = target_channel_id
        
        # Merge blacklisted roles list
        current_roles = self.settings[guild_id].get("blacklisted_roles", [])
        if blacklisted_role_id and blacklisted_role_id not in current_roles:
            current_roles.append(blacklisted_role_id)
        if created_role_id and created_role_id not in current_roles:
            current_roles.append(created_role_id)
            
        self.settings[guild_id]["blacklisted_roles"] = current_roles
        
        self.save_settings()

        # Cleanup
        try:
            await interaction.original_response() # To get the interaction message? actually we sent followups? No wait, defer sends a "thinking" state.
            # We used channel.send for questions.
            # Delete questions and answers
            to_delete = [q1, msg1, q2, msg2, q3, msg3]
            for m in to_delete:
                try:
                    await m.delete()
                except:
                    pass
            # Also delete the interaction response ("Thinking...") if possible, or edit it to success
            await interaction.edit_original_response(content=f"✅ **Quote Setup Complete!**\nOutput: <#{target_channel_id}>")
        except:
            pass

    async def quote_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu to quote a message"""
        await interaction.response.defer(ephemeral=True)
        
        # 1. Generate Image
        try:
            img_buffer, is_gif = await self.generate_quote_image(message)
        except Exception as e:
            logger.error(f"Failed to generate quote image: {e}")
            await interaction.followup.send("❌ Failed to generate quote image.", ephemeral=True)
            return

        # 2. Determine Output Destination
        sent_to_dm = False
        target_channel = None
        
        # Check if in a guild and configured
        if interaction.guild_id:
            guild_id = str(interaction.guild_id)
            if guild_id in self.settings:
                # Configuration Check
                settings = self.settings[guild_id]
                
                # Check Blacklist
                if "blacklisted_roles" in settings:
                    member = interaction.guild.get_member(interaction.user.id)
                    if member:
                        for role in member.roles:
                            if role.id in settings["blacklisted_roles"]:
                                await interaction.followup.send("❌ You are banned from using quotes.", ephemeral=True)
                                return

                # Get Channel
                if "channel_id" in settings:
                    target_channel = self.bot.get_channel(settings["channel_id"])
        
        # 3. Create Embed and File
        filename = "quote.gif" if is_gif else "quote.png"
        file = discord.File(fp=img_buffer, filename=filename)
        
        embed = discord.Embed(
            description=f"💬 Quote by {interaction.user.mention}",
            color=discord.Color.blurple()
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"Quoted: {message.author.display_name}", icon_url=message.author.display_avatar.url)
        
        # Create delete button view
        view = DeleteQuoteButton(quote_creator_id=interaction.user.id, quoted_user_id=message.author.id)
        
        if target_channel:
            # Send to server channel
            try:
                await target_channel.send(embed=embed, file=file, view=view)
                await interaction.followup.send(f"✅ Quote sent to {target_channel.mention}!", ephemeral=True)
                return
            except Exception as e:
                # Fallback if failed to send to channel (perms etc)
                pass
        
        # Fallback: Send to DM
        try:
            await interaction.user.send(embed=embed, file=file, view=view)
            await interaction.followup.send("✅ Quote sent to your DMs!", ephemeral=True)
        except:
            await interaction.followup.send("❌ Could not send quote (Check your DM settings).", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        # Check if it's a reply and mentions the bot
        if message.reference and self.bot.user in message.mentions:
            # It's a quote request!
            
            # 1. Check if configured
            guild_id = str(message.guild.id)
            if guild_id not in self.settings:
                # Not configured, ignore
                return
                
            quote_settings = self.settings[guild_id]
            
            # 2. Check Blacklist
            member = message.author
            blacklisted_roles = quote_settings.get("blacklisted_roles", [])
            for role in member.roles:
                if role.id in blacklisted_roles:
                    await message.reply("❌ You have been banned from quoting.", delete_after=5)
                    return

            # 3. Get Quoted Message
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id) # Resolves usage of reply 
            except:
                return 

            # 4. Generate Image
            try:
                img_buffer, is_gif = await self.generate_quote_image(original_message)
            except Exception as e:
                logger.error(f"Failed to generate quote image: {e}")
                return

            # 5. Send to Configured Channel
            output_channel_id = quote_settings.get("channel_id")
            output_channel = self.bot.get_channel(output_channel_id)
            
            if output_channel:
                filename = "quote.gif" if is_gif else "quote.png"
                file = discord.File(fp=img_buffer, filename=filename)
                
                embed = discord.Embed(
                    description=f"💬 Quote by {message.author.mention}",
                    color=discord.Color.blurple()
                )
                embed.set_image(url=f"attachment://{filename}")
                embed.set_footer(text=f"Quoted: {original_message.author.display_name}", icon_url=original_message.author.display_avatar.url)
                
                # Create delete button view
                view = DeleteQuoteButton(quote_creator_id=message.author.id, quoted_user_id=original_message.author.id)
                
                await output_channel.send(embed=embed, file=file, view=view)
                await message.add_reaction("✅") # Ack
            else:
                logger.error("Output channel not found")

    async def generate_quote_image(self, message: discord.Message):
        """
        Generate a quote image with banner background and avatar decorations.
        Creates animated GIF if avatar or decoration is animated.
        Returns: (buffer, is_gif) tuple
        """
        # Configuration
        WIDTH = 1200
        HEIGHT = 500
        TEXT_COLOR = (255, 255, 255)
        NAME_COLOR = (220, 220, 220)
        DATE_COLOR = (180, 180, 180)
        
        # 1. Fetch full user object to get banner
        try:
            user = await self.bot.fetch_user(message.author.id)
        except:
            user = message.author
        
        
        # 2. Prepare Assets (optimized for memory)
        # Download avatar (check if animated) - use smaller size to save memory
        avatar_asset = message.author.display_avatar.with_size(256)  # Reduced from 512
        avatar_buffer = io.BytesIO()
        await avatar_asset.save(avatar_buffer)
        avatar_buffer.seek(0)
        
        # Open avatar and check if it's animated
        avatar_img = Image.open(avatar_buffer)
        is_animated_avatar = getattr(avatar_img, 'is_animated', False)
        
        
        # Extract frames if animated (limit to 10 frames to prevent OOM)
        avatar_frames = []
        max_frames = 10  # Further reduced to prevent memory issues
        
        if is_animated_avatar:
            try:
                num_avatar_frames = min(avatar_img.n_frames, max_frames)
                for frame_idx in range(num_avatar_frames):
                    avatar_img.seek(frame_idx)
                    avatar_frames.append(avatar_img.convert("RGBA").copy())
                logger.info(f"Loaded {len(avatar_frames)} avatar frames")
            except:
                avatar_frames = [avatar_img.convert("RGBA")]
        else:
            avatar_frames = [avatar_img.convert("RGBA")]
        
        # Download banner if available (smaller size)
        banner_img = None
        if hasattr(user, 'banner') and user.banner:
            try:
                banner_asset = user.banner.with_size(512)  # Reduced from 1024
                banner_buffer = io.BytesIO()
                await banner_asset.save(banner_buffer)
                banner_buffer.seek(0)
                banner_img = Image.open(banner_buffer).convert("RGBA")
                logger.info(f"Loaded banner for {user.name}")
            except Exception as e:
                logger.warning(f"Failed to load banner: {e}")
        
        # Try to get avatar decoration (Nitro feature) - USE STATIC ONLY to prevent OOM
        decoration_frames = []
        try:
            if hasattr(message.author, 'avatar_decoration') and message.author.avatar_decoration:
                decoration_asset = message.author.avatar_decoration
                decoration_buffer = io.BytesIO()
                await decoration_asset.save(decoration_buffer)
                decoration_buffer.seek(0)
                decoration_img = Image.open(decoration_buffer)
                
                # ALWAYS use only first frame to prevent OOM crashes
                # Animated decorations are too memory-intensive
                decoration_img.seek(0)
                decoration_frames = [decoration_img.convert("RGBA")]
                logger.info(f"Loaded avatar decoration (static only to prevent OOM)")
        except Exception as e:
            logger.debug(f"No avatar decoration or failed to load: {e}")
        
        # Determine if we need GIF
        is_gif = is_animated_avatar or len(decoration_frames) > 1
        
        # Calculate number of frames (use max of avatar and decoration frames)
        num_frames = max(len(avatar_frames), len(decoration_frames), 1)
        
        # 3. Load fonts once (outside frame loop for efficiency)
        def load_font(name, size):
            cog_dir = os.path.dirname(os.path.abspath(__file__))
            bot_root = os.path.dirname(os.path.dirname(cog_dir))
            bundled_fonts_dir = os.path.join(bot_root, "fonts")
            
            font_paths = [
                os.path.join(bundled_fonts_dir, name),
                f"C:/Windows/Fonts/{name}",
                f"C:\\Windows\\Fonts\\{name}",
                f"/usr/share/fonts/truetype/dejavu/{name}",
                f"/usr/share/fonts/truetype/liberation/{name}",
                f"/usr/share/fonts/truetype/{name}",
                f"/usr/share/fonts/{name}",
                f"/usr/local/share/fonts/{name}",
                name,
            ]
            
            for path in font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
            
            logger.warning(f"Failed to load font '{name}' at size {size}, using default font.")
            return ImageFont.load_default()

        font_large = load_font("Richocet Bold.ttf", 60)
        font_med = load_font("Richocet Bold.ttf", 45)
        font_name = load_font("Richocet Bold.ttf", 40)
        font_date = load_font("Richocet Bold.ttf", 28)
        font_quote = load_font("Richocet Bold.ttf", 120)
        
        # Prepare text content
        content = message.content
        if not content and message.attachments:
            content = "[Image Attachment]"
        
        # 4. Generate frames
        output_frames = []
        frame_duration = 100  # milliseconds per frame
        
        for frame_idx in range(num_frames):
            # Get current frame for avatar and decoration (loop if needed)
            avatar_frame = avatar_frames[frame_idx % len(avatar_frames)]
            decoration_frame = decoration_frames[frame_idx % len(decoration_frames)] if decoration_frames else None
            
            # Create Background
            if banner_img:
                bg_img = ImageOps.fit(banner_img.copy(), (WIDTH, HEIGHT), centering=(0.5, 0.5))
            else:
                bg_img = ImageOps.fit(avatar_frame.copy(), (WIDTH, HEIGHT), centering=(0.5, 0.5))
                from PIL import ImageFilter
                bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=20))
            
            # Gradient overlay
            overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            for y in range(HEIGHT):
                alpha = int(150 + (80 * (y / HEIGHT)))
                draw_overlay.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
            
            bg_img = Image.alpha_composite(bg_img, overlay)
            draw = ImageDraw.Draw(bg_img)
            
            # Circular Avatar
            avatar_size = 220
            avatar_circle = avatar_frame.copy().resize((avatar_size, avatar_size))
            
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            output_avatar = ImageOps.fit(avatar_circle, (avatar_size, avatar_size), centering=(0.5, 0.5))
            output_avatar.putalpha(mask)
            
            # Border ring
            ring_size = avatar_size + 8
            ring = Image.new("RGBA", (ring_size, ring_size), (0, 0, 0, 0))
            draw_ring = ImageDraw.Draw(ring)
            draw_ring.ellipse((0, 0, ring_size, ring_size), outline=(255, 255, 255, 50), width=4)
            
            avatar_x = 100
            avatar_y = (HEIGHT - avatar_size) // 2
            ring_x = avatar_x - (ring_size - avatar_size) // 2
            ring_y = avatar_y - (ring_size - avatar_size) // 2
            
            bg_img.paste(ring, (ring_x, ring_y), ring)
            bg_img.paste(output_avatar, (avatar_x, avatar_y), output_avatar)
            
            # Overlay decoration
            if decoration_frame:
                try:
                    decoration_resized = decoration_frame.resize((avatar_size, avatar_size))
                    bg_img.paste(decoration_resized, (avatar_x, avatar_y), decoration_resized)
                except Exception as e:
                    logger.warning(f"Failed to apply decoration frame {frame_idx}: {e}")
            
            # Draw Text
            text_x = 380
            max_width = 750
            
            lines = []
            words = content.split()
            current_line = []
            
            if len(content) > 150:
                active_font = font_med
                line_height = 50
            else:
                active_font = font_large
                line_height = 70
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=active_font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))
            
            text_block_height = len(lines) * line_height
            total_height = text_block_height + 80
            start_y = (HEIGHT - total_height) // 2
            
            # Quote mark
            draw.text((text_x - 50, start_y - 60), '"', font=font_quote, fill=(255, 255, 255, 40))
            
            # Content
            current_y = start_y
            for line in lines[:7]:
                draw.text((text_x + 3, current_y + 3), line, font=active_font, fill=(0, 0, 0, 180))
                draw.text((text_x, current_y), line, font=active_font, fill=TEXT_COLOR)
                current_y += line_height
            
            # Separator
            current_y += 15
            draw.line([(text_x, current_y), (text_x + 300, current_y)], fill=(255, 255, 255, 100), width=2)
            current_y += 20
            
            # Name
            name_text = f"{message.author.display_name}"
            draw.text((text_x + 2, current_y + 2), name_text, font=font_name, fill=(0, 0, 0, 180))
            draw.text((text_x, current_y), name_text, font=font_name, fill=NAME_COLOR)
            
            # Handle and date
            handle = f"@{message.author.name}"
            date_str = message.created_at.strftime("%b %d, %Y")
            meta_text = f"{handle} • {date_str}"
            draw.text((text_x, current_y + 40), meta_text, font=font_date, fill=DATE_COLOR)
            
            output_frames.append(bg_img)
        
        
        # 5. Save as GIF or PNG (optimized)
        output_buffer = io.BytesIO()
        if is_gif and len(output_frames) > 1:
            # Convert frames to P mode (palette) to reduce memory
            optimized_frames = []
            for frame in output_frames:
                # Convert to palette mode with adaptive palette
                frame_p = frame.convert('P', palette=Image.ADAPTIVE, colors=256)
                optimized_frames.append(frame_p)
            
            # Save optimized GIF
            optimized_frames[0].save(
                output_buffer,
                format='GIF',
                save_all=True,
                append_images=optimized_frames[1:],
                duration=100,  # 100ms per frame
                loop=0,
                optimize=True,  # Enable optimization
                disposal=2  # Clear frame before next
            )
            logger.info(f"Created optimized animated GIF with {len(optimized_frames)} frames")
        else:
            output_frames[0].save(output_buffer, format='PNG', optimize=True)
        
        output_buffer.seek(0)
        return output_buffer, is_gif 

async def setup(bot):
    await bot.add_cog(Quote(bot))
