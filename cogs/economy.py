"""Ekonomia - balansy, daily, work, hazard, transfery, sklep z rolami."""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils

CUR = config.CURRENCY_SYMBOL


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + f" {CUR}"


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Pokazuje stan konta.")
    @app_commands.describe(user="Czyje konto (pusto = Twoje)")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        eco = await db.get_economy(interaction.guild.id, user.id)
        e = utils.info(title=f"Konto: {user.display_name}")
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name="Portfel", value=fmt(eco["balance"]))
        e.add_field(name="Bank", value=fmt(eco["bank"]))
        e.add_field(name="Razem", value=fmt(eco["balance"] + eco["bank"]))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="daily", description="Odbierz codzienna nagrode.")
    async def daily(self, interaction: discord.Interaction):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        now = time.time()
        if now - eco["last_daily"] < config.DAILY_COOLDOWN:
            remaining = int(config.DAILY_COOLDOWN - (now - eco["last_daily"]))
            h, m = divmod(remaining // 60, 60)
            return await interaction.response.send_message(
                embed=utils.warning(f"Juz odebrales dzisiaj. Wroc za **{h}h {m}m**."), ephemeral=True
            )
        await db.execute(
            "UPDATE economy SET balance = balance + $3, last_daily = $4 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, config.DAILY_AMOUNT, now,
        )
        await interaction.response.send_message(
            embed=utils.success(f"Odebrales codzienna nagrode: **{fmt(config.DAILY_AMOUNT)}**!")
        )

    @app_commands.command(name="work", description="Pracuj i zarob troche monet.")
    async def work(self, interaction: discord.Interaction):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        now = time.time()
        if now - eco["last_work"] < config.WORK_COOLDOWN:
            remaining = int(config.WORK_COOLDOWN - (now - eco["last_work"]))
            m, s = divmod(remaining, 60)
            return await interaction.response.send_message(
                embed=utils.warning(f"Jestes zmeczony. Odpocznij jeszcze **{m}m {s}s**."), ephemeral=True
            )
        earned = random.randint(config.WORK_MIN, config.WORK_MAX)
        jobs = ["programowales bota", "dostarczyles pizze", "naprawiles serwer",
                "sprzedales memy", "streamowales na Twitchu", "wyprowadziles psa sasiada"]
        await db.execute(
            "UPDATE economy SET balance = balance + $3, last_work = $4 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, earned, now,
        )
        await interaction.response.send_message(
            embed=utils.success(f"{random.choice(jobs).capitalize()} i zarobiles **{fmt(earned)}**!")
        )

    @app_commands.command(name="gamble", description="Zaryzykuj monety - 50% szans na podwojenie.")
    @app_commands.describe(amount="Ile postawic")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(embed=utils.error("Postaw dodatnia kwote."), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if amount > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error("Nie masz tyle w portfelu."), ephemeral=True)
        if random.random() < 0.5:
            await db.add_balance(interaction.guild.id, interaction.user.id, amount)
            await interaction.response.send_message(embed=utils.success(f"Wygrales! +**{fmt(amount)}**"))
        else:
            await db.add_balance(interaction.guild.id, interaction.user.id, -amount)
            await interaction.response.send_message(embed=utils.error(f"Przegrales **{fmt(amount)}**...", title="Pech"))

    @app_commands.command(name="deposit", description="Wplac monety do banku.")
    @app_commands.describe(amount="Ile wplacic (lub 'all')")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        value = eco["balance"] if amount.lower() == "all" else self._parse(amount)
        if value is None or value <= 0 or value > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error("Nieprawidlowa kwota."), ephemeral=True)
        await db.execute(
            "UPDATE economy SET balance = balance - $3, bank = bank + $3 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, value,
        )
        await interaction.response.send_message(embed=utils.success(f"Wplacono **{fmt(value)}** do banku."))

    @app_commands.command(name="withdraw", description="Wyplac monety z banku.")
    @app_commands.describe(amount="Ile wyplacic (lub 'all')")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        value = eco["bank"] if amount.lower() == "all" else self._parse(amount)
        if value is None or value <= 0 or value > eco["bank"]:
            return await interaction.response.send_message(embed=utils.error("Nieprawidlowa kwota."), ephemeral=True)
        await db.execute(
            "UPDATE economy SET balance = balance + $3, bank = bank - $3 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, value,
        )
        await interaction.response.send_message(embed=utils.success(f"Wyplacono **{fmt(value)}** z banku."))

    @app_commands.command(name="pay", description="Przekaz monety innemu uzytkownikowi.")
    @app_commands.describe(user="Komu", amount="Ile")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.bot or user.id == interaction.user.id:
            return await interaction.response.send_message(embed=utils.error("Nieprawidlowy odbiorca."), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if amount <= 0 or amount > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error("Nieprawidlowa kwota."), ephemeral=True)
        await db.add_balance(interaction.guild.id, interaction.user.id, -amount)
        await db.add_balance(interaction.guild.id, user.id, amount)
        await interaction.response.send_message(embed=utils.success(f"Przekazano **{fmt(amount)}** dla {user.mention}."))

    @app_commands.command(name="richest", description="Najbogatsi na serwerze.")
    async def richest(self, interaction: discord.Interaction):
        rows = await db.fetch(
            "SELECT user_id, balance + bank AS total FROM economy WHERE guild_id = $1 "
            "ORDER BY total DESC LIMIT 10",
            interaction.guild.id,
        )
        if not rows:
            return await interaction.response.send_message(embed=utils.info("Brak danych."), ephemeral=True)
        lines = []
        for i, r in enumerate(rows):
            m = interaction.guild.get_member(r["user_id"])
            name = m.display_name if m else f"<@{r['user_id']}>"
            lines.append(f"**{i+1}.** {name} - {fmt(r['total'])}")
        await interaction.response.send_message(embed=utils.info(title="\U0001F4B0 Najbogatsi", description="\n".join(lines)))

    # ---------- Sklep ----------
    @app_commands.command(name="shop", description="Pokazuje sklep z rolami.")
    async def shop(self, interaction: discord.Interaction):
        rows = await db.fetch("SELECT * FROM shop_items WHERE guild_id = $1 ORDER BY price", interaction.guild.id)
        if not rows:
            return await interaction.response.send_message(embed=utils.info("Sklep jest pusty."), ephemeral=True)
        lines = [f"**{r['name']}** - {fmt(r['price'])} (<@&{r['role_id']}>) `ID: {r['id']}`" for r in rows]
        await interaction.response.send_message(embed=utils.info(title="\U0001F6D2 Sklep", description="\n".join(lines)))

    @app_commands.command(name="buy", description="Kup przedmiot ze sklepu (po ID).")
    @app_commands.describe(item_id="ID przedmiotu ze /shop")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        item = await db.fetchrow(
            "SELECT * FROM shop_items WHERE id = $1 AND guild_id = $2", item_id, interaction.guild.id
        )
        if not item:
            return await interaction.response.send_message(embed=utils.error("Nie ma takiego przedmiotu."), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if eco["balance"] < item["price"]:
            return await interaction.response.send_message(embed=utils.error("Nie masz wystarczajaco monet."), ephemeral=True)
        role = interaction.guild.get_role(item["role_id"])
        if not role:
            return await interaction.response.send_message(embed=utils.error("Rola juz nie istnieje."), ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message(embed=utils.warning("Juz masz te role."), ephemeral=True)
        try:
            await interaction.user.add_roles(role, reason="Zakup w sklepie")
        except discord.Forbidden:
            return await interaction.response.send_message(embed=utils.error("Nie moge nadac tej roli (sprawdz uprawnienia)."), ephemeral=True)
        await db.add_balance(interaction.guild.id, interaction.user.id, -item["price"])
        await interaction.response.send_message(embed=utils.success(f"Kupiles **{item['name']}** za {fmt(item['price'])}!"))

    shop_group = app_commands.Group(name="shopadmin", description="Zarzadzanie sklepem.",
                                   default_permissions=discord.Permissions(manage_guild=True))

    @shop_group.command(name="add", description="Dodaje role do sklepu.")
    @app_commands.describe(rola="Rola do sprzedazy", cena="Cena", nazwa="Nazwa w sklepie")
    async def shop_add(self, interaction: discord.Interaction, rola: discord.Role, cena: int, nazwa: str):
        await db.execute(
            "INSERT INTO shop_items (guild_id, role_id, price, name) VALUES ($1, $2, $3, $4)",
            interaction.guild.id, rola.id, cena, nazwa,
        )
        await interaction.response.send_message(embed=utils.success(f"Dodano **{nazwa}** do sklepu za {fmt(cena)}."))

    @shop_group.command(name="remove", description="Usuwa przedmiot ze sklepu.")
    @app_commands.describe(item_id="ID przedmiotu")
    async def shop_remove(self, interaction: discord.Interaction, item_id: int):
        await db.execute("DELETE FROM shop_items WHERE id = $1 AND guild_id = $2", item_id, interaction.guild.id)
        await interaction.response.send_message(embed=utils.success(f"Usunieto przedmiot #{item_id}."))

    @shop_group.command(name="give", description="Dodaje monety uzytkownikowi (admin).")
    @app_commands.describe(user="Komu", amount="Ile (moze byc ujemne)")
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await db.add_balance(interaction.guild.id, user.id, amount)
        await interaction.response.send_message(embed=utils.success(f"Zmieniono balans {user.mention} o **{fmt(amount)}**."))

    @staticmethod
    def _parse(s: str):
        try:
            return int(s)
        except ValueError:
            return None


async def setup(bot):
    await bot.add_cog(Economy(bot))
