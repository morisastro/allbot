"""Ekonomia - balansy, daily, work, hazard, transfery, sklep z rolami."""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils
from i18n import t

CUR = config.CURRENCY_SYMBOL


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + f" {CUR}"


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Stan konta. / Account balance.")
    @app_commands.describe(user="Czyje konto / Whose account")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        eco = await db.get_economy(interaction.guild.id, user.id)
        e = utils.info(title=t("eco.account_title", name=user.display_name))
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name=t("eco.wallet"), value=fmt(eco["balance"]))
        e.add_field(name=t("eco.bank"), value=fmt(eco["bank"]))
        e.add_field(name=t("eco.total"), value=fmt(eco["balance"] + eco["bank"]))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="daily", description="Codzienna nagroda. / Daily reward.")
    async def daily(self, interaction: discord.Interaction):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        now = time.time()
        if now - eco["last_daily"] < config.DAILY_COOLDOWN:
            remaining = int(config.DAILY_COOLDOWN - (now - eco["last_daily"]))
            h, m = divmod(remaining // 60, 60)
            return await interaction.response.send_message(embed=utils.warning(t("eco.daily_wait", h=h, m=m)), ephemeral=True)
        await db.execute(
            "UPDATE economy SET balance = balance + $3, last_daily = $4 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, config.DAILY_AMOUNT, now,
        )
        await interaction.response.send_message(embed=utils.success(t("eco.daily_ok", amount=fmt(config.DAILY_AMOUNT))))

    @app_commands.command(name="work", description="Pracuj i zarob. / Work and earn coins.")
    async def work(self, interaction: discord.Interaction):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        now = time.time()
        if now - eco["last_work"] < config.WORK_COOLDOWN:
            remaining = int(config.WORK_COOLDOWN - (now - eco["last_work"]))
            m, s = divmod(remaining, 60)
            return await interaction.response.send_message(embed=utils.warning(t("eco.work_wait", m=m, s=s)), ephemeral=True)
        earned = random.randint(config.WORK_MIN, config.WORK_MAX)
        job = t(f"eco.job{random.randint(1, 6)}")
        await db.execute(
            "UPDATE economy SET balance = balance + $3, last_work = $4 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, earned, now,
        )
        await interaction.response.send_message(embed=utils.success(t("eco.work_ok", job=job, amount=fmt(earned))))

    @app_commands.command(name="gamble", description="Zaryzykuj monety (50%). / Gamble coins (50%).")
    @app_commands.describe(amount="Ile postawic / How much to bet")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(embed=utils.error(t("eco.gamble_positive")), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if amount > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error(t("eco.not_enough_wallet")), ephemeral=True)
        if random.random() < 0.5:
            await db.add_balance(interaction.guild.id, interaction.user.id, amount)
            await interaction.response.send_message(embed=utils.success(t("eco.gamble_win", amount=fmt(amount))))
        else:
            await db.add_balance(interaction.guild.id, interaction.user.id, -amount)
            await interaction.response.send_message(embed=utils.error(t("eco.gamble_lose", amount=fmt(amount)), title=t("eco.gamble_lose_title")))

    @app_commands.command(name="deposit", description="Wplata do banku. / Deposit to bank.")
    @app_commands.describe(amount="Ile (lub 'all') / How much (or 'all')")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        value = eco["balance"] if amount.lower() == "all" else self._parse(amount)
        if value is None or value <= 0 or value > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error(t("eco.bad_amount")), ephemeral=True)
        await db.execute(
            "UPDATE economy SET balance = balance - $3, bank = bank + $3 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, value,
        )
        await interaction.response.send_message(embed=utils.success(t("eco.deposited", amount=fmt(value))))

    @app_commands.command(name="withdraw", description="Wyplata z banku. / Withdraw from bank.")
    @app_commands.describe(amount="Ile (lub 'all') / How much (or 'all')")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        value = eco["bank"] if amount.lower() == "all" else self._parse(amount)
        if value is None or value <= 0 or value > eco["bank"]:
            return await interaction.response.send_message(embed=utils.error(t("eco.bad_amount")), ephemeral=True)
        await db.execute(
            "UPDATE economy SET balance = balance + $3, bank = bank - $3 WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id, interaction.user.id, value,
        )
        await interaction.response.send_message(embed=utils.success(t("eco.withdrew", amount=fmt(value))))

    @app_commands.command(name="pay", description="Przekaz monety. / Transfer coins.")
    @app_commands.describe(user="Komu / To whom", amount="Ile / How much")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.bot or user.id == interaction.user.id:
            return await interaction.response.send_message(embed=utils.error(t("eco.bad_recipient")), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if amount <= 0 or amount > eco["balance"]:
            return await interaction.response.send_message(embed=utils.error(t("eco.bad_amount")), ephemeral=True)
        await db.add_balance(interaction.guild.id, interaction.user.id, -amount)
        await db.add_balance(interaction.guild.id, user.id, amount)
        await interaction.response.send_message(embed=utils.success(t("eco.paid", amount=fmt(amount), user=user.mention)))

    @app_commands.command(name="richest", description="Najbogatsi. / Richest members.")
    async def richest(self, interaction: discord.Interaction):
        rows = await db.fetch(
            "SELECT user_id, balance + bank AS total FROM economy WHERE guild_id = $1 ORDER BY total DESC LIMIT 10",
            interaction.guild.id,
        )
        if not rows:
            return await interaction.response.send_message(embed=utils.info(t("eco.no_data")), ephemeral=True)
        lines = []
        for i, r in enumerate(rows):
            m = interaction.guild.get_member(r["user_id"])
            name = m.display_name if m else f"<@{r['user_id']}>"
            lines.append(f"**{i+1}.** {name} - {fmt(r['total'])}")
        await interaction.response.send_message(embed=utils.info(title=f"\U0001F4B0 {t('eco.richest_title')}", description="\n".join(lines)))

    @app_commands.command(name="shop", description="Sklep z rolami. / Role shop.")
    async def shop(self, interaction: discord.Interaction):
        rows = await db.fetch("SELECT * FROM shop_items WHERE guild_id = $1 ORDER BY price", interaction.guild.id)
        if not rows:
            return await interaction.response.send_message(embed=utils.info(t("eco.shop_empty")), ephemeral=True)
        lines = [t("eco.shop_line", name=r["name"], price=fmt(r["price"]), role=f"<@&{r['role_id']}>", id=r["id"]) for r in rows]
        await interaction.response.send_message(embed=utils.info(title=f"\U0001F6D2 {t('eco.shop_title')}", description="\n".join(lines)))

    @app_commands.command(name="buy", description="Kup przedmiot (po ID). / Buy an item by ID.")
    @app_commands.describe(item_id="ID przedmiotu / Item ID")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        item = await db.fetchrow("SELECT * FROM shop_items WHERE id = $1 AND guild_id = $2", item_id, interaction.guild.id)
        if not item:
            return await interaction.response.send_message(embed=utils.error(t("eco.item_not_found")), ephemeral=True)
        eco = await db.get_economy(interaction.guild.id, interaction.user.id)
        if eco["balance"] < item["price"]:
            return await interaction.response.send_message(embed=utils.error(t("eco.cant_afford")), ephemeral=True)
        role = interaction.guild.get_role(item["role_id"])
        if not role:
            return await interaction.response.send_message(embed=utils.error(t("eco.role_gone")), ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message(embed=utils.warning(t("eco.already_have_role")), ephemeral=True)
        try:
            await interaction.user.add_roles(role, reason="Shop purchase")
        except discord.Forbidden:
            return await interaction.response.send_message(embed=utils.error(t("eco.cant_grant")), ephemeral=True)
        await db.add_balance(interaction.guild.id, interaction.user.id, -item["price"])
        await interaction.response.send_message(embed=utils.success(t("eco.bought", name=item["name"], price=fmt(item["price"]))))

    shop_group = app_commands.Group(name="shopadmin", description="Zarzadzanie sklepem. / Shop management.",
                                   default_permissions=discord.Permissions(manage_guild=True))

    @shop_group.command(name="add", description="Dodaje role do sklepu. / Adds a role to the shop.")
    @app_commands.describe(rola="Rola / Role", cena="Cena / Price", nazwa="Nazwa / Name")
    async def shop_add(self, interaction: discord.Interaction, rola: discord.Role, cena: int, nazwa: str):
        await db.execute("INSERT INTO shop_items (guild_id, role_id, price, name) VALUES ($1, $2, $3, $4)",
                         interaction.guild.id, rola.id, cena, nazwa)
        await interaction.response.send_message(embed=utils.success(t("eco.shop_added", name=nazwa, price=fmt(cena))))

    @shop_group.command(name="remove", description="Usuwa przedmiot ze sklepu. / Removes a shop item.")
    @app_commands.describe(item_id="ID przedmiotu / Item ID")
    async def shop_remove(self, interaction: discord.Interaction, item_id: int):
        await db.execute("DELETE FROM shop_items WHERE id = $1 AND guild_id = $2", item_id, interaction.guild.id)
        await interaction.response.send_message(embed=utils.success(t("eco.shop_removed", id=item_id)))

    @shop_group.command(name="give", description="Dodaje monety (admin). / Gives coins (admin).")
    @app_commands.describe(user="Komu / To whom", amount="Ile / How much")
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await db.add_balance(interaction.guild.id, user.id, amount)
        await interaction.response.send_message(embed=utils.success(t("eco.balance_changed", user=user.mention, amount=fmt(amount))))

    @staticmethod
    def _parse(s: str):
        try:
            return int(s)
        except ValueError:
            return None


async def setup(bot):
    await bot.add_cog(Economy(bot))
