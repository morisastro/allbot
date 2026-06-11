# Discord Bot All-in-One (Polski)

Wielofunkcyjny bot Discord napisany w **Pythonie (discord.py)** ze slash commands i baza **PostgreSQL**.
Gotowy do hostowania **24/7 na Railway**.

## Funkcje

- **Moderacja** – ban, kick, timeout, warn (system ostrzezen), purge, slowmode, lock/unlock
- **Automoderacja** – anty-zaproszenia, anty-linki, anty-spam, zabronione slowa + logi serwera
- **Powitania / pozegnania** – z embedami i placeholderami, autorole dla nowych
- **Leveling** – XP za aktywnosc, rank, leaderboard, role-nagrody za poziomy
- **Ekonomia** – balance, daily, work, gamble, bank (deposit/withdraw), pay, sklep z rolami
- **Role reakcyjne** – panele z przyciskami (persystentne po restarcie)
- **Tickety** – panel z przyciskiem tworzacy prywatne kanaly zgloszen
- **Narzedzia** – poll, giveaway, userinfo, serverinfo, avatar, afk, ping, embed
- **Zabawa** – 8ball, dice, coinflip, meme, hug, slap, say
- **Dwujezycznosc (PL / EN)** – ustaw zmienna `LANGUAGE` na `pl` albo `en`

---

## 1. Tworzenie bota na Discordzie

1. Wejdz na https://discord.com/developers/applications i kliknij **New Application**.
2. Zakladka **Bot** -> **Reset Token** -> skopiuj token (to Twoj `DISCORD_TOKEN`).
3. W sekcji **Privileged Gateway Intents** wlacz:
   - **SERVER MEMBERS INTENT**
   - **MESSAGE CONTENT INTENT**
4. Zakladka **OAuth2 -> URL Generator**: zaznacz `bot` i `applications.commands`,
   nadaj uprawnienia (np. **Administrator** dla wygody) i otworz wygenerowany link,
   aby dodac bota na swoj serwer.

---

## 2. Uruchomienie lokalnie (test)

Wymagania: Python 3.11+ oraz dzialajacy PostgreSQL.

```bash
pip install -r requirements.txt
copy .env.example .env        # Windows  (lub: cp .env.example .env)
```

Uzupelnij `.env`:
```
DISCORD_TOKEN=twoj_token
DATABASE_URL=postgresql://user:haslo@localhost:5432/discordbot
GUILD_ID=id_twojego_serwera   # opcjonalnie - komendy pojawia sie od razu
LANGUAGE=pl                   # jezyk bota: pl albo en
```

Start:
```bash
python bot.py
```

> Wskazowka: ustaw `GUILD_ID` na czas testow – slash commands sa wtedy widoczne
> natychmiast. Bez tego rejestracja globalna moze potrwac do godziny.

---

## 3. Deploy na Railway (24/7)

1. Wrzuc projekt na GitHub.
2. Wejdz na https://railway.app -> **New Project -> Deploy from GitHub repo**.
3. W projekcie kliknij **New -> Database -> PostgreSQL**.
4. Wejdz w serwis bota -> zakladka **Variables**. Dzieki plikowi `railway.toml`
   wszystkie zmienne sa juz przygotowane i czekaja na uzupelnienie:
   - `DISCORD_TOKEN` -> wklej token bota
   - `DATABASE_URL` -> kliknij i wybierz referencje `${{Postgres.DATABASE_URL}}`
   - `GUILD_ID` oraz pozostale ustawienia ekonomii/levelingu sa opcjonalne
     (maja wartosci domyslne - mozna zostawic bez zmian).
5. Railway automatycznie zbuduje i uruchomi bota (`python bot.py`).
   Bot dziala 24/7.

> Bot przy starcie sprawdza zmienne i wypisze w logach dokladnie czego brakuje,
> jesli cos pominiesz.

---

## 4. Pierwsza konfiguracja na serwerze

Po dodaniu bota wykonaj na serwerze:

```
/config logs #logi
/config welcome #powitania Witaj {user} na {server}!
/config autorole @Czlonek
/ticket setup kategoria:Tickety rola_supportu:@Support
/ticket panel
/levels addreward poziom:5 rola:@Aktywny
```

Pelna lista komend: `/help`

---

## Struktura projektu

```
bot.py            # glowny plik (laduje cogi, sync komend)
config.py         # konfiguracja i stale
database.py       # PostgreSQL (asyncpg)
utils.py          # pomocnicze embedy
cogs/
  moderation.py
  automod.py
  welcome.py
  leveling.py
  economy.py
  reaction_roles.py
  tickets.py
  utility.py
  fun.py
```

Aby zmienic wartosci ekonomii/levelingu edytuj `config.py`.
