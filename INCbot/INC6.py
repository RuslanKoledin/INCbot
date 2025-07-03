import datetime
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

incidents = {}

def get_incident_key(text: str, chat_id: int) -> str:
    for key, value in incidents.items():
        if value["chat_id"] == chat_id and value["text"] in text:
            return key
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    print(f"Получено сообщение: {text} в чате {chat_id}")

    # Создание нового инцидента
    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
        incident_key = f"{chat_id}_{now.timestamp()}"
        incidents[incident_key] = {
            "text": text,
            "chat_id": chat_id,
            "time": now,
            "jobs": []
        }

        print(f"Обнаружен инцидент: {incident_key}")

        for group_id in [-1002591060921, -1002631818202]:
            await context.bot.send_message(chat_id=group_id, text=text)

        if ("Средний" not in text) and ("Низкий" not in text):
            job50 = scheduler.add_job(
                notify_50_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=30),  # 30 секунд
                args=[context.application, chat_id, incident_key]
            )
            job60 = scheduler.add_job(
                notify_60_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=60),  # 60 секунд (1 минута)
                args=[context.application, chat_id, incident_key]
            )
            incidents[incident_key]["jobs"] = [job50.id, job60.id]
        else:
            print("Средний/Низкий приоритет — напоминания не ставим.")

    # Изменение приоритета
    elif "Приоритет инцидента поднят до" in text or "Приоритет инцидента понижен до" in text:
        if update.message.reply_to_message:
            replied_text = update.message.reply_to_message.text
            incident_key = get_incident_key(replied_text, chat_id)
            if not incident_key or incident_key not in incidents:
                print("❌ Не удалось найти связанный инцидент.")
                return

            incident = incidents[incident_key]

            if "поднят до" in text and ("Высокий" in text or "Наивысший" in text):
                print(f"🔼 Приоритет инцидента {incident_key} повышен.")
                if not incident["jobs"]:
                    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
                    # При повышении приоритета — напоминания через 30 и 60 секунд от текущего времени
                    job50 = scheduler.add_job(
                        notify_50_minutes,
                        trigger='date',
                        run_date=now + datetime.timedelta(seconds=30),
                        args=[context.application, chat_id, incident_key]
                    )
                    job60 = scheduler.add_job(
                        notify_60_minutes,
                        trigger='date',
                        run_date=now + datetime.timedelta(seconds=60),
                        args=[context.application, chat_id, incident_key]
                    )
                    incident["jobs"] = [job50.id, job60.id]
                    print("✅ Напоминания установлены после повышения приоритета.")

            elif "понижен до" in text and ("Средний" in text or "Низкий" in text):
                print(f"🔽 Приоритет инцидента {incident_key} понижен. Удаляем напоминания.")
                for job_id in incident["jobs"]:
                    scheduler.remove_job(job_id)
                incident["jobs"] = []
        else:
            print("❌ Сообщение не является ответом на инцидент.")

    # Закрытие инцидента (например, по слову "заработал")
    elif "заработал" in text.lower():
        if update.message.reply_to_message:
            replied_text = update.message.reply_to_message.text
            incident_key = get_incident_key(replied_text, chat_id)
            if incident_key and incident_key in incidents:
                print(f"✅ Инцидент {incident_key} закрыт — отменяем напоминания.")
                for job_id in incidents[incident_key]["jobs"]:
                    scheduler.remove_job(job_id)
                incidents[incident_key]["jobs"] = []

def notify_50_minutes(application, chat_id, incident_key):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if incident_key in incidents and incidents[incident_key]["jobs"]:
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=chat_id,
                text="Прошло 50 минут с момента инцидента. Через 10 минут нужно оповестить. @PR @"
            ),
            loop
        )

def notify_60_minutes(application, chat_id, incident_key):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if incident_key in incidents and incidents[incident_key]["jobs"]:
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=chat_id,
                text="Оповестите! @PR @Ruslank1111!!"
            ),
            loop
        )

if __name__ == '__main__':
    application = ApplicationBuilder().token("7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ").build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Запускаем бота...")
    application.run_polling()
