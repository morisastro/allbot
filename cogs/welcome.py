"""Powitania, pozegnania, autorole oraz komendy konfiguracyjne serwera.

W tekstach powitan/pozegnan mozna uzywac:
  {user}   - wzmianka uzytkownika
  {name}   - nazwa uzytkownika
  {server} - nazwa serwera
  {count}  - liczba czlonkow
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


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

        # autorole
        if settings["autorole_id"]:
            role = member.guild.get_role(settings["autorole_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except discord.Forbidden:
                    pass

        # powitanie
        if settings["welcome_channel"]:
            ch = member.guild.get_channel(settings["welcome_channel"])
            if ch:
                template = settings["welcome_message"] or "Witaj {user} na **{server}**! Jestes {count} czlonkiem."
                e = utils.info(title=f"\U0001F44B Witaj na {member.guild.name}!", description=format_msg(template, member))
                e.set_thumbnail(url=member.display_avatar.url)
                try:
                    await ch.send(content=member.mention, embed=e)
                except discord.Forbidden:
                    pass

        # log
        if settings["log_channel"]:
            ch = member.guild.get_channel(settings["log_channel"])
            if ch:
                e = utils.info(title="Czlonek dolaczyl", description=f"{member.mention} ({member})")
                e.add_field(name="Konto utworzone", value=discord.utils.format_dt(member.created_at, "R"))
                await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        settings = await db.get_guild_settings(member.guild.id)

        if settings["leave_channel"]:
            ch = member.guild.get_channel(settings["leave_channel"])
            if ch:
                template = settings["leave_message"] or "{name} opuscil serwer. Zostalo nas {count}."
                e = utils.embed(title="\U0001F44B Do zobaczenia!", description=format_msg(template, member), color=0x99AAB5)
                try:
                    await ch.send(embed=e)
                except discord.Forbidden:
                    pass

        if settings["log_channel"]:
            ch = member.guild.get_channel(settings["log_channel"])
            if ch:
                await ch.send(embed=utils.info(title="Czlonek opuscil serwer", description=f"{member} ({member.id})"))

    # ---------- Konfiguracja ----------
    config_group = app_commands.Group(name="config", description="Konfiguracja serwera.",
                                      default_permissions=discord.Permissions(manage_guild=True))

    @config_group.command(name="welcome", description="Ustawia kanal i tekst powitania.")
    @app_commands.describe(kanal="Kanal powitan", tekst="Tekst (placeholdery: {user} {name} {server} {count})")
    async def set_welcome(self, interaction: discord.Interaction, kanal: discord.TextChannel, tekst: str = None):
        await db.set_guild_setting(interaction.guild.id, "welcome_channel", kanal.id)
        if tekst:
            await db.set_guild_setting(interaction.guild.id, "welcome_message", tekst)
        await interaction.response.send_message(embed=utils.success(f"Powitania ustawione na {kanal.mention}."))

    @config_group.command(name="leave", description="Ustawia kanal i tekst pozegnania.")
    @app_commands.describe(kanal="Kanal pozegnan", tekst="Tekst (placeholdery: {user} {name} {server} {count})")
    async def set_leave(self, interaction: discord.Interaction, kanal: discord.TextChannel, tekst: str = None):
        await db.set_guild_setting(interaction.guild.id, "leave_channel", kanal.id)
        if tekst:
            await db.set_guild_setting(interaction.guild.id, "leave_message", tekst)
        await interaction.response.send_message(embed=utils.success(f"Pozegnania ustawione na {kanal.mention}."))

    @config_group.command(name="autorole", description="Ustawia role nadawana nowym czlonkom.")
    @app_commands.describe(rola="Rola dla nowych czlonkow")
    async def set_autorole(self, interaction: discord.Interaction, rola: discord.Role):
        await db.set_guild_setting(interaction.guild.id, "autorole_id", rola.id)
        await interaction.response.send_message(embed=utils.success(f"Autorole ustawione na {rola.mention}."))

    @config_group.command(name="logs", description="Ustawia kanal logow moderacji/serwera.")
    @app_commands.describe(kanal="Kanal logow")
    async def set_logs(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        await db.set_guild_setting(interaction.guild.id, "log_channel", kanal.id)
        await interaction.response.send_message(embed=utils.success(f"Logi ustawione na {kanal.mention}."))

    @config_group.command(name="levelchannel", description="Ustawia kanal ogloszen o awansach poziomu.")
    @app_commands.describe(kanal="Kanal awansow (pusto = ten sam kanal)")
    async def set_levelchannel(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        await db.set_guild_setting(interaction.guild.id, "level_up_channel", kanal.id)
        await interaction.response.send_message(embed=utils.success(f"Ogloszenia o poziomach: {kanal.mention}."))


async def setup(bot):
    await bot.add_cog(Welcome(bot))
