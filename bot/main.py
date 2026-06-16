import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-domain.com")


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton(
            "📊 Открыть SMC Trader Pro",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]]
    await update.message.reply_text(
        "👋 *SMC Trader Pro*\n\n"
        "Профессиональный торговый анализ по методологии *Smart Money Concepts*:\n\n"
        "• 📦 Order Blocks\n"
        "• ⚡ Fair Value Gaps (FVG)\n"
        "• 🔄 CHoCH / BOS\n"
        "• 💧 Liquidity Zones\n"
        "• 📐 Multi-Timeframe Analysis\n\n"
        "Нажми кнопку ниже чтобы открыть торговый терминал 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Как пользоваться ботом:*\n\n"
        "1️⃣ Выбери *Крипто* или *Форекс*\n"
        "2️⃣ Выбери торговый инструмент (BTC, ETH, EUR/USD...)\n"
        "3️⃣ Выбери таймфрейм входа (1M / 5M / 15M)\n"
        "4️⃣ Нажми *ПОЛУЧИТЬ СИГНАЛ*\n\n"
        "Бот анализирует рынок на старшем ТФ и находит:\n"
        "• Точку входа\n"
        "• Стоп-лосс\n"
        "• 3 тейк-профита\n"
        "• Риск-менеджмент\n\n"
        "⚠️ _Торговля сопряжена с риском. Всегда используй риск-менеджмент._",
        parse_mode="Markdown",
    )


def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    return app


async def start_bot() -> Application:
    """Initialize and start polling without blocking; for embedding in another asyncio app."""
    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("Bot started (polling)...")
    return app


async def stop_bot(app: Application):
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


def main():
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env")
        return
    app = build_app()
    print("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
