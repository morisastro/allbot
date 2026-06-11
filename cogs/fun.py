"""Zabawa - 8ball, kostka, rzut moneta, memy, akcje (hug/slap), say."""
import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import utils

EIGHTBALL = [
    "Tak.", "Nie.", "Zdecydowanie tak!", "Raczej nie.", "Moze.",
    "Bez watpienia.", "Nie licz na to.", "Pytaj pozniej.",
    "Skup sie i zapytaj ponownie.", "Wszystko na to wskazuje.",
    "Nie moge teraz przewidziec.", "Tak - definitywnie.",
]

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

    @app_commands.command(name="8ball", description="Zadaj pytanie magicznej kuli.")
    @app_commands.describe(pytanie="Twoje pytanie")
    async def eightball(self, interaction: discord.Interaction, pytanie: str):
        e = utils.info(title="\U0001F3B1 Magiczna kula")
        e.add_field(name="Pytanie", value=pytanie, inline=False)
        e.add_field(name="Odpowiedz", value=random.choice(EIGHTBALL), inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="dice", description="Rzuca koscia (1-6 lub podaj liczbe scian).")
    @app_commands.describe(sciany="Liczba scian (domyslnie 6)")
    async def dice(self, interaction: discord.Interaction, sciany: int = 6):
        if sciany < 2:
            return await interaction.response.send_message(embed=utils.error("Min. 2 sciany."), ephemeral=True)
        wynik = random.randint(1, sciany)
        await interaction.response.send_message(embed=utils.info(title="\U0001F3B2 Rzut koscia", description=f"Wypadlo: **{wynik}** (k{sciany})"))

    @app_commands.command(name="coinflip", description="Rzut moneta.")
    async def coinflip(self, interaction: discord.Interaction):
        wynik = random.choice(["Orzel", "Reszka"])
        await interaction.response.send_message(embed=utils.info(title="\U0001FA99 Rzut moneta", description=f"Wypadlo: **{wynik}**"))

    @app_commands.command(name="meme", description="Losowy mem z Reddita.")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    data = await resp.json()
            e = utils.info(title=data.get("title", "Mem"))
            e.set_image(url=data["url"])
            e.set_footer(text=f"r/{data.get('subreddit', '?')}")
            await interaction.followup.send(embed=e)
        except Exception:
            await interaction.followup.send(embed=utils.error("Nie udalo sie pobrac mema. Sprobuj ponownie."))

    @app_commands.command(name="hug", description="Przytul kogos.")
    @app_commands.describe(user="Kogo przytulic")
    async def hug(self, interaction: discord.Interaction, user: discord.Member):
        e = utils.info(description=f"{interaction.user.mention} przytula {user.mention} \U0001F917")
        e.set_image(url=random.choice(HUG_GIFS))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="slap", description="Spoliczkuj kogos (zartem).")
    @app_commands.describe(user="Kogo")
    async def slap(self, interaction: discord.Interaction, user: discord.Member):
        e = utils.info(description=f"{interaction.user.mention} spoliczkowal {user.mention} \U0001F44B")
        e.set_image(url=random.choice(SLAP_GIFS))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="say", description="Bot powtarza Twoja wiadomosc.")
    @app_commands.describe(tekst="Co napisac")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, tekst: str):
        await interaction.channel.send(tekst)
        await interaction.response.send_message(embed=utils.success("Wyslano."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Fun(bot))
