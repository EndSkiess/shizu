"""
Marriage & Family System - Propose, marry, adopt, and build family trees
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

from .marriage_utils import (
    is_married, get_partner, marry_users, divorce_users,
    get_marriage_data, toggle_joint_balance, get_couple_leaderboard,
    get_family_data, add_child, can_adopt, get_full_family,
    remove_child, remove_from_family
)

# Try to import economy utils for joint balance
try:
    from .economy_utils import get_balance, add_balance, remove_balance, CURRENCY_NAME
    ECONOMY_AVAILABLE = True
except ImportError:
    ECONOMY_AVAILABLE = False

logger = logging.getLogger('DiscordBot.Marriage')


class ProposalView(discord.ui.View):
    """Interactive view for marriage proposals"""
    def __init__(self, proposer, target):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.target = target
        self.value = None
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions"""
        logger.error(f"Error in ProposalView: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred processing this action.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred processing this action.", ephemeral=True)
        except:
            pass
    
    @discord.ui.button(label="Accept 💍", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This proposal isn't for you!", ephemeral=True)
            return
        
        self.value = True
        self.stop()
        
        # Marry the users
        marry_users(self.proposer.id, self.target.id)
        
        embed = discord.Embed(
            title="💒 Just Married! 💒",
            description=f"{self.proposer.mention} and {self.target.mention} are now married!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Congratulations! 🎉")
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Reject ❌", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This proposal isn't for you!", ephemeral=True)
            return
        
        self.value = False
        self.stop()
        
        embed = discord.Embed(
            title="💔 Proposal Rejected",
            description=f"{self.target.mention} rejected {self.proposer.mention}'s proposal.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class AdoptionView(discord.ui.View):
    """Interactive view for adoption requests"""
    def __init__(self, parent, child):
        super().__init__(timeout=60)
        self.parent = parent
        self.child = child
        self.value = None
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions"""
        logger.error(f"Error in AdoptionView: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred processing this action.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred processing this action.", ephemeral=True)
        except:
            pass

    @discord.ui.button(label="Accept 👶", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.child.id:
            await interaction.response.send_message("This adoption request isn't for you!", ephemeral=True)
            return
        
        self.value = True
        self.stop()
        
        # Add child to family
        add_child(self.parent.id, self.child.id)
        
        embed = discord.Embed(
            title="👨‍👩‍👧 Adoption Complete! 👨‍👩‍👧",
            description=f"{self.parent.mention} has adopted {self.child.mention}!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Welcome to the family! 🎉")
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Reject ❌", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.child.id:
            await interaction.response.send_message("This adoption request isn't for you!", ephemeral=True)
            return
        
        self.value = False
        self.stop()
        
        embed = discord.Embed(
            title="❌ Adoption Rejected",
            description=f"{self.child.mention} rejected {self.parent.mention}'s adoption request.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class Marriage(commands.Cog):
    """Marriage and family system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="propose", description="Propose marriage to another user")
    @app_commands.describe(user="User to propose to")
    async def propose(self, interaction: discord.Interaction, user: discord.Member):
        """Propose marriage to another user"""
        # Validation
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't marry yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't marry a bot!", ephemeral=True)
            return
        
        if is_married(interaction.user.id):
            await interaction.response.send_message("❌ You're already married!", ephemeral=True)
            return
        
        if is_married(user.id):
            await interaction.response.send_message(f"❌ {user.mention} is already married!", ephemeral=True)
            return
        
        # Create proposal embed
        embed = discord.Embed(
            title="💍 Marriage Proposal 💍",
            description=f"{interaction.user.mention} is proposing to {user.mention}!",
            color=discord.Color.pink()
        )
        embed.set_footer(text="Will you marry them?")
        
        # Send proposal with buttons
        view = ProposalView(interaction.user, user)
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="divorce", description="Divorce your current partner")
    async def divorce(self, interaction: discord.Interaction):
        """Divorce current partner"""
        if not is_married(interaction.user.id):
            await interaction.response.send_message("❌ You're not married!", ephemeral=True)
            return
        
        marriage_data = get_marriage_data(interaction.user.id)
        partner_id = marriage_data["partner_id"]
        
        # Handle joint balance
        if ECONOMY_AVAILABLE and marriage_data.get("joint_balance", False):
            # Split balance 50/50
            user_balance = await get_balance(interaction.user.id)
            partner_balance = await get_balance(int(partner_id))
            total = user_balance + partner_balance
            split = total // 2
            
            # Set new balances
            await remove_balance(interaction.user.id, user_balance)
            await add_balance(interaction.user.id, split)
            await remove_balance(int(partner_id), partner_balance)
            await add_balance(int(partner_id), split)
        
        # Divorce
        divorce_users(interaction.user.id)
        
        try:
            partner = await self.bot.fetch_user(int(partner_id))
            partner_mention = partner.mention
        except:
            partner_mention = f"User {partner_id}"
        
        embed = discord.Embed(
            title="💔 Divorce",
            description=f"{interaction.user.mention} and {partner_mention} are now divorced.",
            color=discord.Color.dark_gray()
        )
        
        if ECONOMY_AVAILABLE and marriage_data.get("joint_balance", False):
            embed.add_field(name="Joint Balance Split", value=f"Each received {split:,} {CURRENCY_NAME}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="marry", description="View marriage status")
    @app_commands.describe(user="User to view (optional)")
    async def marry(self, interaction: discord.Interaction, user: discord.Member = None):
        """View marriage status"""
        target = user or interaction.user
        
        if not is_married(target.id):
            await interaction.response.send_message(f"❌ {target.mention} is not married!", ephemeral=True)
            return
        
        marriage_data = get_marriage_data(target.id)
        partner_id = marriage_data["partner_id"]
        married_at = datetime.fromisoformat(marriage_data["married_at"])
        duration = datetime.utcnow() - married_at
        
        days = duration.days
        hours = duration.seconds // 3600
        
        try:
            partner = await self.bot.fetch_user(int(partner_id))
            partner_name = partner.display_name
        except:
            partner_name = f"User {partner_id}"
        
        embed = discord.Embed(
            title=f"💑 {target.display_name}'s Marriage",
            color=discord.Color.pink()
        )
        embed.add_field(name="Partner", value=partner_name, inline=True)
        embed.add_field(name="Duration", value=f"{days} days, {hours} hours", inline=True)
        embed.add_field(name="Joint Balance", value="✅ Enabled" if marriage_data.get("joint_balance") else "❌ Disabled", inline=True)
        embed.set_footer(text=f"Married since {married_at.strftime('%Y-%m-%d')}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="couples", description="View couple leaderboard")
    async def couples(self, interaction: discord.Interaction):
        """Display couple leaderboard"""
        couples = get_couple_leaderboard(10)
        
        if not couples:
            await interaction.response.send_message("❌ No married couples found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💑 Couple Leaderboard",
            description="Top 10 couples by marriage duration",
            color=discord.Color.gold()
        )
        
        for i, couple in enumerate(couples, 1):
            try:
                user1 = await self.bot.fetch_user(int(couple["user1_id"]))
                user2 = await self.bot.fetch_user(int(couple["user2_id"]))
                
                duration = couple["duration"]
                days = int(duration // 86400)
                hours = int((duration % 86400) // 3600)
                
                joint = "💰" if couple["joint_balance"] else ""
                
                embed.add_field(
                    name=f"{i}. {user1.display_name} & {user2.display_name} {joint}",
                    value=f"{days} days, {hours} hours",
                    inline=False
                )
            except Exception as e:
                logger.error(f"Failed to fetch couple: {e}")
                continue
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="jointbalance", description="Toggle joint balance with your partner")
    async def jointbalance(self, interaction: discord.Interaction):
        """Toggle joint balance"""
        if not ECONOMY_AVAILABLE:
            await interaction.response.send_message("❌ Economy system not available!", ephemeral=True)
            return
        
        if not is_married(interaction.user.id):
            await interaction.response.send_message("❌ You're not married!", ephemeral=True)
            return
        
        new_value = toggle_joint_balance(interaction.user.id)
        
        if new_value:
            embed = discord.Embed(
                title="💰 Joint Balance Enabled",
                description="You and your partner now share a joint balance!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="💰 Joint Balance Disabled",
                description="You and your partner now have separate balances.",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="adopt", description="Adopt another user as your child")
    @app_commands.describe(user="User to adopt")
    async def adopt(self, interaction: discord.Interaction, user: discord.Member):
        """Adopt another user"""
        # Validation
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't adopt yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't adopt a bot!", ephemeral=True)
            return
        
        if not can_adopt(interaction.user.id, user.id):
            await interaction.response.send_message(f"❌ {user.mention} already has 2 parents!", ephemeral=True)
            return
        
        # Create adoption embed
        embed = discord.Embed(
            title="👶 Adoption Request 👶",
            description=f"{interaction.user.mention} wants to adopt {user.mention}!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Do you accept?")
        
        # Send request with buttons
        view = AdoptionView(interaction.user, user)
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="disown", description="Disown one of your children")
    @app_commands.describe(user="Child to disown")
    async def disown(self, interaction: discord.Interaction, user: discord.Member):
        """Disown a child from your family"""
        # Get family data
        family_data = get_family_data(interaction.user.id)
        
        # Check if user is actually their child
        if str(user.id) not in family_data.get("children_ids", []):
            await interaction.response.send_message(f"❌ {user.mention} is not your child!", ephemeral=True)
            return
        
        # Remove the child
        success = remove_child(interaction.user.id, user.id)
        
        if success:
            embed = discord.Embed(
                title="💔 Child Disowned",
                description=f"{interaction.user.mention} has disowned {user.mention}.",
                color=discord.Color.dark_red()
            )
            embed.set_footer(text="They are no longer part of your family tree.")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Failed to disown child. Please try again.", ephemeral=True)
    
    @app_commands.command(name="runaway", description="Leave your entire family tree")
    async def runaway(self, interaction: discord.Interaction):
        """Leave the entire family tree"""
        # Get family data
        family_data = get_family_data(interaction.user.id)
        
        # Check if user has any family
        has_parents = len(family_data.get("parent_ids", [])) > 0
        has_children = len(family_data.get("children_ids", [])) > 0
        
        if not has_parents and not has_children:
            await interaction.response.send_message("❌ You don't have any family to leave!", ephemeral=True)
            return
        
        # Remove from family
        success = remove_from_family(interaction.user.id)
        
        if success:
            embed = discord.Embed(
                title="🏃 Ran Away From Family",
                description=f"{interaction.user.mention} has left their family tree!",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="What happened?",
                value="All parent and child relationships have been removed.",
                inline=False
            )
            embed.set_footer(text="You can always start a new family!")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Failed to leave family. Please try again.", ephemeral=True)
    
    @app_commands.command(name="tree", description="View your family tree")
    async def tree(self, interaction: discord.Interaction):
        """Generate and display family tree image"""
        await interaction.response.defer()
        
        # Get family data
        family = get_full_family(interaction.user.id)
        
        # Create image
        img_width = 1200
        img_height = 800
        img = Image.new('RGB', (img_width, img_height), color='#2C2F33')
        draw = ImageDraw.Draw(img)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Define positions
        center_x = img_width // 2
        user_y = 400
        
        # Draw user (highlighted in blue)
        user_name = interaction.user.display_name
        draw.rectangle([center_x - 100, user_y - 30, center_x + 100, user_y + 30], fill='#5865F2', outline='white', width=3)
        draw.text((center_x, user_y), user_name, fill='white', font=font, anchor='mm')
        
        # Draw spouse
        if family["spouse"]:
            try:
                spouse = await self.bot.fetch_user(int(family["spouse"]))
                spouse_name = spouse.display_name
                spouse_x = center_x + 250
                draw.rectangle([spouse_x - 100, user_y - 30, spouse_x + 100, user_y + 30], fill='#ED4245', outline='white', width=2)
                draw.text((spouse_x, user_y), spouse_name, fill='white', font=font, anchor='mm')
                # Draw connection line
                draw.line([center_x + 100, user_y, spouse_x - 100, user_y], fill='white', width=2)
            except:
                pass
        
        # Draw parents
        if family["parents"]:
            parent_y = 200
            parent_spacing = 250
            start_x = center_x - (len(family["parents"]) - 1) * parent_spacing // 2
            
            for i, parent_id in enumerate(family["parents"][:2]):
                try:
                    parent = await self.bot.fetch_user(int(parent_id))
                    parent_name = parent.display_name
                    parent_x = start_x + i * parent_spacing
                    draw.rectangle([parent_x - 80, parent_y - 25, parent_x + 80, parent_y + 25], fill='#57F287', outline='white', width=2)
                    draw.text((parent_x, parent_y), parent_name, fill='white', font=font_small, anchor='mm')
                    # Draw line to user
                    draw.line([parent_x, parent_y + 25, center_x, user_y - 30], fill='white', width=2)
                except:
                    pass
        
        # Draw children
        if family["children"]:
            child_y = 600
            child_spacing = 200
            num_children = min(len(family["children"]), 5)
            start_x = center_x - (num_children - 1) * child_spacing // 2
            
            for i, child_id in enumerate(family["children"][:5]):
                try:
                    child = await self.bot.fetch_user(int(child_id))
                    child_name = child.display_name
                    child_x = start_x + i * child_spacing
                    draw.rectangle([child_x - 70, child_y - 25, child_x + 70, child_y + 25], fill='#FEE75C', outline='white', width=2)
                    draw.text((child_x, child_y), child_name, fill='black', font=font_small, anchor='mm')
                    # Draw line from user
                    draw.line([center_x, user_y + 30, child_x, child_y - 25], fill='white', width=2)
                except:
                    pass
        
        # Draw grandparents
        if family["grandparents"]:
            gp_y = 50
            gp_spacing = 200
            num_gp = min(len(family["grandparents"]), 4)
            start_x = center_x - (num_gp - 1) * gp_spacing // 2
            
            for i, gp_id in enumerate(family["grandparents"][:4]):
                try:
                    gp = await self.bot.fetch_user(int(gp_id))
                    gp_name = gp.display_name[:10]
                    gp_x = start_x + i * gp_spacing
                    draw.rectangle([gp_x - 60, gp_y - 20, gp_x + 60, gp_y + 20], fill='#9B59B6', outline='white', width=2)
                    draw.text((gp_x, gp_y), gp_name, fill='white', font=font_small, anchor='mm')
                except:
                    pass
        
        # Add title
        draw.text((center_x, 750), f"{user_name}'s Family Tree", fill='white', font=font, anchor='mm')
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Send image
        file = discord.File(img_bytes, filename='family_tree.png')
        embed = discord.Embed(
            title=f"🌳 {interaction.user.display_name}'s Family Tree",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://family_tree.png")
        
        await interaction.followup.send(embed=embed, file=file)


    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in marriage command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Marriage(bot))
