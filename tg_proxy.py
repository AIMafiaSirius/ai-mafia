import logging
import os

import requests
from chatsky import Message
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackContext, CallbackQueryHandler, MessageHandler, filters

from ai_mafia.config import load_config
from ai_mafia.tg_proxy import tg_update_to_chatsky_message

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config().chatsky


async def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        msg = tg_update_to_chatsky_message(update).model_dump(mode="json")
        response = requests.post(config.make_endpoint("chat"), json=msg, timeout=5)  # noqa: ASYNC210
        response.raise_for_status()
        msg = Message(**response.json())
        keyboard = None
        if hasattr(msg, "reply_markup"):
            keyboard = msg.reply_markup
        if update.callback_query is None:
            await update.message.reply_text(msg.text, reply_markup=keyboard)
        else:
            query = update.callback_query
            await query.answer()
            await context.bot.edit_message_text(chat_id=query.message.chat_id, text=msg.text, reply_markup=keyboard,
                                                message_id=query.message.message_id)
    except requests.exceptions.RequestException as e:
        logger.exception("Error sending message to HTTP endpoint: %s", str(e))  # noqa: TRY401
        if update.callback_query is None:
            await update.message.reply_text("Failed to forward the message.")
        else:
            await update.callback_query.answer(text="Failed to forward the message.")


def main() -> None:
    app = ApplicationBuilder().token(os.environ["TG_TOKEN"]).build()

    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(CallbackQueryHandler(handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
