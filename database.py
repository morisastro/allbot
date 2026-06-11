"""Warstwa bazy danych - PostgreSQL przez asyncpg.

Tworzy pule polaczen, inicjalizuje tabele i udostepnia
proste funkcje pomocnicze uzywane przez coggi.
"""
import asyncpg
import config

# Globalna pula polaczen (ustawiana w setup()).
pool: asyncpg.Pool | None = None


SCHEMA = """
-- Ustawienia per serwer (gildia)
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id        BIGINT PRIMARY KEY,
    welcome_channel BIGINT,
    welcome_message TEXT,
    leave_channel   BIGINT,
    leave_message   TEXT,
    autorole_id     BIGINT,
    log_channel     BIGINT,
    level_up_channel BIGINT,
    levels_enabled  BOOLEAN DEFAULT TRUE,
    mute_role_id    BIGINT
);

-- Leveling / XP
CREATE TABLE IF NOT EXISTS levels (
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    xp          BIGINT DEFAULT 0,
    level       INT DEFAULT 0,
    last_xp     DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

-- Nagrody za poziom (rola za osiagniecie poziomu)
CREATE TABLE IF NOT EXISTS level_rewards (
    guild_id    BIGINT NOT NULL,
    level       INT NOT NULL,
    role_id     BIGINT NOT NULL,
    PRIMARY KEY (guild_id, level)
);

-- Ekonomia
CREATE TABLE IF NOT EXISTS economy (
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    balance     BIGINT DEFAULT 0,
    bank        BIGINT DEFAULT 0,
    last_daily  DOUBLE PRECISION DEFAULT 0,
    last_work   DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

-- Przedmioty w sklepie (role do kupienia)
CREATE TABLE IF NOT EXISTS shop_items (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    role_id     BIGINT NOT NULL,
    price       BIGINT NOT NULL,
    name        TEXT NOT NULL
);

-- Ostrzezenia (warny)
CREATE TABLE IF NOT EXISTS warns (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Role reakcyjne (panele z przyciskami)
CREATE TABLE IF NOT EXISTS reaction_roles (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    message_id  BIGINT NOT NULL,
    role_id     BIGINT NOT NULL,
    label       TEXT,
    emoji       TEXT
);

-- Konfiguracja ticketow
CREATE TABLE IF NOT EXISTS ticket_settings (
    guild_id        BIGINT PRIMARY KEY,
    category_id     BIGINT,
    support_role_id BIGINT,
    log_channel     BIGINT,
    ticket_counter  INT DEFAULT 0
);

-- Giveawaye
CREATE TABLE IF NOT EXISTS giveaways (
    message_id  BIGINT PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    channel_id  BIGINT NOT NULL,
    prize       TEXT NOT NULL,
    winners     INT DEFAULT 1,
    end_time    DOUBLE PRECISION NOT NULL,
    host_id     BIGINT NOT NULL,
    ended       BOOLEAN DEFAULT FALSE
);

-- Uczestnicy giveawayow
CREATE TABLE IF NOT EXISTS giveaway_entries (
    message_id  BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    PRIMARY KEY (message_id, user_id)
);

-- AFK
CREATE TABLE IF NOT EXISTS afk (
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    message     TEXT,
    since       DOUBLE PRECISION,
    PRIMARY KEY (guild_id, user_id)
);

-- Automoderacja
CREATE TABLE IF NOT EXISTS automod (
    guild_id        BIGINT PRIMARY KEY,
    anti_invite     BOOLEAN DEFAULT FALSE,
    anti_link       BOOLEAN DEFAULT FALSE,
    anti_spam       BOOLEAN DEFAULT FALSE,
    banned_words    TEXT[]  DEFAULT '{}'
);
"""


async def setup():
    """Tworzy pule polaczen i inicjalizuje tabele."""
    global pool
    pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=10)
    async with pool.acquire() as con:
        await con.execute(SCHEMA)


async def close():
    if pool:
        await pool.close()


# ---------- Helpery ogolne ----------
async def execute(query: str, *args):
    async with pool.acquire() as con:
        return await con.execute(query, *args)


async def fetch(query: str, *args):
    async with pool.acquire() as con:
        return await con.fetch(query, *args)


async def fetchrow(query: str, *args):
    async with pool.acquire() as con:
        return await con.fetchrow(query, *args)


async def fetchval(query: str, *args):
    async with pool.acquire() as con:
        return await con.fetchval(query, *args)


# ---------- Ustawienia gildii ----------
async def get_guild_settings(guild_id: int):
    row = await fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
    if row is None:
        await execute("INSERT INTO guild_settings (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
        row = await fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
    return row


async def set_guild_setting(guild_id: int, column: str, value):
    # column jest kontrolowane wewnetrznie (nigdy z inputu uzytkownika)
    await execute(
        f"INSERT INTO guild_settings (guild_id, {column}) VALUES ($1, $2) "
        f"ON CONFLICT (guild_id) DO UPDATE SET {column} = $2",
        guild_id, value,
    )


# ---------- Ekonomia ----------
async def get_economy(guild_id: int, user_id: int):
    row = await fetchrow(
        "SELECT * FROM economy WHERE guild_id = $1 AND user_id = $2", guild_id, user_id
    )
    if row is None:
        await execute(
            "INSERT INTO economy (guild_id, user_id, balance) VALUES ($1, $2, $3) "
            "ON CONFLICT DO NOTHING",
            guild_id, user_id, config.START_BALANCE,
        )
        row = await fetchrow(
            "SELECT * FROM economy WHERE guild_id = $1 AND user_id = $2", guild_id, user_id
        )
    return row


async def add_balance(guild_id: int, user_id: int, amount: int):
    await get_economy(guild_id, user_id)
    await execute(
        "UPDATE economy SET balance = balance + $3 WHERE guild_id = $1 AND user_id = $2",
        guild_id, user_id, amount,
    )


# ---------- Leveling ----------
async def get_level(guild_id: int, user_id: int):
    row = await fetchrow(
        "SELECT * FROM levels WHERE guild_id = $1 AND user_id = $2", guild_id, user_id
    )
    if row is None:
        await execute(
            "INSERT INTO levels (guild_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            guild_id, user_id,
        )
        row = await fetchrow(
            "SELECT * FROM levels WHERE guild_id = $1 AND user_id = $2", guild_id, user_id
        )
    return row
