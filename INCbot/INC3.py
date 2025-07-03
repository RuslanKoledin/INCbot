import datetime
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

# Инициализация планировщика с таймзоной Бишкек
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

# Хранилище инцидентов
incidents = {}
event_loop = None

def extract_incident_key(text: str) -> str:
    match = re.search(r'Инцидент:([^\n\r]+)', text)
    return match.group(1).strip() if match else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
    incident_key = extract_incident_key(text)

    if not incident_key:
        print("❌ Не удалось извлечь ключ инцидента.")
        return

    incident_id = f"{chat_id}_{incident_key}"

    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        print(f"✅ Инцидент обнаружен: {incident_key}")
        priority = "Высокий" if "Высокий" in text else "Наивысший" if "Наивысший" in text else "Средний"
        incidents[incident_id] = {
            "text": text,
            "chat_id": chat_id,
            "incident_key": incident_key,
            "time": now,
            "priority": priority,
            "jobs": []
        }

        # Всегда пересылаем
        for group_id in [-1002591060921, -1002631818202]:
            await context.bot.send_message(chat_id=group_id, text=text)

        if priority in ["Высокий", "Наивысший"]:
            j1 = scheduler.add_job(notify_50_minutes, 'date', run_date=now + datetime.timedelta(seconds=10),
                                   args=[context.application, chat_id, incident_id])
            j2 = scheduler.add_job(notify_60_minutes, 'date', run_date=now + datetime.timedelta(seconds=20),
                                   args=[context.application, chat_id, incident_id])
            incidents[incident_id]["jobs"] = [j1.id, j2.id]

    elif "Приоритет инцидента поднят до" in text and incident_id in incidents:
        inc = incidents[incident_id]
        if inc["priority"] in ["Средний", "Низкий"]:
            inc["priority"] = "Высокий"
            j1 = scheduler.add_job(notify_50_minutes, 'date', run_date=inc["time"] + datetime.timedelta(minutes=50),
                                   args=[context.application, chat_id, incident_id])
            j2 = scheduler.add_job(notify_60_minutes, 'date', run_date=inc["time"] + datetime.timedelta(minutes=60),
                                   args=[context.application, chat_id, incident_id])
            inc["jobs"] = [j1.id, j2.id]
            print(f"🔺 Приоритет поднят, запланированы уведомления от {inc['time']}")

    elif "Приоритет инцидента понижен до" in text and incident_id in incidents:
        inc = incidents[incident_id]
        if inc["priority"] == "Высокий":
            inc["priority"] = "Средний"
            for job_id in inc["jobs"]:
                try:
                    scheduler.remove_job(job_id)
                except:
                    pass
            inc["jobs"] = []
            print("🔻 Приоритет понижен, задачи удалены.")

def notify_50_minutes(application, chat_id, incident_id):
    global event_loop
    if event_loop:
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=chat_id,
                text="С момента создания прошло 50 минут, через 10 минут надо оповестить. @PR @"
            ),
            event_loop
        )

def notify_60_minutes(application, chat_id, incident_id):
    global event_loop
    if event_loop:
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=chat_id,
                text="Оповестите! @PR @Ruslank1111!!"
            ),
            event_loop
        )

if __name__ == '__main__':
    application = ApplicationBuilder().token("7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ").build()

    # Правильное создание event loop
    try:
        event_loop = asyncio.get_running_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Запускаем бота...")
    asyncio.run(application.run_polling())
