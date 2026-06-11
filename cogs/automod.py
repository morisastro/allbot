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
from i18n import t

INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)", re.IGNORECASE)
LINK_RE = re.compile(r"https?://", re.IGNORECASE)


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
            return

        cfg = await self.get_config(message.guild.id)
        content = message.content.lower()

        async def punish(reason: str):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            try:
                await message.channel.send(
                    embed=utils.warning(f"{message.author.mention}, {reason}"), delete_after=5,
                )
            except discord.HTTPException:
                pass

        if cfg["banned_words"]:
            for word in cfg["banned_words"]:
                if word.lower() in content:
                    return await punish(t("auto.banned_word"))

        if cfg["anti_invite"] and INVITE_RE.search(message.content):
            return await punish(t("auto.invite"))

        if cfg["anti_link"] and LINK_RE.search(message.content):
            return await punish(t("auto.link"))

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
                return await punish(t("auto.spam"))

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
            e = utils.info(title=t("auto.msg_deleted"), description=message.content or t("auto.no_text"))
            e.add_field(name=t("auto.author"), value=message.author.mention)
            e.add_field(name=t("auto.channel"), value=message.channel.mention)
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        ch = await self.get_log_channel(before.guild)
        if ch:
            e = utils.info(title=t("auto.msg_edited"))
            e.add_field(name=t("auto.before"), value=(before.content or t("auto.no_text"))[:1000], inline=False)
            e.add_field(name=t("auto.after"), value=(after.content or t("auto.no_text"))[:1000], inline=False)
            e.add_field(name=t("auto.author"), value=before.author.mention)
            e.add_field(name=t("auto.channel"), value=before.channel.mention)
            await ch.send(embed=e)

    automod_group = app_commands.Group(name="automod", description="Konfiguracja automoderacji. / Automod config.",
                                       default_permissions=discord.Permissions(manage_guild=True))

    @automod_group.command(name="toggle", description="Wlacza/wylacza filtr. / Toggles a filter.")
    @app_commands.describe(filtr="Filtr / Filter", wartosc="Wlaczony? / Enabled?")
    @app_commands.choices(filtr=[
        app_commands.Choice(name="anti-invite", value="anti_invite"),
        app_commands.Choice(name="anti-link", value="anti_link"),
        app_commands.Choice(name="anti-spam", value="anti_spam"),
    ])
    async def toggle(self, interaction: discord.Interaction, filtr: app_commands.Choice[str], wartosc: bool):
        await self.get_config(interaction.guild.id)
        await db.execute(f"UPDATE automod SET {filtr.value} = $2 WHERE guild_id = $1", interaction.guild.id, wartosc)
        state = t("auto.state_on") if wartosc else t("auto.state_off")
        await interaction.response.send_message(embed=utils.success(t("auto.filter_state", name=filtr.name, state=state)))

    @automod_group.command(name="addword", description="Dodaje zabronione slowo. / Adds a banned word.")
    @app_commands.describe(slowo="Slowo / Word")
    async def addword(self, interaction: discord.Interaction, slowo: str):
        await self.get_config(interaction.guild.id)
        await db.execute("UPDATE automod SET banned_words = array_append(banned_words, $2) WHERE guild_id = $1",
                         interaction.guild.id, slowo.lower())
        await interaction.response.send_message(embed=utils.success(t("auto.word_added")), ephemeral=True)

    @automod_group.command(name="delword", description="Usuwa zabronione slowo. / Removes a banned word.")
    @app_commands.describe(slowo="Slowo / Word")
    async def delword(self, interaction: discord.Interaction, slowo: str):
        await self.get_config(interaction.guild.id)
        await db.execute("UPDATE automod SET banned_words = array_remove(banned_words, $2) WHERE guild_id = $1",
                         interaction.guild.id, slowo.lower())
        await interaction.response.send_message(embed=utils.success(t("auto.word_removed")), ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
