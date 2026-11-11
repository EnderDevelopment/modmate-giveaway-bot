import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = os.getenv("GUILD_ID", "").strip()
DATA_FILE = Path("bot_data.json")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
data_lock = asyncio.Lock()


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"tickets": {}, "giveaways": {}}
    try:
        loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {
            "tickets": loaded.get("tickets", {}),
            "giveaways": loaded.get("giveaways", {}),
        }
    except (OSError, json.JSONDecodeError):
        return {"tickets": {}, "giveaways": {}}


def save_data() -> None:
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(DATA_FILE)


data = load_data()


def parse_duration(value: str) -> timedelta:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        amount = int(value[:-1])
        unit = value[-1].lower()
    except (ValueError, IndexError) as exc:
        raise ValueError("Use a duration like 30s, 15m, 2h, or 3d.") from exc
    if amount < 1 or unit not in units:
        raise ValueError("Use a positive duration like 15m, 2h, or 3d.")
    duration = timedelta(seconds=amount * units[unit])
    if duration > timedelta(days=30):
        raise ValueError("Giveaway duration cannot exceed 30 days.")
    return duration


class GiveawayView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter giveaway", style=discord.ButtonStyle.primary, emoji="🎉",
        custom_id="giveaway:enter",
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.message is None:
            await interaction.response.send_message("This giveaway is unavailable.", ephemeral=True)
            return
        async with data_lock:
            giveaway = data["giveaways"].get(str(interaction.message.id))
            if not giveaway or giveaway.get("ended"):
                await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
                return
            user_id = str(interaction.user.id)
            if user_id in giveaway["entries"]:
                giveaway["entries"].remove(user_id)
                response = "Your entry has been removed."
            else:
                giveaway["entries"].append(user_id)
                response = "You are entered. Good luck!"
            save_data()
        await interaction.response.send_message(response, ephemeral=True)


async def complete_giveaway(message_id: str) -> None:
    async with data_lock:
        giveaway = data["giveaways"].get(message_id)
        if not giveaway or giveaway.get("ended"):
            return
        giveaway["ended"] = True
        entries = list(giveaway["entries"])
        winner_ids = random.sample(entries, min(giveaway["winners"], len(entries)))
        channel_id = giveaway["channel_id"]
        prize = giveaway["prize"]
        save_data()

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
    try:
        message = await channel.fetch_message(int(message_id))
        embed = message.embeds[0] if message.embeds else discord.Embed(title="Giveaway ended")
        embed.color = discord.Color.dark_grey()
        embed.description = f"**Prize:** {prize}\n**Entries:** {len(entries)}"
        await message.edit(embed=embed, view=None)
        if winner_ids:
            winners = ", ".join(f"<@{user_id}>" for user_id in winner_ids)
            await channel.send(f"Congratulations {winners}! You won **{prize}**.")
        else:
            await channel.send(f"The giveaway for **{prize}** ended with no entries.")
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


@tasks.loop(seconds=15)
async def giveaway_watcher() -> None:
    now = datetime.now(timezone.utc).timestamp()
    expired = [
        message_id
        for message_id, giveaway in data["giveaways"].items()
        if not giveaway.get("ended") and giveaway["ends_at"] <= now
    ]
    for message_id in expired:
        await complete_giveaway(message_id)


@giveaway_watcher.before_loop
async def before_giveaway_watcher() -> None:
    await bot.wait_until_ready()


@bot.event
async def setup_hook() -> None:
    bot.add_view(GiveawayView())
    if GUILD_ID.isdigit():
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    giveaway_watcher.start()


@bot.event
async def on_ready() -> None:
    print(f"Ready as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Check whether the bot is responding.")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)} ms")


@bot.tree.command(name="coinflip", description="Flip a coin.")
async def coinflip(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(random.choice(["Heads!", "Tails!"]))


@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question.")
@app_commands.describe(question="Your question")
async def eight_ball(interaction: discord.Interaction, question: str) -> None:
    answers = [
        "It is certain.", "Without a doubt.", "Yes, definitely.",
        "Outlook good.", "Ask again later.", "Cannot predict that now.",
        "Probably not.", "My sources say no.",
    ]
    await interaction.response.send_message(f"🎱 {random.choice(answers)}")


@bot.tree.command(name="kick", description="Kick a member from this server.")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(member="Member to kick", reason="Reason for the kick")
async def kick(
    interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"
) -> None:
    if member == interaction.user:
        await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
        return
    await member.kick(reason=f"{reason} (by {interaction.user})")
    await interaction.response.send_message(f"Kicked {member.mention}. Reason: {reason}")


@bot.tree.command(name="ban", description="Ban a member from this server.")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="Member to ban", reason="Reason for the ban")
async def ban(
    interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"
) -> None:
    if member == interaction.user:
        await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
        return
    await member.ban(reason=f"{reason} (by {interaction.user})")
    await interaction.response.send_message(f"Banned {member.mention}. Reason: {reason}")


