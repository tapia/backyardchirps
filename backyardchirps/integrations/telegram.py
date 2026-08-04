import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.types import URLInputFile

logger = logging.getLogger(__name__)


async def send_photo_and_audio(
    token: str,
    chat_id: str,
    photo: BufferedInputFile | URLInputFile,
    caption: str,
    audio: BufferedInputFile,
) -> None:
    """
    Send a photo with its caption, then the audio. Errors are logged and go no further,
    so that Telegram being down cannot stop the recording loop.
    """
    bot = Bot(token=token)
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode="HTML",
        )
        logger.info("Telegram photo sent")
        await bot.send_audio(
            chat_id=chat_id,
            audio=audio,
        )
    except Exception:
        logger.exception("Failed to send Telegram notification")
    finally:
        await bot.session.close()
