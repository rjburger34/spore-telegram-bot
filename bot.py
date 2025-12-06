import os
import requests
import asyncio

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
    CommandHandler,
)
from openai import OpenAI


# --- Load config from environment variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")  # e.g. SporeLoreBot (NO @)

if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN env var is not set.")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY env var is not set.")
if not BOT_USERNAME:
    print("ERROR: BOT_USERNAME env var is not set.")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Load community lore / history file ---
# --- Load all knowledge files from /knowledge ---
def load_knowledge():
    knowledge_dir = "knowledge"
    parts = []
    if os.path.isdir(knowledge_dir):
        for name in sorted(os.listdir(knowledge_dir)):
            if name.lower().endswith(".md"):
                path = os.path.join(knowledge_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    parts.append(f"# From {name}\n\n{content}")
                except Exception as e:
                    print(f"Could not read {path}: {e}")
    if not parts:
        return "No knowledge files yet. Add .md files under the knowledge/ folder."
    return "\n\n---\n\n".join(parts)

KNOWLEDGE = load_knowledge()

# --- Price config and fetcher ---

import requests  # Required for API calls

TOKEN_CONFIG = {
    "BTC": {"id": "bitcoin", "label": "Bitcoin"},
    "ETH": {"id": "ethereum", "label": "Ethereum"},
    "FUNGI": {"id": "fungi", "label": "Fungi"},
    "FROGGI": {"id": "froggi", "label": "Froggi"},
    "PEPI": {"id": "pepi-2", "label": "Pepi"},
    "JELLI": {"id": "jelli", "label": "Jelli"},
}


COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


def fetch_prices():
    """Fetch current price + 24h change for configured tokens."""
    if not TOKEN_CONFIG:
        return {}

    ids = ",".join(cfg["id"] for cfg in TOKEN_CONFIG.values())

    params = {
        "ids": ids,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }

    try:
        resp = requests.get(COINGECKO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Price fetch error:", e)
        return {}

    results = {}
    for symbol, cfg in TOKEN_CONFIG.items():
        cid = cfg["id"]
        if cid not in data:
            continue
        entry = data[cid]
        price = entry.get("usd")
        change = entry.get("usd_24h_change")
        results[symbol] = {
            "label": cfg["label"],
            "price": price,
            "change": change,
        }

    return results


def message_mentions_bot(message_text: str, entities, bot_username: str) -> bool:
    """Return True if the message explicitly @mentions this bot."""
    if not entities or not message_text:
        return False

    for ent in entities:
        if ent.type == "mention":
            mention_text = message_text[ent.offset : ent.offset + ent.length]
            if mention_text.lstrip("@").lower() == bot_username.lower():
                return True
    return False


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or msg.text is None:
        return

    text = msg.text

    # 1) Trigger on @mention
    mentioned = message_mentions_bot(text, msg.entities, BOT_USERNAME)

    # 2) Trigger if user is replying directly to the bot
    is_reply_to_bot = (
        msg.reply_to_message is not None
        and msg.reply_to_message.from_user is not None
        and msg.reply_to_message.from_user.id == context.bot.id
    )

    if not (mentioned or is_reply_to_bot):
        # Ignore everything else in the group
        return

    # Build the question we send to the LLM
    if mentioned:
        clean_question = text.replace(f"@{BOT_USERNAME}", "").strip()
    else:
        clean_question = text.strip()

    if not clean_question:
        clean_question = "They pinged you without any text. Say hi and explain what you can do."

    user_handle = msg.from_user.username or msg.from_user.first_name

    # --- System prompt (personality + knowledge) ---
    system_prompt = (
    "You are Spore, a semi-sentient mushroom archivist and lore keeper for an "
    "ERC-20i / Base Telegram community.\n"
    "- You speak like a friendly crypto degen (CT tone) but stay helpful and positive.\n"
    "- You explain the community's history, culture, key events, characters, memes, links, and tools.\n"
    "- Keep replies short and group-chat friendly (1–3 short paragraphs or a few lines).\n"
    "- If you don't know something, say you're not sure and suggest asking mods or checking official resources.\n\n"
    "Below is ALL community knowledge loaded from the /knowledge folder, including history, links, docs, characters, memes, FAQs, and ecosystem info:\n\n"
    f"{KNOWLEDGE}\n\n"
    "Use this knowledge when helpful. If a user asks for official links, socials, website, docs, or tools, pull the answer directly from the links.md file."
)

    user_prompt = (
        f"Telegram user @{user_handle} asked or said:\n"
        f"{clean_question}\n\n"
        "Reply as Spore in a busy group chat. Address them directly, keep it casual and concise."
    )

    # --- Call OpenAI LLM ---
    try:
        completion = client.chat.completions.create(
            model="gpt-4.1-mini",  # or gpt-4.1-nano if you want cheaper
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=250,
            temperature=0.8,
        )
        reply_text = completion.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        reply_text = "My spores are clogged rn, try again in a bit."

    # Reply to the user in chat
    await msg.reply_text(f"@{user_handle} {reply_text}")

# --- /prices command handler ---

async def prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current prices and 24h changes."""
    await update.message.chat.send_chat_action("typing")

    data = fetch_prices()
    if not data:
        await update.message.reply_text("Could not fetch prices rn, spores are tired.")
        return

    lines = ["📊 *Market Spores* (USD, 24h change)\n"]
    for symbol, info in data.items():
        price = info["price"]
        change = info["change"]

        if price is None:
            continue

        # Format price
        if price >= 1:
            price_str = f"${price:,.2f}"
        else:
            price_str = f"${price:.6f}"

        # Format change with emoji
        if change is None:
            emoji = "➖"
            change_str = "n/a"
        else:
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"{change:+.2f}%"

        label = info["label"]
        lines.append(f"{emoji} *{label}* ({symbol}): {price_str}  ({change_str})")

    text = "\n".join(lines)
    await update.message.reply_markdown(text)

# --- /prices command handler ---

async def prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current prices and 24h changes."""
    msg = update.message
    if msg is None:
        return

    await msg.chat.send_chat_action("typing")

    data = fetch_prices()
    if not data:
        await msg.reply_text("Could not fetch prices rn, spores are tired.")
        return

    lines = ["📊 *Market Spores* (USD, 24h change)\n"]
    for symbol, info in data.items():
        price = info["price"]
        change = info["change"]

        if price is None:
            continue

        # Format price
        if price >= 1:
            price_str = f"${price:,.2f}"
        else:
            price_str = f"${price:.6f}"

        # Format change with emoji
        if change is None:
            emoji = "➖"
            change_str = "n/a"
        else:
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"{change:+.2f}%"

        label = info["label"]
        lines.append(f"{emoji} *{label}* ({symbol}): {price_str}  ({change_str})")

    text = "\n".join(lines)
    await msg.reply_markdown(text)


def main():
    # Create and set an explicit event loop (needed for Python 3.14)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if not TELEGRAM_TOKEN or not OPENAI_API_KEY or not BOT_USERNAME:
        print("Missing required environment variables. Exiting.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Listen to all text messages; our handler decides when to respond
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))

    # /prices command
    app.add_handler(CommandHandler("prices", prices))
    
    print("Spore Telegram agent is running...")
    app.run_polling()  # uses the loop we just set


if __name__ == "__main__":
    main()
