"""Glowny plik bota Discord - laduje wszystkie moduly (cogi) i synchronizuje slash commands.

Uruchomienie lokalnie:  python bot.py
Na Railway: uruchamia sie automatycznie (Procfile).
"""
import asyncio
import logging
import os

import discord
from discord.ext import commands

import config
import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

# Lista cogow do zaladowania
INITIAL_EXTENSIONS = [
    "cogs.moderation",
    "cogs.automod",
    "cogs.welcome",
    "cogs.leveling",
    "cogs.economy",
    "cogs.reaction_roles",
    "cogs.tickets",
    "cogs.utility",
    "cogs.fun",
]


class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True   # potrzebne do automod, leveling, afk
        intents.members = True           # potrzebne do powitan, autorole
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Globalna obsluga bledow slash commands
        self.tree.error(self.on_app_command_error)

        # 1. Baza danych
        await database.setup()
        log.info("Polaczono z baza danych.")

        # 2. Ladowanie cogow
        for ext in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Zaladowano %s", ext)
            except Exception as e:
                log.exception("Blad ladowania %s: %s", ext, e)

        # 3. Synchronizacja slash commands
        if config.GUILD_ID:
            guild = discord.Object(id=int(config.GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Zsynchronizowano %d komend na serwerze %s", len(synced), config.GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Zsynchronizowano %d komend globalnie", len(synced))

    async def on_ready(self):
        log.info("Zalogowano jako %s (ID: %s)", self.user, self.user.id)
        log.info("Serwery: %d", len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"/help | {len(self.guilds)} serwerow",
            )
        )

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        import utils
        from discord import app_commands

        if isinstance(error, app_commands.MissingPermissions):
            msg = "Nie masz wymaganych uprawnien do tej komendy."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "Bot nie ma wymaganych uprawnien. Sprawdz jego role."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Poczekaj jeszcze {error.retry_after:.0f}s."
        else:
            log.exception("Blad komendy: %s", error)
            msg = "Wystapil blad podczas wykonywania komendy."

        embed = utils.error(msg)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    async def close(self):
        await database.close()
        await super().close()


async def main():
    missing = config.validate()
    if missing:
        log.error("Brakuje wymaganych zmiennych srodowiskowych: %s", ", ".join(missing))
        log.error("Uzupelnij je w pliku .env (lokalnie) lub w panelu Railway -> Variables.")
        raise SystemExit(1)

    bot = DiscordBot()
    async with bot:
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
