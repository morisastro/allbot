"""Role reakcyjne - przyciski ktore nadaja/zdejmuja role.

Przyciski sa "persystentne" - dzialaja nawet po restarcie bota,
bo ich custom_id zawiera ID roli, a View jest rejestrowany na starcie.
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str = None):
        super().__init__(
            label=label,
            emoji=emoji or None,
            style=discord.ButtonStyle.secondary,
            custom_id=f"rr:{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message(embed=utils.error("Ta rola juz nie istnieje."), ephemeral=True)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Reaction role")
            await interaction.response.send_message(embed=utils.info(f"Zdjeto role {role.mention}."), ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason="Reaction role")
            await interaction.response.send_message(embed=utils.success(f"Nadano role {role.mention}."), ephemeral=True)


class PersistentRoleView(discord.ui.View):
    """View bez timeoutu - dziala wiecznie."""
    def __init__(self, buttons: list[tuple[int, str, str]]):
        super().__init__(timeout=None)
        for role_id, label, emoji in buttons:
            self.add_item(RoleButton(role_id, label, emoji))


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Rejestracja persystentnych przyciskow po restarcie
        rows = await db.fetch("SELECT DISTINCT message_id FROM reaction_roles")
        for row in rows:
            buttons = await db.fetch(
                "SELECT role_id, label, emoji FROM reaction_roles WHERE message_id = $1",
                row["message_id"],
            )
            view = PersistentRoleView([(b["role_id"], b["label"], b["emoji"]) for b in buttons])
            self.bot.add_view(view, message_id=row["message_id"])

    rr_group = app_commands.Group(name="reactionrole", description="Panele samodzielnego nadawania rol.",
                                 default_permissions=discord.Permissions(manage_roles=True))

    @rr_group.command(name="create", description="Tworzy panel z jednym przyciskiem roli (mozna dodawac kolejne).")
    @app_commands.describe(tytul="Tytul panelu", opis="Opis panelu", rola="Rola", etykieta="Tekst przycisku", emoji="Emoji (opcjonalnie)")
    async def create(self, interaction: discord.Interaction, tytul: str, opis: str,
                     rola: discord.Role, etykieta: str, emoji: str = None):
        if rola >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=utils.error("Ta rola jest wyzej niz moja - nie moge jej nadawac. Przesun moja role wyzej."),
                ephemeral=True,
            )
        view = PersistentRoleView([(rola.id, etykieta, emoji)])
        e = utils.info(title=tytul, description=opis)
        msg = await interaction.channel.send(embed=e, view=view)

        await db.execute(
            "INSERT INTO reaction_roles (guild_id, message_id, role_id, label, emoji) VALUES ($1, $2, $3, $4, $5)",
            interaction.guild.id, msg.id, rola.id, etykieta, emoji,
        )
        self.bot.add_view(view, message_id=msg.id)
        await interaction.response.send_message(
            embed=utils.success(f"Panel utworzony (ID wiadomosci: `{msg.id}`).\nAby dodac wiecej rol uzyj `/reactionrole add`."),
            ephemeral=True,
        )

    @rr_group.command(name="add", description="Dodaje przycisk roli do istniejacego panelu (po ID wiadomosci).")
    @app_commands.describe(message_id="ID wiadomosci panelu", rola="Rola", etykieta="Tekst przycisku", emoji="Emoji (opcjonalnie)")
    async def add(self, interaction: discord.Interaction, message_id: str, rola: discord.Role,
                  etykieta: str, emoji: str = None):
        try:
            mid = int(message_id)
            msg = await interaction.channel.fetch_message(mid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message(embed=utils.error("Nie znaleziono wiadomosci w tym kanale."), ephemeral=True)

        await db.execute(
            "INSERT INTO reaction_roles (guild_id, message_id, role_id, label, emoji) VALUES ($1, $2, $3, $4, $5)",
            interaction.guild.id, mid, rola.id, etykieta, emoji,
        )
        buttons = await db.fetch(
            "SELECT role_id, label, emoji FROM reaction_roles WHERE message_id = $1", mid
        )
        view = PersistentRoleView([(b["role_id"], b["label"], b["emoji"]) for b in buttons])
        self.bot.add_view(view, message_id=mid)
        await msg.edit(view=view)
        await interaction.response.send_message(embed=utils.success(f"Dodano przycisk dla {rola.mention}."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
