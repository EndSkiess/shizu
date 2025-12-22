"""
Shop & Inventory System - Buy items, manage inventory, and trade with others
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from .shop_utils import (
    load_shop_items, get_user_inventory, add_item_to_inventory,
    remove_item_from_inventory, has_item, get_items_by_category,
    activate_luck_boost, add_badge, get_active_luck_boost
)

# Try to import economy utils
try:
    from .economy_utils import get_balance, remove_balance, add_balance, CURRENCY_NAME
    ECONOMY_AVAILABLE = True
except ImportError:
    ECONOMY_AVAILABLE = False

logger = logging.getLogger('DiscordBot.Shop')


class Shop(commands.Cog):
    """Shop and inventory management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="shop", description="Browse the shop")
    @app_commands.describe(category="Filter by category (role, color, perk, luck, badge)")
    async def shop(self, interaction: discord.Interaction, category: Optional[str] = None):
        """Display shop items"""
        # Validate category
        valid_categories = ["role", "color", "luck", "badge"]
        if category and category.lower() not in valid_categories:
            await interaction.response.send_message(
                f"❌ Invalid category! Choose from: {', '.join(valid_categories)}",
                ephemeral=True
            )
            return
        
        embed = self.create_shop_embed(category)
        view = ShopView(category)
        await interaction.response.send_message(embed=embed, view=view)

    def create_shop_embed(self, category: Optional[str] = None) -> discord.Embed:
        items = get_items_by_category(category.lower() if category else None)
        
        if not items:
            return discord.Embed(title="🛒 Shop", description="❌ No items found!", color=discord.Color.red())
        
        # Group items by category
        categories = {}
        for item_id, item in items.items():
            cat = item.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((item_id, item))
        
        # Create embed
        embed = discord.Embed(
            title="🛒 Shop",
            description=f"Use `/buy <item_id>` to purchase items\n{f'**Category:** {category.title()}' if category else '**All Categories**'}",
            color=discord.Color.blue()
        )
        
        # Category emojis and order
        cat_config = {
            "badge": "<:goldredgunsbadge:1442767350372892834>",
            "color": "<a:flowers:1442767348091322389>",
            "luck": "<a:clover:1442767346467864576>",
            "role": "<:bluecrown:1442767352306466971>",
            "perk": "<a:thunder:1442767344538484817>"
        }
        
        # Sort categories by defined order, then alphabetically for others
        sorted_cats = sorted(categories.items(), key=lambda x: (list(cat_config.keys()).index(x[0]) if x[0] in cat_config else 999, x[0]))

        for cat, cat_items in sorted_cats:
            items_text = []
            for item_id, item in cat_items[:5]:  # Limit to 5 items per category
                emoji = item.get("emoji", "")
                price = item.get("price", 0)
                # Code block format
                items_text.append(f"```\n{emoji} {item['name']}\nPrice: {price:,}\nID: {item_id}\n```")
            
            if items_text:
                embed.add_field(
                    name=f"{cat_config.get(cat, '📦')} {cat.title()}",
                    value="\n".join(items_text),
                    inline=True
                )
        
        return embed

class ShopSelect(discord.ui.Select):
    def __init__(self, current_category: Optional[str] = None):
        options = [
            discord.SelectOption(
                label="Badges", 
                value="badge", 
                description="Show badges",
                emoji=discord.PartialEmoji.from_str("<:goldredgunsbadge:1442767350372892834>"),
                default=current_category == "badge"
            ),
            discord.SelectOption(
                label="Colors", 
                value="color", 
                description="Show role colors",
                emoji=discord.PartialEmoji.from_str("<a:flowers:1442767348091322389>"),
                default=current_category == "color"
            ),
            discord.SelectOption(
                label="Luck", 
                value="luck", 
                description="Show luck items",
                emoji=discord.PartialEmoji.from_str("<a:clover:1442767346467864576>"),
                default=current_category == "luck"
            ),
            discord.SelectOption(
                label="Roles", 
                value="role", 
                description="Show custom roles",
                emoji=discord.PartialEmoji.from_str("<:bluecrown:1442767352306466971>"),
                default=current_category == "role"
            ),
             discord.SelectOption(
                label="Perks", 
                value="perk", 
                description="Show perks",
                emoji=discord.PartialEmoji.from_str("<a:thunder:1442767344538484817>"),
                default=current_category == "perk"
            )
        ]
        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "all":
            category = None
        
        # Get the cog to access the create_shop_embed method
        # We can find the cog from the interaction's client if needed, 
        # but since this is a view, we might not have direct access to the cog instance easily 
        # unless we pass it or use the bot instance.
        # Actually, we can just instantiate the embed logic here or make the method static/standalone.
        # For simplicity, let's assume the View has access or we move the logic.
        
        # Better approach: The View should handle the update.
        await self.view.update_shop(interaction, category)

