"""Zabawa - 8ball, kostka, rzut moneta, memy, akcje (hug/slap), say."""
import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import utils
from i18n import t

HUG_GIFS = [
    "https://media.tenor.com/9e1aE_xBLCsAAAAC/hug.gif",
    "https://media.tenor.com/kCZjTqCKiggAAAAC/anime-hug.gif",
]
SLAP_GIFS = [
    "https://media.tenor.com/Ws6Dm1ZW_vkAAAAC/anime-slap.gif",
    "https://media.tenor.com/3Wmd5MNRz7gAAAAC/slap.gif",
]


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Magiczna kula. / Magic 8-ball.")
    @app_commands.describe(pytanie="Twoje pytanie / Your question")
    async def eightball(self, interaction: discord.Interaction, pytanie: str):
        e = utils.info(title=f"\U0001F3B1 {t('fun.8ball_title')}")
        e.add_field(name=t("fun.question"), value=pytanie, inline=False)
        e.add_field(name=t("fun.answer"), value=t(f"8ball.{random.randint(1, 12)}"), inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="dice", description="Rzut koscia. / Roll a die.")
    @app_commands.describe(sciany="Liczba scian / Number of sides")
    async def dice(self, interaction: discord.Interaction, sciany: int = 6):
        if sciany < 2:
            return await interaction.response.send_message(embed=utils.error(t("fun.dice_min")), ephemeral=True)
        wynik = random.randint(1, sciany)
        await interaction.response.send_message(embed=utils.info(
            title=f"\U0001F3B2 {t('fun.dice_title')}", description=t("fun.dice_result", result=wynik, sides=sciany)
        ))

    @app_commands.command(name="coinflip", description="Rzut moneta. / Coin flip.")
    async def coinflip(self, interaction: discord.Interaction):
        wynik = t("fun.heads") if random.random() < 0.5 else t("fun.tails")
        await interaction.response.send_message(embed=utils.info(
            title=f"\U0001FA99 {t('fun.coin_title')}", description=t("fun.coin_result", result=wynik)
        ))

    @app_commands.command(name="meme", description="Losowy mem. / Random meme.")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    data = await resp.json()
            e = utils.info(title=data.get("title", t("fun.meme_default")))
            e.set_image(url=data["url"])
            e.set_footer(text=f"r/{data.get('subreddit', '?')}")
            await interaction.followup.send(embed=e)
        except Exception:
            await interaction.followup.send(embed=utils.error(t("fun.meme_fail")))

    @app_commands.command(name="hug", description="Przytul kogos. / Hug someone.")
    @app_commands.describe(user="Kogo / Who")
    async def hug(self, interaction: discord.Interaction, user: discord.Member):
        e = utils.info(description=f"{t('fun.hug', user=interaction.user.mention, target=user.mention)} \U0001F917")
        e.set_image(url=random.choice(HUG_GIFS))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="slap", description="Spoliczkuj kogos. / Slap someone.")
    @app_commands.describe(user="Kogo / Who")
    async def slap(self, interaction: discord.Interaction, user: discord.Member):
        e = utils.info(description=f"{t('fun.slap', user=interaction.user.mention, target=user.mention)} \U0001F44B")
        e.set_image(url=random.choice(SLAP_GIFS))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="say", description="Bot powtarza wiadomosc. / Bot repeats your message.")
    @app_commands.describe(tekst="Co napisac / What to say")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, tekst: str):
        await interaction.channel.send(tekst)
        await interaction.response.send_message(embed=utils.success(t("ut.sent")), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Fun(bot))
