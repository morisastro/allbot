"""System ticketow - panel z przyciskiem, ktory tworzy prywatny kanal zgloszenia.

Przyciski sa persystentne (dzialaja po restarcie).
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


async def get_ticket_settings(guild_id: int):
    row = await db.fetchrow("SELECT * FROM ticket_settings WHERE guild_id = $1", guild_id)
    if row is None:
        await db.execute("INSERT INTO ticket_settings (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
        row = await db.fetchrow("SELECT * FROM ticket_settings WHERE guild_id = $1", guild_id)
    return row


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Otworz ticket", emoji="\U0001F4E9", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        settings = await get_ticket_settings(interaction.guild.id)

        # czy uzytkownik ma juz otwarty ticket?
        existing = discord.utils.get(interaction.guild.channels, name=f"ticket-{interaction.user.id}")
        if existing:
            return await interaction.followup.send(
                embed=utils.warning(f"Masz juz otwarty ticket: {existing.mention}"), ephemeral=True
            )

        category = interaction.guild.get_channel(settings["category_id"]) if settings["category_id"] else None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if settings["support_role_id"]:
            role = interaction.guild.get_role(settings["support_role_id"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        counter = (settings["ticket_counter"] or 0) + 1
        await db.execute("UPDATE ticket_settings SET ticket_counter = $2 WHERE guild_id = $1",
                         interaction.guild.id, counter)

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket #{counter} | {interaction.user}",
        )

        e = utils.info(
            title=f"Ticket #{counter}",
            description=f"Witaj {interaction.user.mention}!\nOpisz swoj problem, zespol wkrotce odpowie.",
        )
        support_mention = f"<@&{settings['support_role_id']}>" if settings["support_role_id"] else ""
        await channel.send(content=f"{interaction.user.mention} {support_mention}", embed=e, view=CloseTicket())
        await interaction.followup.send(embed=utils.success(f"Twoj ticket: {channel.mention}"), ephemeral=True)


class CloseTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij ticket", emoji="\U0001F512", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=utils.warning("Zamykanie ticketu za 5 sekund..."))
        settings = await get_ticket_settings(interaction.guild.id)
        if settings["log_channel"]:
            log_ch = interaction.guild.get_channel(settings["log_channel"])
            if log_ch:
                await log_ch.send(embed=utils.info(
                    title="Ticket zamkniety",
                    description=f"Kanal: {interaction.channel.name}\nZamkniety przez: {interaction.user.mention}",
                ))
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket zamkniety przez {interaction.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # rejestracja persystentnych widokow
        self.bot.add_view(TicketPanel())
        self.bot.add_view(CloseTicket())

    ticket_group = app_commands.Group(name="ticket", description="Konfiguracja systemu ticketow.",
                                     default_permissions=discord.Permissions(manage_guild=True))

    @ticket_group.command(name="setup", description="Konfiguruje system ticketow.")
    @app_commands.describe(kategoria="Kategoria dla ticketow", rola_supportu="Rola obslugi", kanal_logow="Kanal logow ticketow")
    async def setup_tickets(self, interaction: discord.Interaction, kategoria: discord.CategoryChannel,
                            rola_supportu: discord.Role, kanal_logow: discord.TextChannel = None):
        await get_ticket_settings(interaction.guild.id)
        await db.execute(
            "UPDATE ticket_settings SET category_id = $2, support_role_id = $3, log_channel = $4 WHERE guild_id = $1",
            interaction.guild.id, kategoria.id, rola_supportu.id, kanal_logow.id if kanal_logow else None,
        )
        await interaction.response.send_message(embed=utils.success("System ticketow skonfigurowany."))

    @ticket_group.command(name="panel", description="Wysyla panel z przyciskiem do otwierania ticketow.")
    @app_commands.describe(tytul="Tytul panelu", opis="Opis")
    async def panel(self, interaction: discord.Interaction,
                    tytul: str = "Wsparcie / Pomoc",
                    opis: str = "Kliknij przycisk ponizej, aby otworzyc ticket i skontaktowac sie z zespolem."):
        e = utils.info(title=tytul, description=opis)
        await interaction.channel.send(embed=e, view=TicketPanel())
        await interaction.response.send_message(embed=utils.success("Panel wyslany."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
