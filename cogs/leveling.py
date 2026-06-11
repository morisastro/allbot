"""Leveling - zdobywanie XP za wiadomosci, awanse, ranking, nagrody za poziom."""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils
from i18n import t


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        settings = await db.get_guild_settings(message.guild.id)
        if not settings["levels_enabled"]:
            return

        data = await db.get_level(message.guild.id, message.author.id)
        now = time.time()
        if now - data["last_xp"] < config.XP_COOLDOWN:
            return

        gain = random.randint(config.XP_PER_MESSAGE_MIN, config.XP_PER_MESSAGE_MAX)
        new_xp = data["xp"] + gain
        level = data["level"]

        leveled_up = False
        while new_xp >= config.xp_needed(level):
            new_xp -= config.xp_needed(level)
            level += 1
            leveled_up = True

        await db.execute(
            "UPDATE levels SET xp = $3, level = $4, last_xp = $5 WHERE guild_id = $1 AND user_id = $2",
            message.guild.id, message.author.id, new_xp, level, now,
        )

        if leveled_up:
            await self.handle_level_up(message, level, settings)

    async def handle_level_up(self, message, level, settings):
        channel = message.channel
        if settings["level_up_channel"]:
            c = message.guild.get_channel(settings["level_up_channel"])
            if c:
                channel = c
        try:
            await channel.send(embed=utils.success(
                t("lvl.levelup", user=message.author.mention, level=level),
                title=f"\U0001F389 {t('lvl.levelup_title')}",
            ))
        except discord.HTTPException:
            pass

        reward = await db.fetchrow(
            "SELECT role_id FROM level_rewards WHERE guild_id = $1 AND level = $2",
            message.guild.id, level,
        )
        if reward:
            role = message.guild.get_role(reward["role_id"])
            if role:
                try:
                    await message.author.add_roles(role, reason=f"Level {level} reward")
                except discord.Forbidden:
                    pass

    @app_commands.command(name="rank", description="Twoj poziom i XP. / Your level and XP.")
    @app_commands.describe(user="Czyj ranking / Whose rank")
    async def rank(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data = await db.get_level(interaction.guild.id, user.id)
        needed = config.xp_needed(data["level"])

        position = await db.fetchval(
            "SELECT COUNT(*) + 1 FROM levels WHERE guild_id = $1 AND "
            "(level > $2 OR (level = $2 AND xp > $3))",
            interaction.guild.id, data["level"], data["xp"],
        )

        bar_len = 20
        filled = int((data["xp"] / needed) * bar_len) if needed else 0
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)

        e = utils.info(title=t("lvl.rank_title", name=user.display_name))
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name=t("lvl.level"), value=str(data["level"]))
        e.add_field(name=t("lvl.position"), value=f"#{position}")
        e.add_field(name="XP", value=f"{data['xp']} / {needed}")
        e.add_field(name=t("lvl.progress"), value=f"`{bar}`", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="leaderboard", description="Top 10 poziomow. / Top 10 by level.")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await db.fetch(
            "SELECT user_id, level, xp FROM levels WHERE guild_id = $1 ORDER BY level DESC, xp DESC LIMIT 10",
            interaction.guild.id,
        )
        if not rows:
            return await interaction.response.send_message(embed=utils.info(t("lvl.no_data")), ephemeral=True)
        medals = ["\U0001F947", "\U0001F948", "\U0001F949"]
        lines = []
        for i, r in enumerate(rows):
            member = interaction.guild.get_member(r["user_id"])
            name = member.display_name if member else f"<@{r['user_id']}>"
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(t("lvl.lb_entry", prefix=prefix, name=name, level=r["level"], xp=r["xp"]))
        e = utils.info(title=f"\U0001F3C6 {t('lvl.leaderboard_title', guild=interaction.guild.name)}",
                       description="\n".join(lines))
        await interaction.response.send_message(embed=e)

    levels_group = app_commands.Group(name="levels", description="Konfiguracja poziomow. / Leveling config.",
                                     default_permissions=discord.Permissions(manage_guild=True))

    @levels_group.command(name="toggle", description="Wlacza/wylacza poziomy. / Toggles leveling.")
    @app_commands.describe(wartosc="Wlaczony? / Enabled?")
    async def toggle(self, interaction: discord.Interaction, wartosc: bool):
        await db.set_guild_setting(interaction.guild.id, "levels_enabled", wartosc)
        from i18n import t as _t
        state = _t("auto.state_on") if wartosc else _t("auto.state_off")
        await interaction.response.send_message(embed=utils.success(t("lvl.system_state", state=state)))

    @levels_group.command(name="addreward", description="Rola-nagroda za poziom. / Role reward for a level.")
    @app_commands.describe(poziom="Poziom / Level", rola="Rola / Role")
    async def addreward(self, interaction: discord.Interaction, poziom: int, rola: discord.Role):
        await db.execute(
            "INSERT INTO level_rewards (guild_id, level, role_id) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id, level) DO UPDATE SET role_id = $3",
            interaction.guild.id, poziom, rola.id,
        )
        await interaction.response.send_message(embed=utils.success(t("lvl.reward_added", level=poziom, role=rola.mention)))

    @levels_group.command(name="delreward", description="Usuwa nagrode za poziom. / Removes a level reward.")
    @app_commands.describe(poziom="Poziom / Level")
    async def delreward(self, interaction: discord.Interaction, poziom: int):
        await db.execute("DELETE FROM level_rewards WHERE guild_id = $1 AND level = $2", interaction.guild.id, poziom)
        await interaction.response.send_message(embed=utils.success(t("lvl.reward_deleted", level=poziom)))

    @levels_group.command(name="rewards", description="Lista nagrod za poziomy. / List of level rewards.")
    async def rewards(self, interaction: discord.Interaction):
        rows = await db.fetch("SELECT level, role_id FROM level_rewards WHERE guild_id = $1 ORDER BY level",
                              interaction.guild.id)
        if not rows:
            return await interaction.response.send_message(embed=utils.info(t("lvl.no_rewards")), ephemeral=True)
        lines = [t("lvl.reward_line", level=r["level"], role=f"<@&{r['role_id']}>") for r in rows]
        await interaction.response.send_message(embed=utils.info(title=t("lvl.rewards_title"), description="\n".join(lines)))


async def setup(bot):
    await bot.add_cog(Leveling(bot))
