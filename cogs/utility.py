"""Narzedzia - poll, giveaway, userinfo, serverinfo, avatar, afk, ping, help, embed."""
import datetime
import random
import time

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

import config
import database as db
import utils
from i18n import t

NUM_EMOJI = ["1\uFE0F\u20E3", "2\uFE0F\u20E3", "3\uFE0F\u20E3", "4\uFE0F\u20E3", "5\uFE0F\u20E3",
             "6\uFE0F\u20E3", "7\uFE0F\u20E3", "8\uFE0F\u20E3", "9\uFE0F\u20E3", "\U0001F51F"]


class GiveawayJoin(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.join.label = t("ut.giveaway_button")

    @discord.ui.button(emoji="\U0001F389", style=discord.ButtonStyle.primary, custom_id="giveaway:join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ga = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = $1", interaction.message.id)
        if not ga or ga["ended"]:
            return await interaction.followup.send(embed=utils.error(t("ut.giveaway_ended")), ephemeral=True)
        existing = await db.fetchval(
            "SELECT 1 FROM giveaway_entries WHERE message_id = $1 AND user_id = $2",
            interaction.message.id, interaction.user.id,
        )
        if existing:
            await db.execute("DELETE FROM giveaway_entries WHERE message_id = $1 AND user_id = $2",
                             interaction.message.id, interaction.user.id)
            await interaction.followup.send(embed=utils.info(t("ut.giveaway_left")), ephemeral=True)
        else:
            await db.execute("INSERT INTO giveaway_entries (message_id, user_id) VALUES ($1, $2)",
                             interaction.message.id, interaction.user.id)
            await interaction.followup.send(embed=utils.success(t("ut.giveaway_joined")), ephemeral=True)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.check_giveaways.start()

    async def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(GiveawayJoin())

    @app_commands.command(name="ping", description="Opoznienie bota. / Bot latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=utils.info(
            title=f"\U0001F3D3 {t('ut.pong_title')}", description=t("ut.latency", ms=round(self.bot.latency * 1000))
        ))

    @app_commands.command(name="help", description="Lista komend. / Command list.")
    async def help_cmd(self, interaction: discord.Interaction):
        e = utils.info(title=f"\U0001F4D6 {t('ut.help_title')}", description=t("ut.help_desc"))
        e.add_field(name=f"\U0001F6E1 {t('ut.help_mod')}",
                    value="`ban` `unban` `kick` `timeout` `untimeout` `warn` `warnings` `delwarn` `purge` `slowmode` `lock` `unlock`", inline=False)
        e.add_field(name=f"\U0001F916 {t('ut.help_auto')}", value="`automod toggle/addword/delword`", inline=False)
        e.add_field(name=f"\U0001F389 {t('ut.help_lvl')}",
                    value="`rank` `leaderboard` `levels toggle/addreward/delreward/rewards`", inline=False)
        e.add_field(name=f"\U0001F4B0 {t('ut.help_eco')}",
                    value="`balance` `daily` `work` `gamble` `deposit` `withdraw` `pay` `richest` `shop` `buy` `shopadmin ...`", inline=False)
        e.add_field(name=f"\U0001F3AB {t('ut.help_tk')}", value="`ticket setup/panel` `reactionrole create/add`", inline=False)
        e.add_field(name=f"\U0001F6E0 {t('ut.help_ut')}", value="`poll` `giveaway` `userinfo` `serverinfo` `avatar` `afk` `ping` `embed`", inline=False)
        e.add_field(name=f"\U0001F3B2 {t('ut.help_fun')}", value="`8ball` `dice` `coinflip` `meme` `hug` `slap` `say`", inline=False)
        e.add_field(name=f"\u2699 {t('ut.help_cfg')}", value="`config welcome/leave/autorole/logs/levelchannel`", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="poll", description="Tworzy ankiete (opcje przez |). / Creates a poll (options via |).")
    @app_commands.describe(pytanie="Pytanie / Question", opcje="Opcje przez | / Options via | e.g. Yes|No")
    async def poll(self, interaction: discord.Interaction, pytanie: str, opcje: str):
        options = [o.strip() for o in opcje.split("|") if o.strip()]
        if len(options) < 2:
            return await interaction.response.send_message(embed=utils.error(t("ut.poll_min")), ephemeral=True)
        if len(options) > 10:
            return await interaction.response.send_message(embed=utils.error(t("ut.poll_max")), ephemeral=True)
        desc = "\n".join(f"{NUM_EMOJI[i]} {opt}" for i, opt in enumerate(options))
        e = utils.info(title=f"\U0001F4CA {pytanie}", description=desc)
        e.set_footer(text=t("ut.poll_footer", name=interaction.user.display_name))
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(NUM_EMOJI[i])

    @app_commands.command(name="giveaway", description="Tworzy giveaway. / Creates a giveaway.")
    @app_commands.describe(czas_minut="Czas w minutach / Minutes", zwyciezcy="Liczba zwyciezcow / Winners", nagroda="Nagroda / Prize")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, czas_minut: int, zwyciezcy: int, nagroda: str):
        if czas_minut < 1 or zwyciezcy < 1:
            return await interaction.response.send_message(embed=utils.error(t("ut.giveaway_invalid")), ephemeral=True)
        end_time = time.time() + czas_minut * 60
        end_dt = discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=czas_minut), "R")
        e = utils.embed(title=f"\U0001F389 {t('ut.giveaway_title', prize=nagroda)}", color=config.COLOR_PRIMARY,
                        description=t("ut.giveaway_desc", winners=zwyciezcy, end=end_dt, host=interaction.user.mention))
        await interaction.response.send_message(embed=e, view=GiveawayJoin())
        msg = await interaction.original_response()
        await db.execute(
            "INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners, end_time, host_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            msg.id, interaction.guild.id, interaction.channel.id, nagroda, zwyciezcy, end_time, interaction.user.id,
        )

    @tasks.loop(seconds=20)
    async def check_giveaways(self):
        now = time.time()
        rows = await db.fetch("SELECT * FROM giveaways WHERE ended = FALSE AND end_time <= $1", now)
        for ga in rows:
            await db.execute("UPDATE giveaways SET ended = TRUE WHERE message_id = $1", ga["message_id"])
            channel = self.bot.get_channel(ga["channel_id"])
            if not channel:
                continue
            entries = await db.fetch("SELECT user_id FROM giveaway_entries WHERE message_id = $1", ga["message_id"])
            user_ids = [r["user_id"] for r in entries]
            if not user_ids:
                await channel.send(embed=utils.warning(t("ut.giveaway_no_entries", prize=ga["prize"])))
                continue
            winners_count = min(ga["winners"], len(user_ids))
            winners = random.sample(user_ids, winners_count)
            mentions = ", ".join(f"<@{w}>" for w in winners)
            await channel.send(content=mentions, embed=utils.success(
                t("ut.giveaway_winners", prize=ga["prize"]), title=f"\U0001F389 {t('ut.giveaway_results')}"
            ))

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="userinfo", description="Info o uzytkowniku. / User info.")
    @app_commands.describe(user="O kim / About whom")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        e = utils.info(title=t("ut.userinfo_title", user=user))
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name=t("ut.id"), value=str(user.id))
        e.add_field(name=t("ut.nick"), value=user.display_name)
        e.add_field(name=t("ut.is_bot"), value=t("ut.yes") if user.bot else t("ut.no"))
        e.add_field(name=t("ut.created"), value=discord.utils.format_dt(user.created_at, "D"))
        e.add_field(name=t("ut.joined"), value=discord.utils.format_dt(user.joined_at, "D") if user.joined_at else "?")
        roles = [r.mention for r in reversed(user.roles) if r.name != "@everyone"]
        e.add_field(name=t("ut.roles", count=len(roles)), value=" ".join(roles[:15]) or t("common.none"), inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="serverinfo", description="Info o serwerze. / Server info.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        e = utils.info(title=g.name)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name=t("ut.id"), value=str(g.id))
        e.add_field(name=t("ut.owner"), value=g.owner.mention if g.owner else "?")
        e.add_field(name=t("ut.members"), value=str(g.member_count))
        e.add_field(name=t("ut.channels"), value=str(len(g.channels)))
        e.add_field(name=t("ut.roles_count"), value=str(len(g.roles)))
        e.add_field(name=t("ut.boosts"), value=str(g.premium_subscription_count))
        e.add_field(name=t("ut.created_at"), value=discord.utils.format_dt(g.created_at, "D"))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="avatar", description="Awatar uzytkownika. / User avatar.")
    @app_commands.describe(user="Czyj awatar / Whose avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        e = utils.info(title=t("ut.avatar_title", name=user.display_name))
        e.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="embed", description="Tworzy embed (manage server). / Creates an embed.")
    @app_commands.describe(tytul="Tytul / Title", opis="Opis / Description")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def embed_cmd(self, interaction: discord.Interaction, tytul: str, opis: str):
        await interaction.channel.send(embed=utils.info(title=tytul, description=opis.replace("\\n", "\n")))
        await interaction.response.send_message(embed=utils.success(t("ut.sent")), ephemeral=True)

    @app_commands.command(name="afk", description="Ustawia status AFK. / Sets AFK status.")
    @app_commands.describe(powod="Powod / Reason")
    async def afk(self, interaction: discord.Interaction, powod: str = "AFK"):
        await db.execute(
            "INSERT INTO afk (guild_id, user_id, message, since) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (guild_id, user_id) DO UPDATE SET message = $3, since = $4",
            interaction.guild.id, interaction.user.id, powod, time.time(),
        )
        await interaction.response.send_message(embed=utils.info(t("ut.afk_set", reason=powod)))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        row = await db.fetchrow("SELECT 1 FROM afk WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
        if row:
            await db.execute("DELETE FROM afk WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
            try:
                await message.channel.send(embed=utils.success(t("ut.afk_back", user=message.author.mention)), delete_after=5)
            except discord.HTTPException:
                pass
        for member in message.mentions:
            afk_row = await db.fetchrow("SELECT message FROM afk WHERE guild_id = $1 AND user_id = $2", message.guild.id, member.id)
            if afk_row:
                try:
                    await message.channel.send(embed=utils.warning(t("ut.afk_mention", name=member.display_name, reason=afk_row["message"])), delete_after=8)
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(Utility(bot))
