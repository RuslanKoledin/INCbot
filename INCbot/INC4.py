import datetime
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

# Планировщик с таймзоной
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

# Хранилище инцидентов: ключ - текст инцидента, значение - словарь с инфой
incidents = {}
event_loop = asyncio.get_event_loop()

# Уведомление через 50 минут
def notify_50_minutes(application, chat_id, incident_key):
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text=f"С момента создания инцидента '{incident_key}' прошло 50 минут. Через 10 минут надо оповестить. @PR @"
        ),
        event_loop
    )

# Уведомление через 60 минут
def notify_60_minutes(application, chat_id, incident_key):
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text=f"Оповестите! Инцидент: '{incident_key}' @PR @Ruslank1111!!"
        ),
        event_loop
    )

# Основная логика
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))

    # === 1. Новый инцидент ===
    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        match = re.search(r"Инцидент:\s*(.+)", text)
        if not match:
            print("❌ Не удалось извлечь ключ инцидента.")
            return
        incident_key = match.group(1).strip()

        # Сохраняем инцидент
        incidents[incident_key] = {
            "text": text,
            "chat_id": chat_id,
            "time": now,
            "priority": "current",
            "jobs": []
        }

        # Пересылаем во все группы
        for group_id in [-1002591060921, -1002631818202]:
            await context.bot.send_message(chat_id=group_id, text=text)

        # Проверка приоритета
        if "Средний" not in text and "Низкий" not in text:
            job_50 = scheduler.add_job(notify_50_minutes, 'date', run_date=now + datetime.timedelta(minutes=50),
                                       args=[context.application, chat_id, incident_key])
            job_60 = scheduler.add_job(notify_60_minutes, 'date', run_date=now + datetime.timedelta(minutes=60),
                                       args=[context.application, chat_id, incident_key])
            incidents[incident_key]["jobs"] = [job_50.id, job_60.id]

    # === 2. Повышение приоритета ===
    elif "Приоритет инцидента поднят" in text and update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text
        match = re.search(r"Инцидент:\s*(.+)", replied_text)
        if not match:
            print("❌ Не удалось извлечь ключ инцидента из ответа.")
            return

        incident_key = match.group(1).strip()
        incident = incidents.get(incident_key)
        if incident:
            if not incident["jobs"]:
                print(f"Повышен приоритет инцидента: {incident_key}, запускаем напоминания")
                job_50 = scheduler.add_job(notify_50_minutes, 'date',
                                           run_date=incident["time"] + datetime.timedelta(seconds=30),
                                           args=[context.application, chat_id, incident_key])
                job_60 = scheduler.add_job(notify_60_minutes, 'date',
                                           run_date=incident["time"] + datetime.timedelta(minutes=1),
                                           args=[context.application, chat_id, incident_key])
                incident["jobs"] = [job_50.id, job_60.id]
            else:
                print("Напоминания уже запущены для этого инцидента.")
        else:
            print(f"❌ Инцидент '{incident_key}' не найден в базе.")

    # === 3. Понижение приоритета ===
    elif "Приоритет инцидента понижен" in text and update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text
        match = re.search(r"Инцидент:\s*(.+)", replied_text)
        if not match:
            print("❌ Не удалось извлечь ключ инцидента из ответа (понижение).")
            return

        incident_key = match.group(1).strip()
        incident = incidents.get(incident_key)
        if incident and incident["jobs"]:
            print(f"Приоритет понижен. Отменяем задачи по инциденту: {incident_key}")
            for job_id in incident["jobs"]:
                scheduler.remove_job(job_id)
            incident["jobs"] = []

if __name__ == '__main__':
    application = ApplicationBuilder().token("7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ").build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Запускаем бота...")
    application.run_polling()
