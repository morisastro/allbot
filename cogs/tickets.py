"""System ticketow - panel z przyciskiem tworzacy prywatny kanal zgloszenia."""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils
from i18n import t


async def get_ticket_settings(guild_id: int):
    row = await db.fetchrow("SELECT * FROM ticket_settings WHERE guild_id = $1", guild_id)
    if row is None:
        await db.execute("INSERT INTO ticket_settings (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
        row = await db.fetchrow("SELECT * FROM ticket_settings WHERE guild_id = $1", guild_id)
    return row


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.open_ticket.label = t("tk.open_button")

    @discord.ui.button(emoji="\U0001F4E9", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        settings = await get_ticket_settings(interaction.guild.id)

        existing = discord.utils.get(interaction.guild.channels, name=f"ticket-{interaction.user.id}")
        if existing:
            return await interaction.followup.send(embed=utils.warning(t("tk.already_open", channel=existing.mention)), ephemeral=True)

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
        await db.execute("UPDATE ticket_settings SET ticket_counter = $2 WHERE guild_id = $1", interaction.guild.id, counter)

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.id}", category=category, overwrites=overwrites,
            topic=f"Ticket #{counter} | {interaction.user}",
        )

        e = utils.info(title=t("tk.ticket_title", num=counter),
                       description=t("tk.ticket_welcome", user=interaction.user.mention))
        support_mention = f"<@&{settings['support_role_id']}>" if settings["support_role_id"] else ""
        await channel.send(content=f"{interaction.user.mention} {support_mention}", embed=e, view=CloseTicket())
        await interaction.followup.send(embed=utils.success(t("tk.your_ticket", channel=channel.mention)), ephemeral=True)


class CloseTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.close.label = t("tk.close_button")

    @discord.ui.button(emoji="\U0001F512", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=utils.warning(t("tk.closing")))
        settings = await get_ticket_settings(interaction.guild.id)
        if settings["log_channel"]:
            log_ch = interaction.guild.get_channel(settings["log_channel"])
            if log_ch:
                await log_ch.send(embed=utils.info(
                    title=t("tk.closed_title"),
                    description=t("tk.closed_log", name=interaction.channel.name, user=interaction.user.mention),
                ))
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketPanel())
        self.bot.add_view(CloseTicket())

    ticket_group = app_commands.Group(name="ticket", description="Konfiguracja ticketow. / Ticket config.",
                                     default_permissions=discord.Permissions(manage_guild=True))

    @ticket_group.command(name="setup", description="Konfiguruje tickety. / Sets up tickets.")
    @app_commands.describe(kategoria="Kategoria / Category", rola_supportu="Rola obslugi / Support role",
                           kanal_logow="Kanal logow / Logs channel")
    async def setup_tickets(self, interaction: discord.Interaction, kategoria: discord.CategoryChannel,
                            rola_supportu: discord.Role, kanal_logow: discord.TextChannel = None):
        await get_ticket_settings(interaction.guild.id)
        await db.execute(
            "UPDATE ticket_settings SET category_id = $2, support_role_id = $3, log_channel = $4 WHERE guild_id = $1",
            interaction.guild.id, kategoria.id, rola_supportu.id, kanal_logow.id if kanal_logow else None,
        )
        await interaction.response.send_message(embed=utils.success(t("tk.setup_done")))

    @ticket_group.command(name="panel", description="Wysyla panel ticketow. / Sends the ticket panel.")
    @app_commands.describe(tytul="Tytul / Title", opis="Opis / Description")
    async def panel(self, interaction: discord.Interaction, tytul: str = None, opis: str = None):
        e = utils.info(title=tytul or t("tk.panel_title"), description=opis or t("tk.panel_desc"))
        await interaction.channel.send(embed=e, view=TicketPanel())
        await interaction.response.send_message(embed=utils.success(t("tk.panel_sent")), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
