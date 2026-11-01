import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
PREFIX = "!"
COOLDOWN_SECONDS = 7
DAILY_AMOUNT = 150
# ============================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ========== In-memory Storage (Render restart e reset hobe) ==========
cooldowns = {}
economy = defaultdict(lambda: {"coins": 0, "last_daily": None})
favorites = defaultdict(list)          # user_id: [gallery_ids]
# =====================================================================

def check_cooldown(user_id: int):
    now = datetime.utcnow()
    if user_id in cooldowns and now < cooldowns[user_id]:
        remaining = (cooldowns[user_id] - now).seconds
        return False, remaining
    cooldowns[user_id] = now + timedelta(seconds=COOLDOWN_SECONDS)
    return True, 0

async def fetch_rule34(tags: str = "", limit: int = 1):
    tags = tags.strip().replace(" ", "_") if tags else ""
    url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit=50&tags={tags}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            if not data:
                return []
            return random.sample(data, min(limit, len(data)))

async def fetch_nhentai_search(query: str):
    url = f"https://nhentai.net/api/galleries/search?query={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("result", [])
                return results[0] if results else None
        except:
            return None

async def fetch_nhentai_gallery(gallery_id: str):
    url = f"https://nhentai.net/api/gallery/{gallery_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except:
            return None

def get_nh_cover(media_id):
    return f"https://t.nhentai.net/galleries/{media_id}/cover.jpg"

def get_nh_page(media_id, page, ext="jpg"):
    return f"https://i.nhentai.net/galleries/{media_id}/{page}.{ext}"

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Mia online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print("Slash sync error:", e)

# ================== RULE34 ==================
@bot.command(name="r34")
async def r34_prefix(ctx, *, args: str = None):
    if not ctx.channel.is_nsfw():
        return await ctx.send("❌ Ei command shudhu **NSFW channel**-e kaj kore.")

    ok, remaining = check_cooldown(ctx.author.id)
    if not ok:
        return await ctx.send(f"⏳ Ektu wait koro... **{remaining}s**")

    limit = 1
    tags = ""

    if args:
        parts = args.rsplit(" ", 1)
        if parts[-1].isdigit() and 1 <= int(parts[-1]) <= 5:
            limit = int(parts[-1])
            tags = parts[0] if len(parts) > 1 else ""
        else:
            tags = args

    await ctx.typing()
    posts = await fetch_rule34(tags, limit)

    if not posts:
        return await ctx.send("Kichu paowa gelo na re...")

    for post in posts:
        embed = discord.Embed(color=0xFF6B9D)
        embed.set_image(url=post.get("file_url") or post.get("sample_url"))
        embed.set_footer(text=f"Requested by {ctx.author.display_name} • Rule34")
        await ctx.send(embed=embed)

@bot.tree.command(name="r34", description="Rule34 theke image ano")
@app_commands.describe(tags="Character/tags", amount="1-5 ta image")
async def r34_slash(interaction: discord.Interaction, tags: str = "", amount: int = 1):
    if not interaction.channel.is_nsfw():
        return await interaction.response.send_message("❌ NSFW channel e use koro.", ephemeral=True)

    amount = max(1, min(5, amount))
    ok, remaining = check_cooldown(interaction.user.id)
    if not ok:
        return await interaction.response.send_message(f"⏳ {remaining}s wait koro.", ephemeral=True)

    await interaction.response.defer()
    posts = await fetch_rule34(tags, amount)

    if not posts:
        return await interaction.followup.send("Kichu paowa gelo na.")

    for post in posts:
        embed = discord.Embed(color=0xFF6B9D)
        embed.set_image(url=post.get("file_url") or post.get("sample_url"))
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

@bot.command(name="random")
async def random_r34(ctx):
    await r34_prefix(ctx, args="")

