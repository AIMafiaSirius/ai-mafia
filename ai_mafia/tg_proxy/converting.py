from chatsky.core.message import (
    Animation,
    Audio,
    Contact,
    Document,
    Image,
    Invoice,
    Location,
    Message,
    Poll,
    PollOption,
    Sticker,
    Video,
    VideoMessage,
    VoiceMessage,
)
from telegram import Update


def tg_update_to_chatsky_message(update: Update) -> Message:  # noqa: C901
    """
    Convert Telegram update to Chatsky message.
    Extract text and supported attachments.

    :param update: Telegram update object.
    :return: Chatsky message object.
    """

    message = Message()
    message.attachments = []

    tg_msg = update.message
    message.text = tg_msg.text or tg_msg.caption
    if tg_msg.location is not None:
        message.attachments += [Location(latitude=tg_msg.location.latitude, longitude=tg_msg.location.longitude)]
    if tg_msg.contact is not None:
        message.attachments += [
            Contact(
                phone_number=tg_msg.contact.phone_number,
                first_name=tg_msg.contact.first_name,
                last_name=tg_msg.contact.last_name,
                user_id=tg_msg.contact.user_id,
            )
        ]
    if tg_msg.invoice is not None:
        message.attachments += [
            Invoice(
                title=tg_msg.invoice.title,
                description=tg_msg.invoice.description,
                currency=tg_msg.invoice.currency,
                amount=tg_msg.invoice.total_amount,
            )
        ]
    if tg_msg.poll is not None:
        message.attachments += [
            Poll(
                question=tg_msg.poll.question,
                options=[PollOption(text=option.text, votes=option.voter_count) for option in tg_msg.poll.options],
                is_closed=tg_msg.poll.is_closed,
                is_anonymous=tg_msg.poll.is_anonymous,
                type=tg_msg.poll.type,
                multiple_answers=tg_msg.poll.allows_multiple_answers,
                correct_option_id=tg_msg.poll.correct_option_id,
                explanation=tg_msg.poll.explanation,
                open_period=tg_msg.poll.open_period,
            )
        ]
    if tg_msg.sticker is not None:
        message.attachments += [
            Sticker(
                id=tg_msg.sticker.file_id,
                is_animated=tg_msg.sticker.is_animated,
                is_video=tg_msg.sticker.is_video,
                type=tg_msg.sticker.type,
            )
        ]
    if tg_msg.audio is not None:
        thumbnail = (
            Image(id=tg_msg.audio.thumbnail.file_id, file_unique_id=tg_msg.audio.thumbnail.file_unique_id)
            if tg_msg.audio.thumbnail is not None
            else None
        )
        message.attachments += [
            Audio(
                id=tg_msg.audio.file_id,
                file_unique_id=tg_msg.audio.file_unique_id,
                duration=tg_msg.audio.duration,
                performer=tg_msg.audio.performer,
                file_name=tg_msg.audio.file_name,
                mime_type=tg_msg.audio.mime_type,
                thumbnail=thumbnail,
            )
        ]
    if tg_msg.video is not None:
        thumbnail = (
            Image(id=tg_msg.video.thumbnail.file_id, file_unique_id=tg_msg.video.thumbnail.file_unique_id)
            if tg_msg.video.thumbnail is not None
            else None
        )
        message.attachments += [
            Video(
                id=tg_msg.video.file_id,
                file_unique_id=tg_msg.video.file_unique_id,
                width=tg_msg.video.width,
                height=tg_msg.video.height,
                duration=tg_msg.video.duration,
                file_name=tg_msg.video.file_name,
                mime_type=tg_msg.video.mime_type,
                thumbnail=thumbnail,
            )
        ]
    if tg_msg.animation is not None:
        thumbnail = (
            Image(id=tg_msg.animation.thumbnail.file_id, file_unique_id=tg_msg.animation.thumbnail.file_unique_id)
            if tg_msg.animation.thumbnail is not None
            else None
        )
        message.attachments += [
            Animation(
                id=tg_msg.animation.file_id,
                file_unique_id=tg_msg.animation.file_unique_id,
                width=tg_msg.animation.width,
                height=tg_msg.animation.height,
                duration=tg_msg.animation.duration,
                file_name=tg_msg.animation.file_name,
                mime_type=tg_msg.animation.mime_type,
                thumbnail=thumbnail,
            )
        ]
    if len(tg_msg.photo) > 0:
        message.attachments += [
            Image(
                id=picture.file_id,
                file_unique_id=picture.file_unique_id,
                width=picture.width,
                height=picture.height,
            )
            for picture in tg_msg.photo
        ]
    if tg_msg.document is not None:
        thumbnail = (
            Image(id=tg_msg.document.thumbnail.file_id, file_unique_id=tg_msg.document.thumbnail.file_unique_id)
            if tg_msg.document.thumbnail is not None
            else None
        )
        message.attachments += [
            Document(
                id=tg_msg.document.file_id,
                file_unique_id=tg_msg.document.file_unique_id,
                file_name=tg_msg.document.file_name,
                mime_type=tg_msg.document.mime_type,
                thumbnail=thumbnail,
            )
        ]
    if tg_msg.voice is not None:
        message.attachments += [
            VoiceMessage(
                id=tg_msg.voice.file_id,
                file_unique_id=tg_msg.voice.file_unique_id,
                mime_type=tg_msg.voice.mime_type,
            )
        ]
    if tg_msg.video_note is not None:
        thumbnail = (
            Image(id=tg_msg.video_note.thumbnail.file_id, file_unique_id=tg_msg.video_note.thumbnail.file_unique_id)
            if tg_msg.video_note.thumbnail is not None
            else None
        )
        message.attachments += [
            VideoMessage(
                id=tg_msg.video_note.file_id,
                file_unique_id=tg_msg.video_note.file_unique_id,
                thumbnail=thumbnail,
            )
        ]

    message.original_message = update.to_dict()

    return message