class ShopView(discord.ui.View):
    def __init__(self, current_category: Optional[str] = None):
        super().__init__(timeout=180)
        self.current_category = current_category
        self.add_item(ShopSelect(current_category))
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions"""
        import logging
        logger = logging.getLogger('DiscordBot.ShopView')
        logger.error(f"Error in ShopView: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred processing this action.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred processing this action.", ephemeral=True)
        except:
            pass

    async def update_shop(self, interaction: discord.Interaction, category: Optional[str]):
        self.current_category = category
        # Re-create the view to update the default option
        self.clear_items()
        self.add_item(ShopSelect(category))
        
        # We need to generate the embed. 
        # Since the logic is in the Cog, we need a way to call it.
        # We can pass the create_shop_embed function to the View or import it if it was standalone.
        # Let's move create_shop_embed to be a standalone function in this file or a static method.
        # For now, I'll access it via the bot if possible, or just duplicate/move the logic.
        # Actually, let's just make `create_shop_embed` a standalone function outside the class 
        # so both the Cog and the View can use it.
        
        embed = create_shop_embed(category)
        await interaction.response.edit_message(embed=embed, view=self)

# Helper function for embed generation (moved outside class)
def create_shop_embed(category: Optional[str] = None) -> discord.Embed:
    items = get_items_by_category(category.lower() if category else None)
    
    if not items:
        return discord.Embed(title="🛒 Shop", description="❌ No items found!", color=discord.Color.red())
    
    # Group items by category
    categories = {}
    for item_id, item in items.items():
        cat = item.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((item_id, item))
    
    # Create embed
    embed = discord.Embed(
        title="🛒 Shop",
        description=f"Use `/buy <item_id>` to purchase items\n{f'**Category:** {category.title()}' if category else '**All Categories**'}",
        color=discord.Color.blue()
    )
    
    # Category emojis and order
    cat_config = {
        "badge": "🏆",
        "color": "🎨",
        "luck": "🍀",
        "role": "👑",
        "perk": "⚡"
    }
    
    # Sort categories by defined order, then alphabetically for others
    sorted_cats = sorted(categories.items(), key=lambda x: (list(cat_config.keys()).index(x[0]) if x[0] in cat_config else 999, x[0]))

    for cat, cat_items in sorted_cats:
        items_text = []
        for item_id, item in cat_items[:5]:  # Limit to 5 items per category
            emoji = item.get("emoji", "")
            price = item.get("price", 0)
            # Code block format
            items_text.append(f"```\n{emoji} {item['name']}\nPrice: {price:,}\nID: {item_id}\n```")
        
        if items_text:
            embed.add_field(
                name=f"{cat_config.get(cat, '📦')} {cat.title()}",
                value="\n".join(items_text),
                inline=True
            )
    
    return embed
    
    @app_commands.command(name="buy", description="Purchase an item from the shop")
    @app_commands.describe(item_id="ID of the item to purchase")
    async def buy(self, interaction: discord.Interaction, item_id: str):
        """Buy an item from the shop"""
        if not ECONOMY_AVAILABLE:
            await interaction.response.send_message("❌ Economy system not available!", ephemeral=True)
            return
        
        # Get item
        shop_data = load_shop_items()
        item = shop_data["items"].get(item_id)
        
        if not item:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        
        price = item["price"]
        
        # Check balance
        balance = await get_balance(interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                f"❌ Insufficient balance! You need {price:,} {CURRENCY_NAME} but have {balance:,} {CURRENCY_NAME}.",
                ephemeral=True
            )
            return
        
        # Handle custom role purchase
        if item["category"] == "role":
            await interaction.response.send_message(
                "Please enter the name for your custom role:",
                ephemeral=True
            )
            # Note: This would need a modal or message collector for the role name
            # For now, we'll skip the actual role creation
            return
        
        # Deduct balance
        await remove_balance(interaction.user.id, price)
        
        # Add item to inventory
        add_item_to_inventory(interaction.user.id, item_id)
        
        # Handle different item types
        if item["category"] == "badge":
            add_badge(interaction.user.id, item_id)
        
        new_balance = await get_balance(interaction.user.id)
        
        embed = discord.Embed(
            title="✅ Purchase Successful!",
            description=f"You bought **{item['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Price", value=f"{price:,} {CURRENCY_NAME}", inline=True)
        embed.add_field(name="New Balance", value=f"{new_balance:,} {CURRENCY_NAME}", inline=True)
        
        if item["type"] == "consumable":
            embed.set_footer(text="Use /use to activate this item")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        """Display user's inventory"""
        inventory = get_user_inventory(interaction.user.id)
        shop_data = load_shop_items()
        
        if not inventory["items"] and not inventory["badges"]:
            await interaction.response.send_message("📭 Your inventory is empty!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        
        # Show items
        if inventory["items"]:
            items_text = []
            for item_id, item_data in list(inventory["items"].items())[:10]:
                item = shop_data["items"].get(item_id)
                if item:
                    emoji = item.get("emoji", "")
                    qty = item_data["quantity"]
                    uses = item_data.get("uses_remaining", "")
                    uses_text = f" ({uses} uses left)" if uses else ""
                    items_text.append(f"{emoji} **{item['name']}** x{qty}{uses_text}")
            
            if items_text:
                embed.add_field(
                    name="Items",
                    value="\n".join(items_text),
                    inline=False
                )
        
        
        if "luck_boost" in inventory["active_perks"]:
            boost = inventory["active_perks"]["luck_boost"]["boost"]
            uses = inventory["active_perks"]["luck_boost"]["uses_remaining"]
            active_perks.append(f"🍀 +{int(boost*100)}% Luck ({uses} uses)")
        
        if active_perks:
            embed.add_field(
                name="Active Perks",
                value="\n".join(active_perks),
                inline=False
            )
        
        # Show badges
        if inventory["badges"]:
            badges_text = []
            for badge_id in inventory["badges"][:10]:
                item = shop_data["items"].get(badge_id)
                if item:
                    emoji = item.get("emoji", "")
                    badges_text.append(f"{emoji} {item['name']}")
            
            if badges_text:
                embed.add_field(
                    name="Badges",
                    value="\n".join(badges_text),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="use", description="Use/activate an item from your inventory")
    @app_commands.describe(item_id="ID of the item to use")
    async def use(self, interaction: discord.Interaction, item_id: str):
        """Use a consumable item"""
        # Check if user has the item
        if not has_item(interaction.user.id, item_id):
            await interaction.response.send_message("❌ You don't have this item!", ephemeral=True)
            return
        
        shop_data = load_shop_items()
        item = shop_data["items"].get(item_id)
        
        if not item:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        
        if item["type"] != "consumable":
            await interaction.response.send_message("❌ This item cannot be used!", ephemeral=True)
            return
        
        # Handle different item categories
        if item["category"] == "luck":
            # Activate luck boost
            activate_luck_boost(interaction.user.id, item_id)
            remove_item_from_inventory(interaction.user.id, item_id)
            
            boost = item["luck_boost"]
            uses = item["uses"]
            
            embed = discord.Embed(
                title="🍀 Luck Boost Activated!",
                description=f"**+{int(boost*100)}%** win chance on gambling",
                color=discord.Color.green()
            )
            embed.add_field(name="Uses Remaining", value=str(uses))
            
            if item.get("game_specific"):
                embed.add_field(name="Game", value=item["game_specific"].title())
            else:
                embed.add_field(name="Game", value="All gambling games")
            
            await interaction.response.send_message(embed=embed)
        
        else:
            await interaction.response.send_message("❌ This item cannot be used!", ephemeral=True)
    
    @app_commands.command(name="sell", description="Sell an item from your inventory")
    @app_commands.describe(item_id="ID of the item to sell")
    async def sell(self, interaction: discord.Interaction, item_id: str):
        """Sell an item for 50% of its value"""
        if not ECONOMY_AVAILABLE:
            await interaction.response.send_message("❌ Economy system not available!", ephemeral=True)
            return
        
        # Check if user has the item
        if not has_item(interaction.user.id, item_id):
            await interaction.response.send_message("❌ You don't have this item!", ephemeral=True)
            return
        
        shop_data = load_shop_items()
        item = shop_data["items"].get(item_id)
        
        if not item:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        
        # Calculate sell price (50% of original)
        sell_price = item["price"] // 2
        
        # Remove item and add money
        remove_item_from_inventory(interaction.user.id, item_id)
        new_balance = await add_balance(interaction.user.id, sell_price)
        
        embed = discord.Embed(
            title="💰 Item Sold!",
            description=f"You sold **{item['name']}** for **{sell_price:,}** {CURRENCY_NAME}",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"{new_balance:,} {CURRENCY_NAME}")
        
        await interaction.response.send_message(embed=embed)



    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in application commands"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            logger.error(f"Error in shop command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while processing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Shop(bot))
