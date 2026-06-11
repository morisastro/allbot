"""Moderacja - ban, kick, timeout, warn, purge, slowmode, lock/unlock."""
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_action(self, guild: discord.Guild, embed: discord.Embed):
        settings = await db.get_guild_settings(guild.id)
        if settings and settings["log_channel"]:
            ch = guild.get_channel(settings["log_channel"])
            if ch:
                try:
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass

    @app_commands.command(name="ban", description="Banuje uzytkownika z serwera.")
    @app_commands.describe(user="Kogo zbanowac", reason="Powod")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Brak powodu"):
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(
                embed=utils.error("Nie mozesz banowac kogos z rownie wysoka lub wyzsza rola."), ephemeral=True
            )
        try:
            await user.send(embed=utils.warning(f"Zostales zbanowany na **{interaction.guild.name}**.\nPowod: {reason}"))
        except discord.HTTPException:
            pass
        await user.ban(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(
            embed=utils.success(f"{user.mention} zostal zbanowany.\n**Powod:** {reason}")
        )
        await self.log_action(interaction.guild, utils.info(
            f"**Ban**\nUzytkownik: {user} ({user.id})\nModerator: {interaction.user.mention}\nPowod: {reason}",
            title="Log moderacji",
        ))

    @app_commands.command(name="unban", description="Odbanowuje uzytkownika (po ID).")
    @app_commands.describe(user_id="ID uzytkownika", reason="Powod")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Brak powodu"):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message(embed=utils.error("Nie znaleziono uzytkownika o tym ID."), ephemeral=True)
        try:
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        except discord.NotFound:
            return await interaction.response.send_message(embed=utils.error("Ten uzytkownik nie jest zbanowany."), ephemeral=True)
        await interaction.response.send_message(embed=utils.success(f"Odbanowano {user.mention}."))

    @app_commands.command(name="kick", description="Wyrzuca uzytkownika z serwera.")
    @app_commands.describe(user="Kogo wyrzucic", reason="Powod")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Brak powodu"):
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(
                embed=utils.error("Nie mozesz wyrzucic kogos z rownie wysoka lub wyzsza rola."), ephemeral=True
            )
        try:
            await user.send(embed=utils.warning(f"Zostales wyrzucony z **{interaction.guild.name}**.\nPowod: {reason}"))
        except discord.HTTPException:
            pass
        await user.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=utils.success(f"{user.mention} zostal wyrzucony.\n**Powod:** {reason}"))
        await self.log_action(interaction.guild, utils.info(
            f"**Kick**\nUzytkownik: {user} ({user.id})\nModerator: {interaction.user.mention}\nPowod: {reason}",
            title="Log moderacji",
        ))

    @app_commands.command(name="timeout", description="Wycisza uzytkownika na okreslony czas (w minutach).")
    @app_commands.describe(user="Kogo wyciszyc", minutes="Na ile minut (max 40320 = 28 dni)", reason="Powod")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "Brak powodu"):
        if minutes < 1 or minutes > 40320:
            return await interaction.response.send_message(embed=utils.error("Czas musi byc miedzy 1 a 40320 minut."), ephemeral=True)
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await user.timeout(until, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(
            embed=utils.success(f"{user.mention} wyciszony na **{minutes} min**.\n**Powod:** {reason}")
        )
        await self.log_action(interaction.guild, utils.info(
            f"**Timeout** ({minutes} min)\nUzytkownik: {user} ({user.id})\nModerator: {interaction.user.mention}\nPowod: {reason}",
            title="Log moderacji",
        ))

    @app_commands.command(name="untimeout", description="Zdejmuje wyciszenie z uzytkownika.")
    @app_commands.describe(user="Komu zdjac wyciszenie")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member):
        await user.timeout(None)
        await interaction.response.send_message(embed=utils.success(f"Zdjeto wyciszenie z {user.mention}."))

    @app_commands.command(name="warn", description="Daje ostrzezenie uzytkownikowi.")
    @app_commands.describe(user="Kogo ostrzec", reason="Powod")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Brak powodu"):
        await db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason) VALUES ($1, $2, $3, $4)",
            interaction.guild.id, user.id, interaction.user.id, reason,
        )
        count = await db.fetchval(
            "SELECT COUNT(*) FROM warns WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, user.id,
        )
        await interaction.response.send_message(
            embed=utils.success(f"{user.mention} otrzymal ostrzezenie (lacznie: **{count}**).\n**Powod:** {reason}")
        )
        try:
            await user.send(embed=utils.warning(f"Otrzymales ostrzezenie na **{interaction.guild.name}**.\nPowod: {reason}"))
        except discord.HTTPException:
            pass

    @app_commands.command(name="warnings", description="Pokazuje ostrzezenia uzytkownika.")
    @app_commands.describe(user="Czyje ostrzezenia")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        rows = await db.fetch(
            "SELECT * FROM warns WHERE guild_id = $1 AND user_id = $2 ORDER BY created_at DESC LIMIT 15",
            interaction.guild.id, user.id,
        )
        if not rows:
            return await interaction.response.send_message(embed=utils.info(f"{user.mention} nie ma ostrzezen."), ephemeral=True)
        e = utils.info(title=f"Ostrzezenia: {user}")
        for r in rows:
            mod = interaction.guild.get_member(r["moderator_id"])
            mod_name = mod.mention if mod else f"<@{r['moderator_id']}>"
            e.add_field(
                name=f"#{r['id']} - {r['created_at'].strftime('%Y-%m-%d %H:%M')}",
                value=f"Powod: {r['reason']}\nModerator: {mod_name}",
                inline=False,
            )
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="delwarn", description="Usuwa ostrzezenie po ID.")
    @app_commands.describe(warn_id="ID ostrzezenia")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def delwarn(self, interaction: discord.Interaction, warn_id: int):
        result = await db.execute(
            "DELETE FROM warns WHERE id = $1 AND guild_id = $2", warn_id, interaction.guild.id
        )
        if result.endswith("0"):
            return await interaction.response.send_message(embed=utils.error("Nie znaleziono takiego ostrzezenia."), ephemeral=True)
        await interaction.response.send_message(embed=utils.success(f"Usunieto ostrzezenie #{warn_id}."))

    @app_commands.command(name="purge", description="Usuwa okreslona liczbe wiadomosci.")
    @app_commands.describe(amount="Ile wiadomosci usunac (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message(embed=utils.error("Podaj liczbe od 1 do 100."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=utils.success(f"Usunieto **{len(deleted)}** wiadomosci."), ephemeral=True)

    @app_commands.command(name="slowmode", description="Ustawia tryb powolny na kanale (w sekundach).")
    @app_commands.describe(seconds="Liczba sekund (0 = wylacz, max 21600)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message(embed=utils.error("Podaj wartosc 0-21600."), ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message(embed=utils.success("Tryb powolny wylaczony."))
        else:
            await interaction.response.send_message(embed=utils.success(f"Tryb powolny: **{seconds}s**."))

    @app_commands.command(name="lock", description="Blokuje pisanie na kanale dla @everyone.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=utils.success("Kanal zablokowany."))

    @app_commands.command(name="unlock", description="Odblokowuje pisanie na kanale.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=utils.success("Kanal odblokowany."))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
