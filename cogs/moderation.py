"""Moderacja - ban, kick, timeout, warn, purge, slowmode, lock/unlock."""
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils
from i18n import t


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

    @app_commands.command(name="ban", description="Banuje uzytkownika z serwera. / Bans a user.")
    @app_commands.describe(user="Kogo zbanowac / Who to ban", reason="Powod / Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "-"):
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(embed=utils.error(t("mod.hierarchy")), ephemeral=True)
        try:
            await user.send(embed=utils.warning(t("mod.dm_banned", guild=interaction.guild.name, reason=reason)))
        except discord.HTTPException:
            pass
        await user.ban(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=utils.success(t("mod.banned", user=user.mention, reason=reason)))
        await self.log_action(interaction.guild, utils.info(
            t("mod.log_ban", user=user, id=user.id, mod=interaction.user.mention, reason=reason),
            title=t("mod.log_title"),
        ))

    @app_commands.command(name="unban", description="Odbanowuje uzytkownika (po ID). / Unbans a user by ID.")
    @app_commands.describe(user_id="ID uzytkownika / User ID", reason="Powod / Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "-"):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message(embed=utils.error(t("mod.no_user_id")), ephemeral=True)
        try:
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        except discord.NotFound:
            return await interaction.response.send_message(embed=utils.error(t("mod.not_banned")), ephemeral=True)
        await interaction.response.send_message(embed=utils.success(t("mod.unbanned", user=user.mention)))

    @app_commands.command(name="kick", description="Wyrzuca uzytkownika z serwera. / Kicks a user.")
    @app_commands.describe(user="Kogo wyrzucic / Who to kick", reason="Powod / Reason")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "-"):
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(embed=utils.error(t("mod.hierarchy")), ephemeral=True)
        try:
            await user.send(embed=utils.warning(t("mod.dm_kicked", guild=interaction.guild.name, reason=reason)))
        except discord.HTTPException:
            pass
        await user.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=utils.success(t("mod.kicked", user=user.mention, reason=reason)))
        await self.log_action(interaction.guild, utils.info(
            t("mod.log_kick", user=user, id=user.id, mod=interaction.user.mention, reason=reason),
            title=t("mod.log_title"),
        ))

    @app_commands.command(name="timeout", description="Wycisza uzytkownika (minuty). / Times out a user (minutes).")
    @app_commands.describe(user="Kogo / Who", minutes="Ile minut (max 40320) / How many minutes", reason="Powod / Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "-"):
        if minutes < 1 or minutes > 40320:
            return await interaction.response.send_message(embed=utils.error(t("mod.timeout_range")), ephemeral=True)
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await user.timeout(until, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=utils.success(t("mod.timed_out", user=user.mention, min=minutes, reason=reason)))
        await self.log_action(interaction.guild, utils.info(
            t("mod.log_timeout", min=minutes, user=user, id=user.id, mod=interaction.user.mention, reason=reason),
            title=t("mod.log_title"),
        ))

    @app_commands.command(name="untimeout", description="Zdejmuje wyciszenie. / Removes a timeout.")
    @app_commands.describe(user="Komu / Who")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member):
        await user.timeout(None)
        await interaction.response.send_message(embed=utils.success(t("mod.untimed_out", user=user.mention)))

    @app_commands.command(name="warn", description="Daje ostrzezenie uzytkownikowi. / Warns a user.")
    @app_commands.describe(user="Kogo / Who", reason="Powod / Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "-"):
        await db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason) VALUES ($1, $2, $3, $4)",
            interaction.guild.id, user.id, interaction.user.id, reason,
        )
        count = await db.fetchval(
            "SELECT COUNT(*) FROM warns WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, user.id,
        )
        await interaction.response.send_message(embed=utils.success(t("mod.warned", user=user.mention, count=count, reason=reason)))
        try:
            await user.send(embed=utils.warning(t("mod.dm_warned", guild=interaction.guild.name, reason=reason)))
        except discord.HTTPException:
            pass

    @app_commands.command(name="warnings", description="Pokazuje ostrzezenia. / Shows a user's warnings.")
    @app_commands.describe(user="Czyje / Whose")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        rows = await db.fetch(
            "SELECT * FROM warns WHERE guild_id = $1 AND user_id = $2 ORDER BY created_at DESC LIMIT 15",
            interaction.guild.id, user.id,
        )
        if not rows:
            return await interaction.response.send_message(embed=utils.info(t("mod.no_warns", user=user.mention)), ephemeral=True)
        e = utils.info(title=t("mod.warns_title", user=user))
        for r in rows:
            mod = interaction.guild.get_member(r["moderator_id"])
            mod_name = mod.mention if mod else f"<@{r['moderator_id']}>"
            e.add_field(
                name=f"#{r['id']} - {r['created_at'].strftime('%Y-%m-%d %H:%M')}",
                value=t("mod.warn_field", reason=r["reason"], mod=mod_name),
                inline=False,
            )
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="delwarn", description="Usuwa ostrzezenie po ID. / Removes a warning by ID.")
    @app_commands.describe(warn_id="ID ostrzezenia / Warning ID")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def delwarn(self, interaction: discord.Interaction, warn_id: int):
        result = await db.execute("DELETE FROM warns WHERE id = $1 AND guild_id = $2", warn_id, interaction.guild.id)
        if result.endswith("0"):
            return await interaction.response.send_message(embed=utils.error(t("mod.warn_not_found")), ephemeral=True)
        await interaction.response.send_message(embed=utils.success(t("mod.warn_deleted", id=warn_id)))

    @app_commands.command(name="purge", description="Usuwa wiadomosci. / Deletes messages.")
    @app_commands.describe(amount="Ile (1-100) / How many (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message(embed=utils.error(t("mod.purge_range")), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=utils.success(t("mod.purged", count=len(deleted))), ephemeral=True)

    @app_commands.command(name="slowmode", description="Ustawia tryb powolny (sekundy). / Sets slowmode (seconds).")
    @app_commands.describe(seconds="Sekundy (0 = off, max 21600) / Seconds")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message(embed=utils.error(t("mod.slowmode_range")), ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message(embed=utils.success(t("mod.slowmode_off")))
        else:
            await interaction.response.send_message(embed=utils.success(t("mod.slowmode_on", sec=seconds)))

    @app_commands.command(name="lock", description="Blokuje pisanie na kanale. / Locks the channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=utils.success(t("mod.locked")))

    @app_commands.command(name="unlock", description="Odblokowuje pisanie. / Unlocks the channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=utils.success(t("mod.unlocked")))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
