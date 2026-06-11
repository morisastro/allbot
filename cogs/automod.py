"""Automoderacja (anty-invite, anty-link, anty-spam, zakazane slowa)
oraz logi serwera (usuniecia/edycje wiadomosci, wejscia/wyjscia)."""
import datetime
import re
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils

INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)", re.IGNORECASE)
LINK_RE = re.compile(r"https?://", re.IGNORECASE)


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # historia wiadomosci na uzytkownika do wykrywania spamu
        self.spam_tracker: dict[int, deque] = defaultdict(lambda: deque(maxlen=5))

    async def get_config(self, guild_id: int):
        row = await db.fetchrow("SELECT * FROM automod WHERE guild_id = $1", guild_id)
        if row is None:
            await db.execute("INSERT INTO automod (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
            row = await db.fetchrow("SELECT * FROM automod WHERE guild_id = $1", guild_id)
        return row

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.author.guild_permissions.manage_messages:
            return  # moderatorzy pomijani

        cfg = await self.get_config(message.guild.id)
        content = message.content.lower()

        async def punish(reason: str):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            try:
                await message.channel.send(
                    embed=utils.warning(f"{message.author.mention}, {reason}"),
                    delete_after=5,
                )
            except discord.HTTPException:
                pass

        # zakazane slowa
        if cfg["banned_words"]:
            for word in cfg["banned_words"]:
                if word.lower() in content:
                    return await punish("ta wiadomosc zawiera zabronione slowo.")

        if cfg["anti_invite"] and INVITE_RE.search(message.content):
            return await punish("zaproszenia na inne serwery sa zabronione.")

        if cfg["anti_link"] and LINK_RE.search(message.content):
            return await punish("linki sa zabronione na tym serwerze.")

        if cfg["anti_spam"]:
            now = time.time()
            tracker = self.spam_tracker[message.author.id]
            tracker.append(now)
            if len(tracker) == tracker.maxlen and (now - tracker[0]) < 5:
                tracker.clear()
                try:
                    await message.author.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=5))
                except discord.HTTPException:
                    pass
                return await punish("wykryto spam - zostales wyciszony na 5 minut.")

    # ---------- Logi serwera ----------
    async def get_log_channel(self, guild: discord.Guild):
        settings = await db.get_guild_settings(guild.id)
        if settings and settings["log_channel"]:
            return guild.get_channel(settings["log_channel"])
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        ch = await self.get_log_channel(message.guild)
        if ch:
            e = utils.info(title="Usunieto wiadomosc", description=message.content or "*brak tekstu*")
            e.add_field(name="Autor", value=message.author.mention)
            e.add_field(name="Kanal", value=message.channel.mention)
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        ch = await self.get_log_channel(before.guild)
        if ch:
            e = utils.info(title="Edytowano wiadomosc")
            e.add_field(name="Przed", value=(before.content or "*brak*")[:1000], inline=False)
            e.add_field(name="Po", value=(after.content or "*brak*")[:1000], inline=False)
            e.add_field(name="Autor", value=before.author.mention)
            e.add_field(name="Kanal", value=before.channel.mention)
            await ch.send(embed=e)

    # ---------- Komendy konfiguracji ----------
    automod_group = app_commands.Group(name="automod", description="Konfiguracja automoderacji.",
                                       default_permissions=discord.Permissions(manage_guild=True))

    @automod_group.command(name="toggle", description="Wlacza/wylacza dany filtr automoderacji.")
    @app_commands.describe(filtr="Ktory filtr", wartosc="Wlaczony?")
    @app_commands.choices(filtr=[
        app_commands.Choice(name="anty-zaproszenia", value="anti_invite"),
        app_commands.Choice(name="anty-linki", value="anti_link"),
        app_commands.Choice(name="anty-spam", value="anti_spam"),
    ])
    async def toggle(self, interaction: discord.Interaction, filtr: app_commands.Choice[str], wartosc: bool):
        await self.get_config(interaction.guild.id)
        await db.execute(
            f"UPDATE automod SET {filtr.value} = $2 WHERE guild_id = $1",
            interaction.guild.id, wartosc,
        )
        stan = "wlaczony" if wartosc else "wylaczony"
        await interaction.response.send_message(embed=utils.success(f"Filtr **{filtr.name}** jest teraz **{stan}**."))

    @automod_group.command(name="addword", description="Dodaje zabronione slowo.")
    @app_commands.describe(slowo="Slowo do zablokowania")
    async def addword(self, interaction: discord.Interaction, slowo: str):
        await self.get_config(interaction.guild.id)
        await db.execute(
            "UPDATE automod SET banned_words = array_append(banned_words, $2) WHERE guild_id = $1",
            interaction.guild.id, slowo.lower(),
        )
        await interaction.response.send_message(embed=utils.success(f"Dodano zabronione slowo: ||{slowo}||"), ephemeral=True)

    @automod_group.command(name="delword", description="Usuwa zabronione slowo.")
    @app_commands.describe(slowo="Slowo do odblokowania")
    async def delword(self, interaction: discord.Interaction, slowo: str):
        await self.get_config(interaction.guild.id)
        await db.execute(
            "UPDATE automod SET banned_words = array_remove(banned_words, $2) WHERE guild_id = $1",
            interaction.guild.id, slowo.lower(),
        )
        await interaction.response.send_message(embed=utils.success(f"Usunieto slowo z listy."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
