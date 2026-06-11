"""Pomocnicze funkcje wspoldzielone przez cogi - glownie budowanie embedow."""
import discord
import config


def embed(title=None, description=None, color=config.COLOR_PRIMARY):
    return discord.Embed(title=title, description=description, color=color)


def success(description, title="Sukces"):
    return discord.Embed(title=f"\u2705 {title}", description=description, color=config.COLOR_SUCCESS)


def error(description, title="Blad"):
    return discord.Embed(title=f"\u274C {title}", description=description, color=config.COLOR_ERROR)


def warning(description, title="Uwaga"):
    return discord.Embed(title=f"\u26A0\uFE0F {title}", description=description, color=config.COLOR_WARNING)


def info(description, title=None):
    return discord.Embed(title=title, description=description, color=config.COLOR_INFO)
