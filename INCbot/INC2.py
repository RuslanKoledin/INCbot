import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import asyncio

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

incidents = {}
event_loop = None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    print(f"Получено сообщение: {text} в чате {chat_id}")

    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
        incident_id = f"{chat_id}_{now.timestamp()}"
        incidents[incident_id] = {
            "text": text,
            "chat_id": chat_id,
            "time": now,
        }

        print(f"Обнаружен инцидент: {incident_id}")

        # Всегда пересылаем в группы
        for group_id in [-1002591060921, -1002631818202]:
            print(f"Пересылаю в группу {group_id} - IVR_Monitoring, ADM")
            await context.bot.send_message(chat_id=group_id, text=text)

        # Проверяем уровень инцидента в тексте
        if ("Средний" not in text) and ("Низкий" not in text):
            # Только если уровень Высокий или Наивысший - ставим напоминания
            scheduler.add_job(
                notify_50_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=10),  # для теста
                args=[context.application, chat_id, incident_id]
            )
            scheduler.add_job(
                notify_60_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=20),  # для теста
                args=[context.application, chat_id, incident_id]
            )
        else:
            print("Уровень инцидента Средний/Низкий - напоминания не ставим.")
    else:
        print("Сообщение не содержит инцидент.")

def notify_50_minutes(application, chat_id, incident_id):
    global event_loop
    if event_loop is None:
        print("Event loop не установлен!")
        return
    print(f"Напоминание через 50 минут для инцидента {incident_id}")
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text="С момента создания прошло 50 минут, через 10 минут надо оповестить. @PR @"
        ),
        event_loop
    )

def notify_60_minutes(application, chat_id, incident_id):
    global event_loop
    if event_loop is None:
        print("Event loop не установлен!")
        return
    print(f"Напоминание через 60 минут для инцидента {incident_id}")
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text="Оповестите! @PR @Ruslank1111!!"
        ),
        event_loop
    )

if __name__ == '__main__':
    application = ApplicationBuilder().token("7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ").build()
    event_loop = asyncio.get_event_loop()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Запускаем бота...")
    asyncio.run(application.run_polling())
