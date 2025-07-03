import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import asyncio
import re

import os

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

incidents = {}
event_loop = None

def extract_key(text):
    match = re.search(r'Инцидент:\s*(.+?)\n', text)
    return match.group(1).strip() if match else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    reply_to = update.message.reply_to_message

    print(f"Получено сообщение: {text} в чате {chat_id}")

    # 🟠 Обработка закрытия инцидента
    if reply_to and any(x in text.lower() for x in ["заработал", "устранено", "решено"]):
        replied_text = reply_to.text
        key = extract_key(replied_text)
        if not key:
            print("❌ Не удалось извлечь ключ инцидента.")
            return

        incident_id = f"{chat_id}_{key}"
        incident = incidents.get(incident_id)

        if incident:
            print(f"🔕 Инцидент '{key}' закрыт. Отменяю напоминания.")
            for job_id in incident.get("jobs", []):
                scheduler.remove_job(job_id)
            del incidents[incident_id]
        else:
            print(f"⚠️ Инцидент '{key}' не найден.")
        return

    # 🟢 Создание инцидента
    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        key = extract_key(text)
        if not key:
            print("❌ Не удалось извлечь ключ из инцидента.")
            return

        now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
        incident_id = f"{chat_id}_{key}"
        incidents[incident_id] = {
            "text": text,
            "chat_id": chat_id,
            "time": now,
            "jobs": [],
        }

        print(f"✅ Обнаружен инцидент: {incident_id}")

        for group_id in [-1002591060921, -1002631818202]:
            await context.bot.send_message(chat_id=group_id, text=text)

        if ("Средний" not in text) and ("Низкий" not in text):
            job_50 = scheduler.add_job(
                notify_50_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=30),
                args=[context.application, chat_id, incident_id],
                id=f"{incident_id}_50"
            )
            job_60 = scheduler.add_job(
                notify_60_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(minutes=1),
                args=[context.application, chat_id, incident_id],
                id=f"{incident_id}_60"
            )
            incidents[incident_id]["jobs"].extend([job_50.id, job_60.id])
        else:
            print("ℹ️ Уровень инцидента не высокий — напоминания не ставим.")
    else:
        print("Сообщение не содержит инцидент.")

def notify_50_minutes(application, chat_id, incident_id):
    global event_loop
    if incident_id not in incidents:
        print(f"⏱️ Инцидент {incident_id} уже закрыт до 50 минут.")
        return
    print(f"⏰ 50 минут истекли для {incident_id}")
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text="С момента создания прошло 50 минут, через 10 минут надо оповестить. @PR @"
        ),
        event_loop
    )

def notify_60_minutes(application, chat_id, incident_id):
    global event_loop
    if incident_id not in incidents:
        print(f"⏱️ Инцидент {incident_id} уже закрыт до 60 минут.")
        return
    print(f"⏰ 60 минут истекли для {incident_id}")
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
