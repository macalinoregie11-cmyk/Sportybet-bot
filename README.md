# SportyBet (Nigeria) Results Bot — Telegram

Tracks matches you pick and DMs you on Telegram the moment they finish.

## Why it's built this way (read this first)

SportyBet doesn't publish an official public API, so there's nothing safe
and stable to call directly. This project uses a third-party *managed*
wrapper (parse.bot) instead of writing a raw HTML scraper, because raw
scrapers break constantly when SportyBet changes their page. That wrapper
also does **not** expose a dedicated "final results" endpoint — nobody's
does, SportyBet doesn't publish one — so the bot infers "finished" by
watching the live-scores feed and noticing when a tracked match drops off
it. That's a reasonable proxy but not instant/perfect; expect it to fire
within one polling interval (default 2 min) after full time.

If you'd rather point this at your own scraper later, everything network-
related lives in `data_source.py` — swap the two functions in there and
the rest of the bot (Telegram commands, DB, notification logic) doesn't
need to change.

**A note on terms of service:** scraping SportyBet (directly or via a
wrapper) for personal, non-redistributed use is a gray area, not a green
light — it can still fall outside their ToS. Keep this for personal use,
don't hammer it with a very short poll interval, and don't resell the data.

## Setup

```bash
cd sportybet_bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

1. **TELEGRAM_BOT_TOKEN** — message [@BotFather](https://t.me/BotFather) on
   Telegram, send `/newbot`, follow the prompts, paste the token it gives you.
2. **TELEGRAM_CHAT_ID** — send your new bot any message, then open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   copy the number in `"chat":{"id": ...}`.
3. **SPORTY_API_KEY** — sign up free at [parse.bot](https://parse.bot),
   find the "SportyBet API" in their marketplace, grab an API key (free
   tier: 200 credits/month, 5 req/min — fine for personal use).

## Run it

```bash
python bot.py
```

In Telegram:

- `/track arsenal` → bot shows upcoming Arsenal matches as buttons → tap one
- `/list` → see what you're tracking
- `/untrack 3` → stop tracking match id 3

## If notifications don't fire

The live-feed's score field names aren't officially documented anywhere,
so `data_source.py` guesses common spellings (`home_score`, `homeScore`,
etc.). If a real match finishes and you never get a message, run this
during a live match to see the actual JSON and fix the key names in
`HOME_SCORE_KEYS` / `AWAY_SCORE_KEYS` / `STATUS_KEYS`:

```bash
python -c "from data_source import debug_dump_live_event; debug_dump_live_event()"
```

## Files

- `bot.py` — Telegram commands + polling loop
- `data_source.py` — all SportyBet-facing network calls (swap this to change data source)
- `db.py` — SQLite storage for tracked matches
- `.env.example` — config template