# ================== MANHWA / NHENTAI ==================
@bot.command(name="manhwa", aliases=["nh", "doujin"])
async def manhwa_cmd(ctx, action: str = None, *, query: str = None):
    if not ctx.channel.is_nsfw():
        return await ctx.send("❌ NSFW channel e use koro.")

    ok, remaining = check_cooldown(ctx.author.id)
    if not ok:
        return await ctx.send(f"⏳ {remaining}s wait koro.")

    await ctx.typing()

    # Random
    if action and action.lower() == "random":
        gallery = await fetch_nhentai_search("pages:>20")
        if not gallery:
            return await ctx.send("Random manhwa paowa gelo na.")
        title = gallery.get("title", {}).get("pretty") or "Unknown"
        media_id = gallery.get("media_id")
        gid = gallery.get("id")
        embed = discord.Embed(title=title, url=f"https://nhentai.net/g/{gid}/", color=0xFF6B9D)
        embed.set_image(url=get_nh_cover(media_id))
        embed.set_footer(text=f"ID: {gid} • Requested by {ctx.author.display_name}")
        return await ctx.send(embed=embed)

    # Page view: !manhwa page <id> <page>
    if action and action.lower() == "page" and query:
        parts = query.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            gid, page = parts[0], int(parts[1])
            gallery = await fetch_nhentai_gallery(gid)
            if not gallery:
                return await ctx.send("Gallery paowa gelo na.")
            media_id = gallery.get("media_id")
            total = gallery.get("num_pages", 1)
            if page < 1 or page > total:
                return await ctx.send(f"Page 1 theke {total} porjonto.")
            ext = "jpg"
            # simple extension guess
            embed = discord.Embed(title=f"Page {page}/{total}", color=0xFF6B9D)
            embed.set_image(url=get_nh_page(media_id, page, ext))
            embed.set_footer(text=f"ID: {gid}")
            return await ctx.send(embed=embed)

    # Normal search
    search_query = action if not query else f"{action} {query}"
    if not search_query:
        return await ctx.send("Naam dao ba `random` likho.\nExample: `!manhwa secret class` ba `!manhwa random`")

    gallery = await fetch_nhentai_search(search_query)
    if not gallery:
        return await ctx.send("Kichu paowa gelo na.")

    title = gallery.get("title", {}).get("pretty") or gallery.get("title", {}).get("english") or "Unknown"
    media_id = gallery.get("media_id")
    gid = gallery.get("id")
    pages = gallery.get("num_pages", "?")

    embed = discord.Embed(
        title=title,
        url=f"https://nhentai.net/g/{gid}/",
        description=f"**Pages:** {pages}\n**ID:** `{gid}`",
        color=0xFF6B9D
    )
    embed.set_image(url=get_nh_cover(media_id))
    embed.set_footer(text=f"Requested by {ctx.author.display_name} • !manhwa page {gid} 1")
    await ctx.send(embed=embed)

# ================== ECONOMY ==================
@bot.command(name="daily")
async def daily(ctx):
    user = economy[ctx.author.id]
    now = datetime.utcnow()

    if user["last_daily"] and (now - user["last_daily"]).total_seconds() < 86400:
        remaining = 86400 - (now - user["last_daily"]).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        return await ctx.send(f"Aagei niyeso! Abar **{hours}h {minutes}m** pore aasba.")

    user["coins"] += DAILY_AMOUNT
    user["last_daily"] = now
    await ctx.send(f"🎁 **+{DAILY_AMOUNT}** coins pelo!\nEkhon tomar kache **{user['coins']}** coins ache.")

@bot.command(name="balance", aliases=["bal", "coins"])
async def balance(ctx):
    coins = economy[ctx.author.id]["coins"]
    await ctx.send(f"💰 **{ctx.author.display_name}**, tomar kache **{coins}** coins ache.")

# ================== PROFILE & FAVORITE ==================
@bot.command(name="profile")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = economy[member.id]
    favs = favorites[member.id]

    embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0xFF6B9D)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Coins", value=f"💰 {data['coins']}", inline=True)
    embed.add_field(name="Favorites", value=f"❤️ {len(favs)}", inline=True)
    embed.set_footer(text="Mia Bot")
    await ctx.send(embed=embed)

@bot.command(name="fav")
async def fav_cmd(ctx, action: str = None, *, gallery_id: str = None):
    uid = ctx.author.id

    if action == "list" or action is None:
        favs = favorites[uid]
        if not favs:
            return await ctx.send("Tumi akhono kichu favorite koro nai.")
        await ctx.send("❤️ **Tomar Favorites:**\n" + "\n".join([f"`{fid}`" for fid in favs[:15]]))
        return

    if not gallery_id or not gallery_id.isdigit():
        return await ctx.send("Sothik Gallery ID dao.\nExample: `!fav add 123456`")

    if action == "add":
        if gallery_id in favorites[uid]:
            return await ctx.send("Eita already favorite e ache.")
        favorites[uid].append(gallery_id)
        await ctx.send(f"✅ `{gallery_id}` favorite e add holo!")
    elif action == "remove":
        if gallery_id in favorites[uid]:
            favorites[uid].remove(gallery_id)
            await ctx.send(f"❌ `{gallery_id}` remove holo.")
        else:
            await ctx.send("Eita tomar favorite list e nai.")
    else:
        await ctx.send("Usage: `!fav add/remove/list <id>`")

# ================== HELP ==================
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🌸 Mia Help",
        description="NSFW commands gulr list:",
        color=0xFF6B9D
    )
    embed.add_field(
        name="🖼 Rule34",
        value="`!r34 <tags> [1-5]`\n`!random`\n`/r34`",
        inline=False
    )
    embed.add_field(
        name="📖 Manhwa / Doujin",
        value="`!manhwa <name>`\n`!manhwa random`\n`!manhwa page <id> <page>`\n`!nh` `!doujin`",
        inline=False
    )
    embed.add_field(
        name="💰 Economy",
        value="`!daily` `!balance` `!profile`",
        inline=False
    )
    embed.add_field(
        name="❤️ Favorites",
        value="`!fav add/remove/list <id>`",
        inline=False
    )
    embed.set_footer(text="Shudhu NSFW channel e kaj kore")
    await ctx.send(embed=embed)

# ================== RUN ==================
if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ BOT_TOKEN set koro!")
    bot.run(BOT_TOKEN)