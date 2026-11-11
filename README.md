# Discord Moderation, Fun, Ticket, and Giveaway Bot

ModMate Giveaway Bot is a Python Discord bot for server moderation, fun commands, private support tickets, and timed giveaways using `discord.py` slash commands, persistent JSON storage, permission checks, giveaway entry buttons, and automatic winner selection.

## Install

1. Install Python 3.10 or newer.
2. Create a Discord application and bot in the Discord Developer Portal.
3. Enable the Server Members Intent if your server requires member lookups for moderation commands.
4. Copy `.env.example` to `.env`.
5. Set `DISCORD_TOKEN` in `.env` to your bot token.
6. Optionally set `GUILD_ID` to a server ID. Guild command syncing is immediate for development; leaving it empty uses global command syncing.
7. Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

8. Invite the bot using the `bot` and `applications.commands` scopes.
9. Grant the bot the permissions required for moderation, channel management, message management, viewing channels, sending messages, managing messages, and managing roles or members as appropriate.
10. Start the bot:

```bash
python main.py
```

The bot creates `bot_data.json` when it first stores tickets or giveaways. Do not commit `.env` or `bot_data.json` to source control.

## Use

Use these slash commands in Discord:

- `/ping` checks bot response time.
- `/coinflip` returns Heads or Tails.
- `/8ball question:<question>` returns a random magic 8-ball answer.
- `/kick member:<member> reason:<reason>` kicks a member. Requires Kick Members.
- `/ban member:<member> reason:<reason>` bans a member. Requires Ban Members.
- `/timeout member:<member> minutes:<number> reason:<reason>` applies a temporary timeout from 1 to 40,320 minutes. Requires Moderate Members.
- `/clear amount:<number>` deletes 1 to 100 recent messages in a text channel. Requires Manage Messages.
- `/ticket` creates a private support ticket channel for the user.
- `/close-ticket` closes the current registered ticket. The ticket owner or staff with Manage Channels can use it.
- `/giveaway prize:<text> duration:<duration> winners:<number>` starts a giveaway. Requires Manage Server.

Giveaway durations use a number followed by `s`, `m`, `h`, or `d`, such as `30s`, `15m`, `2h`, or `3d`. Durations may be up to 30 days. Users enter or leave an active giveaway with its button. When the duration expires, the bot disables the button, selects the configured number of winners from eligible entries, and announces the result.

Ticket channels are visible to the ticket owner and the bot by default. Staff can join by adjusting the channel permissions or using their server permissions. Ticket and giveaway state is saved in `bot_data.json` and is restored after a restart.

---

More Discord bot projects by EnderDevelopment: https://github.com/EnderDevelopment

Project page: https://dash.enderdevelopment.com/community/29b8afd0-bdb8-484f-86cb-2d9a45d79a60?utm_source=github&utm_medium=readme&utm_campaign=auto_publish&utm_content=29b8afd0-bdb8-484f-86cb-2d9a45d79a60