@bot.tree.command(name="timeout", description="Temporarily timeout a member.")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(member="Member to timeout", minutes="Duration, from 1 to 40320 minutes", reason="Reason")
async def timeout_member(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided",
) -> None:
    if member == interaction.user or member.guild_permissions.administrator:
        await interaction.response.send_message("That member cannot be timed out by this command.", ephemeral=True)
        return
    await member.timeout(timedelta(minutes=minutes), reason=f"{reason} (by {interaction.user})")
    await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes. Reason: {reason}")


@bot.tree.command(name="clear", description="Delete recent messages in this channel.")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(amount="Number of messages to delete, from 1 to 100")
async def clear_messages(
    interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]
) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Use this in a server text channel.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)


@bot.tree.command(name="ticket", description="Open a private support ticket.")
async def ticket(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Tickets can only be opened in a server.", ephemeral=True)
        return
    existing_id = data["tickets"].get(str(interaction.user.id))
    if existing_id:
        existing = guild.get_channel(int(existing_id))
        if existing:
            await interaction.response.send_message(f"You already have a ticket: {existing.mention}", ephemeral=True)
            return
        async with data_lock:
            data["tickets"].pop(str(interaction.user.id), None)
            save_data()

    bot_member = guild.me
    if bot_member is None:
        await interaction.response.send_message("Could not check bot permissions in this server.", ephemeral=True)
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}"[:90],
        overwrites=overwrites,
        topic=f"Support ticket opened by {interaction.user} ({interaction.user.id})",
        reason=f"Support ticket opened by {interaction.user}",
    )
    async with data_lock:
        data["tickets"][str(interaction.user.id)] = channel.id
        save_data()
    await channel.send(f"{interaction.user.mention}, describe what you need help with. Staff can join by adjusting channel permissions.")
    await interaction.response.send_message(f"Your private ticket is open: {channel.mention}", ephemeral=True)


@bot.tree.command(name="close-ticket", description="Close the current support ticket.")
async def close_ticket(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel) or not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("Use this command inside a ticket channel.", ephemeral=True)
        return
    owner_id = next(
        (user_id for user_id, channel_id in data["tickets"].items() if int(channel_id) == interaction.channel.id),
        None,
    )
    if owner_id is None:
        await interaction.response.send_message("This channel is not a registered ticket.", ephemeral=True)
        return
    if str(interaction.user.id) != owner_id and not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)
        return
    channel = interaction.channel
    async with data_lock:
        data["tickets"].pop(owner_id, None)
        save_data()
    await interaction.response.send_message("Ticket closed. This channel will be deleted in 5 seconds.")
    await asyncio.sleep(5)
    await channel.delete(reason=f"Ticket closed by {interaction.user}")


@bot.tree.command(name="giveaway", description="Start a giveaway in this channel.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(prize="Giveaway prize", duration="For example 30m, 2h, or 3d", winners="Number of winners")
async def giveaway(
    interaction: discord.Interaction,
    prize: app_commands.Range[str, 1, 200],
    duration: str,
    winners: app_commands.Range[int, 1, 20] = 1,
) -> None:
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message("Giveaways can only be started in a server.", ephemeral=True)
        return
    try:
        ends_at = datetime.now(timezone.utc) + parse_duration(duration)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    embed = discord.Embed(
        title="🎉 Giveaway",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(ends_at.timestamp())}:R>",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Hosted by {interaction.user}")
    await interaction.response.defer()
    message = await interaction.channel.send(embed=embed, view=GiveawayView())
    async with data_lock:
        data["giveaways"][str(message.id)] = {
            "channel_id": interaction.channel.id,
            "prize": prize,
            "winners": winners,
            "ends_at": ends_at.timestamp(),
            "entries": [],
            "ended": False,
        }
        save_data()
    await interaction.followup.send(f"Giveaway started: {message.jump_url}", ephemeral=True)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "You do not have permission to use that command."
    elif isinstance(error, app_commands.BotMissingPermissions):
        message = "I am missing a required server permission for that action."
    elif isinstance(error, app_commands.CommandInvokeError):
        message = "The command failed. Check my role hierarchy and channel permissions."
    else:
        message = "The command could not be completed."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your .env file before starting the bot.")
    bot.run(TOKEN)
