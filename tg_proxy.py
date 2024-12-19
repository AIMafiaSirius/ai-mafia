import logging
import os

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackContext, MessageHandler, filters

from ai_mafia.config import load_config
from ai_mafia.tg_proxy import tg_update_to_chatsky_message

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config().chatsky


async def handle_message(update: Update, _: CallbackContext) -> None:
    try:
        msg = tg_update_to_chatsky_message(update).model_dump(mode="json")
        response = requests.post(config.chat_endpoint, json=msg, timeout=5)  # noqa: ASYNC210
        response.raise_for_status()
        await update.message.reply_text(response.json()["text"])
    except requests.exceptions.RequestException as e:
        logger.exception("Error sending message to HTTP endpoint: %s", str(e))  # noqa: TRY401
        await update.message.reply_text("Failed to forward the message.")


def main() -> None:
    app = ApplicationBuilder().token(os.environ["TG_TOKEN"]).build()

    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()