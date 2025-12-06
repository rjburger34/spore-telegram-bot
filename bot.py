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


# --- Natural-language price detection helpers ---

# Map canonical symbols (keys from TOKEN_CONFIG) to aliases people will type
TOKEN_ALIASES = {
    "BTC": ["btc", "$btc", "bitcoin"],
    "ETH": ["eth", "$eth", "ethereum"],
    "FUNGI": ["fungi", "$fungi"],
    "FROGGI": ["froggi", "$froggi"],
    "PEPI": ["pepi", "$pepi"],
    "JELLI": ["jelli", "$jelli"],
}

PRICE_KEYWORDS = [
    "price",
    "how much",
    "worth",
    "cost",
    "trading at",
    "going for",
    "quote",
]


def extract_price_request_tokens(message_text: str) -> list[str]:
    """
    Returns a list of canonical token symbols (e.g. ["FUNGI", "PEPI"])
    if the message looks like a price request for those tokens.
    """
    if not message_text:
        return []

    text = message_text.lower()

    # Only treat it as a price query if at least one keyword appears
    if not any(keyword in text for keyword in PRICE_KEYWORDS):
        return []

    requested = []
    for symbol, aliases in TOKEN_ALIASES.items():
        for alias in aliases:
            if alias in text:
                requested.append(symbol)
                break  # don't double-add the same symbol

    return requested


def build_price_line(requested_symbols: list[str]) -> str | None:
    """
    Uses fetch_prices() and returns a single-line string like:
    '🟢 FROGGI: $0.002077 (+3.45%) | 🔴 FUNGI: $0.000123 (-1.23%)'
    Only includes tokens that were successfully priced.
    """
    if not requested_symbols:
        return None

    all_prices = fetch_prices()
    print("[DEBUG] all_prices keys:", list(all_prices.keys()))
    if not all_prices:
        return None

    parts = []
    for symbol in requested_symbols:
        symbol = symbol.upper()
        info = all_prices.get(symbol)
        if not info:
            print(f"[DEBUG] no price info for {symbol}")
            continue

        price = info.get("price")
        change = info.get("change")

        if price is None:
            print(f"[DEBUG] price is None for {symbol}")
            continue

        # Format price
        if price >= 1:
            price_str = f"${price:,.2f}"
        else:
            price_str = f"${price:.6f}"

        # Format 24h change like /prices
        if change is None:
            emoji = "➖"
            change_str = "n/a"
        else:
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"{change:+.2f}%"

        parts.append(f"{emoji} {symbol}: {price_str} ({change_str})")

    if not parts:
        print("[DEBUG] no parts built for price line")
        return None

    line = " | ".join(parts)
    print("[DEBUG] final price line:", line)
    return line

    if not requested_symbols:
        return None

    all_prices = fetch_prices()
    if not all_prices:
        return None

    parts = []
    for symbol in requested_symbols:
        symbol = symbol.upper()
        info = all_prices.get(symbol)
        if not info:
            continue

        price = info.get("price")
        if price is None:
            continue

        # Format price
        if price >= 1:
            price_str = f"${price:,.2f}"
        else:
            price_str = f"${price:.6f}"

        parts.append(f"{symbol}: {price_str}")

    if not parts:
        return None

    return " | ".join(parts)


# --- Core helpers ---


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

    # --- Natural-language price handling ---
    requested_symbols = extract_price_request_tokens(clean_question)
    if requested_symbols:
        price_line = build_price_line(requested_symbols)
        if price_line:
            # Single-line price response, tagged to the user
            await msg.reply_text(f"@{user_handle} {price_line}")
            return
        else:
            # It *is* a price question for tokens we recognize,
            # but we couldn't fetch a price (likely API / ID issue).
            # Do NOT fall back to LLM, or it will spam DexTools links.
            await msg.reply_text(
                f"@{user_handle} I can’t fetch live prices for those spores rn. "
                "Try /prices or double-check if they’re listed on CoinGecko."
            )
            return


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


# --- /prices command handler (full market view) ---

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
