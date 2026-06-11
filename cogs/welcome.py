"""Powitania, pozegnania, autorole oraz komendy konfiguracyjne serwera.

Placeholdery: {user} {name} {server} {count}
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils
from i18n import t


def format_msg(template: str, member: discord.Member) -> str:
    return (template
            .replace("{user}", member.mention)
            .replace("{name}", member.display_name)
            .replace("{server}", member.guild.name)
            .replace("{count}", str(member.guild.member_count)))


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        settings = await db.get_guild_settings(member.guild.id)

        if settings["autorole_id"]:
            role = member.guild.get_role(settings["autorole_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except discord.Forbidden:
                    pass

        if settings["welcome_channel"]:
            ch = member.guild.get_channel(settings["welcome_channel"])
            if ch:
                template = settings["welcome_message"] or t("wel.welcome_default")
                e = utils.info(title=f"\U0001F44B {t('wel.welcome_title', server=member.guild.name)}",
                               description=format_msg(template, member))
                e.set_thumbnail(url=member.display_avatar.url)
                try:
                    await ch.send(content=member.mention, embed=e)
                except discord.Forbidden:
                    pass

        if settings["log_channel"]:
            ch = member.guild.get_channel(settings["log_channel"])
            if ch:
                e = utils.info(title=t("wel.joined_title"), description=f"{member.mention} ({member})")
                e.add_field(name=t("wel.account_created"), value=discord.utils.format_dt(member.created_at, "R"))
                await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        settings = await db.get_guild_settings(member.guild.id)

        if settings["leave_channel"]:
            ch = member.guild.get_channel(settings["leave_channel"])
            if ch:
                template = settings["leave_message"] or t("wel.leave_default")
                e = utils.embed(title=f"\U0001F44B {t('wel.leave_title')}",
                                description=format_msg(template, member), color=0x99AAB5)
                try:
                    await ch.send(embed=e)
                except discord.Forbidden:
                    pass

        if settings["log_channel"]:
            ch = member.guild.get_channel(settings["log_channel"])
            if ch:
                await ch.send(embed=utils.info(title=t("wel.left_title"), description=f"{member} ({member.id})"))

    config_group = app_commands.Group(name="config", description="Konfiguracja serwera. / Server configuration.",
                                      default_permissions=discord.Permissions(manage_guild=True))

    @config_group.command(name="welcome", description="Kanal i tekst powitania. / Welcome channel and text.")
    @app_commands.describe(kanal="Kanal / Channel", tekst="Tekst ({user} {name} {server} {count}) / Text")
    async def set_welcome(self, interaction: discord.Interaction, kanal: discord.TextChannel, tekst: str = None):
        await db.set_guild_setting(interaction.guild.id, "welcome_channel", kanal.id)
        if tekst:
            await db.set_guild_setting(interaction.guild.id, "welcome_message", tekst)
        await interaction.response.send_message(embed=utils.success(t("cfg.welcome_set", channel=kanal.mention)))

    @config_group.command(name="leave", description="Kanal i tekst pozegnania. / Leave channel and text.")
    @app_commands.describe(kanal="Kanal / Channel", tekst="Tekst ({user} {name} {server} {count}) / Text")
    async def set_leave(self, interaction: discord.Interaction, kanal: discord.TextChannel, tekst: str = None):
        await db.set_guild_setting(interaction.guild.id, "leave_channel", kanal.id)
        if tekst:
            await db.set_guild_setting(interaction.guild.id, "leave_message", tekst)
        await interaction.response.send_message(embed=utils.success(t("cfg.leave_set", channel=kanal.mention)))

    @config_group.command(name="autorole", description="Rola dla nowych czlonkow. / Autorole for new members.")
    @app_commands.describe(rola="Rola / Role")
    async def set_autorole(self, interaction: discord.Interaction, rola: discord.Role):
        await db.set_guild_setting(interaction.guild.id, "autorole_id", rola.id)
        await interaction.response.send_message(embed=utils.success(t("cfg.autorole_set", role=rola.mention)))

    @config_group.command(name="logs", description="Kanal logow. / Logs channel.")
    @app_commands.describe(kanal="Kanal / Channel")
    async def set_logs(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        await db.set_guild_setting(interaction.guild.id, "log_channel", kanal.id)
        await interaction.response.send_message(embed=utils.success(t("cfg.logs_set", channel=kanal.mention)))

    @config_group.command(name="levelchannel", description="Kanal ogloszen o awansach. / Level-up channel.")
    @app_commands.describe(kanal="Kanal / Channel")
    async def set_levelchannel(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        await db.set_guild_setting(interaction.guild.id, "level_up_channel", kanal.id)
        await interaction.response.send_message(embed=utils.success(t("cfg.levelchannel_set", channel=kanal.mention)))


async def setup(bot):
    await bot.add_cog(Welcome(bot))
