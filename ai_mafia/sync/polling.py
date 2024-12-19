import asyncio

from bson.objectid import ObjectId

from ai_mafia.db.routines import is_room_ready
from ai_mafia.tg_proxy import send_room_is_ready_signal


async def check_database(room_db_id: ObjectId):
    # TODO make async
    return is_room_ready(room_db_id)


async def poll_database(room_db_id: ObjectId, ctx_id: str, interval: float):
    while True:
        result = await check_database(room_db_id)
        print(f"Database check result: {result}")
        if result:
            print("polling ended")
            send_room_is_ready_signal(ctx_id)
            break
        await asyncio.sleep(interval)


async def start_polling(room_db_id: ObjectId, ctx_id: str, interval: float):
    print("Starting polling...")
    asyncio.create_task(poll_database(room_db_id, ctx_id, interval))  # noqa: RUF006
    print("Polling started.")
