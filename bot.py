"""
SportyBet Nigeria results-alert bot for Telegram.

Commands:
  /start                 - welcome + instructions
  /track <team query>    - search upcoming matches and pick one to track
  /list                  - show matches you're currently tracking
  /untrack <id>          - stop tracking a match (id shown in /list)

Once a tracked match goes live and then finishes, you get a Telegram
message with the final score.
"""
import logging
import os

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import db
import data_source

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("sportybet-bot")

# In-memory cache of the last search results per chat, so the inline
# buttons in /track know which event_id each button maps to.
_LAST_SEARCH = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SportyBet results bot.\n\n"
        "/track <team name> — find and follow an upcoming match\n"
        "/list — see what you're tracking\n"
        "/untrack <id> — stop tracking\n\n"
        "You'll get a message here the moment a tracked match finishes."
    )


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /track arsenal")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"Searching upcoming matches for '{query}'...")

    try:
        results = data_source.search_upcoming_events(query)
    except Exception as e:
        log.exception("search failed")
        await update.message.reply_text(f"Couldn't reach the odds feed: {e}")
        return

    if not results:
        await update.message.reply_text("No upcoming matches found for that team.")
        return

    results = results[:8]  # keep the keyboard small
    chat_id = update.effective_chat.id
    _LAST_SEARCH[chat_id] = {r["event_id"]: r for r in results}

    buttons = [
        [
            InlineKeyboardButton(
                f"{r['home_team']} vs {r['away_team']}",
                callback_data=f"pick:{r['event_id']}",
            )
        ]
        for r in results
    ]
    await update.message.reply_text(
        "Pick the match to track:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    event_id = query.data.split("pick:", 1)[1]

    match = _LAST_SEARCH.get(chat_id, {}).get(event_id)
    if not match:
        await query.edit_message_text("That search expired, run /track again.")
        return

    db.add_tracked_match(
        chat_id=chat_id,
        event_id=match["event_id"],
        home_team=match["home_team"],
        away_team=match["away_team"],
        start_time=match["start_time"],
    )
    await query.edit_message_text(
        f"Tracking {match['home_team']} vs {match['away_team']}. "
        f"You'll be notified when it finishes."
    )


async def list_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.list_tracked_matches(chat_id)
    if not rows:
        await update.message.reply_text("You're not tracking anything right now.")
        return
    lines = [f"#{r['id']}: {r['home_team']} vs {r['away_team']}" for r in rows]
    await update.message.reply_text("\n".join(lines))


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /untrack <id>  (see /list for ids)")
        return
    chat_id = update.effective_chat.id
    try:
        row_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("id must be a number, see /list")
        return
    ok = db.remove_tracked_match(row_id, chat_id)
    await update.message.reply_text("Removed." if ok else "Couldn't find that id.")


async def poll_job(context: ContextTypes.DEFAULT_TYPE):
    """Runs every POLL_INTERVAL seconds. Checks tracked matches against the
    live-events feed. A match that WAS live and has now dropped off the
    live list is treated as finished."""
    pending = db.all_pending_matches()
    if not pending:
        return

    try:
        live = data_source.get_live_events()
    except Exception:
        log.exception("poll: failed to fetch live events")
        return

    for m in pending:
        eid = m["event_id"]
        raw = live.get(eid)

        if raw is not None:
            # still live — remember latest score, not finished yet
            home, away, status = data_source.extract_score(raw)
            db.mark_seen_live(m["id"], home, away)
            continue

        if not m["seen_live"]:
            # never observed live yet (maybe hasn't kicked off) — keep waiting
            continue

        # was live, now gone from the live feed => finished
        home = m["last_home_score"] or "?"
        away = m["last_away_score"] or "?"
        text = (
            f"FULL TIME: {m['home_team']} {home} - {away} {m['away_team']}"
        )
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=text)
        except Exception:
            log.exception("failed to send result notification")
        db.mark_notified(m["id"])


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in your .env file first.")

    db.init_db()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("list", list_tracked))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CallbackQueryHandler(pick_callback, pattern=r"^pick:"))

    app.job_queue.run_repeating(poll_job, interval=POLL_INTERVAL, first=10)

    log.info("Bot started, polling every %ss", POLL_INTERVAL)
    app.run_polling()


if __name__ == "__main__":
    main()
