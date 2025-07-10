import datetime
import asyncio
import re
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

load_dotenv()

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

incidents = {}
event_loop = asyncio.get_event_loop()

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()
#Примеры групп
GROUP_NAMES = {
    -1002783899407: " ",#"MWiki Операционный департамент",
    -1002591060921: " ",#"INC_UAT",
    -1002631818202: " ",#"УКОИМиВИТ",
    -4954181055: "",#"IVR/Мониторинг"
}
BROADCAST_GROUPS = [-1002591060921, -1002631818202,-4954181055]

# GROUP_NAMES = {
#     -: "КЦ_МГ",
#     -: "ADM",
#     -: "УКОИМиВИТ",
#     -: "IVR/Мониторинг"
# }
# BROADCAST_GROUPS = [-1002591060921, -1002631818202]

def extract_key(text: str) -> str:
    match = re.search(r'Инцидент:\s*(.+?)(\n|$)', text)
    return match.group(1).strip() if match else None

def extract_jira_key(text: str) -> str | None:
    match = re.search(r'(ITSMJIRA-\d+)', text)
    return match.group(1) if match else None

def get_incident_key(text: str, chat_id: int) -> str | None:
    for key, value in incidents.items():
        if value["chat_id"] == chat_id and value["text"] in text:
            return key
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    reply_to = update.message.reply_to_message

    # --- ФИЛЬТР, чтобы обрабатывать только сообщения, связанные с инцидентами ---
    resolution_words = ["заработал", "устранено", "решено", "локализован", "восстановлен"]
    priority_words = ["Приоритет инцидента поднят до", "понижен до", "повышен до"]
    jira_pattern = re.compile(r'ITSMJIRA-\d+')

    if not (
        ("Инцидент:" in text and "Время выявления инцидента:" in text)
        or (reply_to and any(word in text.lower() for word in resolution_words))
        or jira_pattern.search(text)
        or any(word in text for word in priority_words)
    ):
        # Игнорируем не относящиеся к инциденту сообщения
        return

    print(f"Получено сообщение: {text} в чате {chat_id}")

    if reply_to and any(word in text.lower() for word in resolution_words):
        replied_text = reply_to.text
        jira_key = extract_jira_key(replied_text) or extract_key(replied_text)
        key = extract_key(replied_text) or jira_key
        if not key:
            print("Не удалось извлечь ключ инцидента.")
            return

        incident_id = f"{chat_id}_{key}"
        incident = incidents.get(incident_id)
        if incident:
            print(f"Инцидент '{key}' закрыт. Отменяю напоминания.")
            for job_id in incident.get("jobs", []):
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass

            now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
            duration = now - incident["time"]
            jira_link = f"\nJIRA: https://jiraportal.cbk.kg/projects/ITSMJIRA/queues/issue/{jira_key}" if jira_key else ""

            msg = (
                f"Инцидент '{key}' решён.{jira_link}\n"
                f"Время решения: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Время на решение: {str(duration).split('.')[0]}"
            )

            await context.bot.send_message(chat_id=chat_id, text=msg)
            for group_id in BROADCAST_GROUPS:
                await context.bot.send_message(chat_id=group_id, text=msg)
            del incidents[incident_id]
        return

    if "Инцидент:" in text and "Время выявления инцидента:" in text:
        key = extract_key(text)
        if not key:
            print("Не удалось извлечь ключ из инцидента.")
            return

        now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
        incident_id = f"{chat_id}_{key}"
        incidents[incident_id] = {"text": text, "chat_id": chat_id, "time": now, "jobs": []}
        print(f"Обнаружен инцидент: {incident_id}")

        for group_id in BROADCAST_GROUPS:
            await context.bot.send_message(chat_id=group_id, text=text)

        if ("Средний" not in text) and ("Низкий" not in text):
            job_50 = scheduler.add_job(notify_50_minutes, 'date', run_date=now + datetime.timedelta(seconds=20),
                                       args=[context.application, chat_id, incident_id, event_loop], id=f"{incident_id}_50")
            job_60 = scheduler.add_job(notify_60_minutes, 'date', run_date=now + datetime.timedelta(seconds=40),
                                       args=[context.application, chat_id, incident_id, event_loop], id=f"{incident_id}_60")
            incidents[incident_id]["jobs"].extend([job_50.id, job_60.id])
        else:
            print("Уровень инцидента не высокий — напоминания не ставим.")
        return

    if any(word in text for word in priority_words):
        if not reply_to:
            print("Сообщение не является ответом на инцидент.")
            return

        incident_id = get_incident_key(reply_to.text, chat_id)
        if not incident_id or incident_id not in incidents:
            print("Не удалось найти связанный инцидент.")
            return

        incident = incidents[incident_id]
        group_name = GROUP_NAMES.get(chat_id, str(chat_id))
        key = incident_id.split('_', 1)[1]

        if ("поднят до" in text or "повышен до" in text) and ("Высокий" in text or "Наивысший" in text):
            print(f"Приоритет инцидента {group_name} повышен.")
            await context.bot.send_message(chat_id=chat_id, text=f"Приоритет инцидента '{key}' ({group_name}) повышен.")
            for job_id in incident["jobs"]:
                try: scheduler.remove_job(job_id)
                except: pass
            incident["jobs"] = []

            now = incident["time"]
            elapsed = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) - now
            remain_50 = max(datetime.timedelta(minutes=50) - elapsed, datetime.timedelta())
            remain_60 = max(datetime.timedelta(minutes=60) - elapsed, datetime.timedelta())

            job_50 = scheduler.add_job(notify_50_minutes, 'date',
                                       run_date=datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) + remain_50,
                                       args=[context.application, chat_id, incident_id, event_loop],
                                       id=f"{incident_id}_50")
            job_60 = scheduler.add_job(notify_60_minutes, 'date',
                                       run_date=datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) + remain_60,
                                       args=[context.application, chat_id, incident_id, event_loop],
                                       id=f"{incident_id}_60")
            incident["jobs"].extend([job_50.id, job_60.id])
            print("Напоминания установлены после повышения приоритета.")
        elif "понижен до" in text and ("Средний" in text or "Низкий" in text):
            print(f"Приоритет понижен. Удаляем напоминания.")
            await context.bot.send_message(chat_id=chat_id, text=f"Приоритет инцидента '{key}' ({group_name}) понижен.")
            for job_id in incident["jobs"]:
                try: scheduler.remove_job(job_id)
                except: pass
            incident["jobs"] = []

def notify_50_minutes(app, chat_id, incident_id, loop):
    if incident_id not in incidents:
        print(f"Инцидент {incident_id} уже закрыт (50 мин).")
        return
    print(f"50 минут истекли для {incident_id}")
    asyncio.run_coroutine_threadsafe(
        app.bot.send_message(chat_id=chat_id, text="С момента создания прошло 50 минут, через 10 минут оповестить. @PR @"),
        loop
    )

def notify_60_minutes(app, chat_id, incident_id, loop):
    if incident_id not in incidents:
        print(f"Инцидент {incident_id} уже закрыт (60 мин).")
        return
    print(f"60 минут истекли для {incident_id}")
    asyncio.run_coroutine_threadsafe(
        app.bot.send_message(chat_id=chat_id, text="Оповестите! @PR @Ruslank1111!!"),
        loop
    )
    job_3h = scheduler.add_job(notify_3_hours_later, 'date',
                               run_date=datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) + datetime.timedelta(hours=3),
                               args=[app, chat_id, incident_id, loop],
                               id=f"{incident_id}_3h")
    incidents[incident_id]["jobs"].append(job_3h.id)

def notify_3_hours_later(app, chat_id, incident_id, loop):
    if incident_id not in incidents:
        print(f"Инцидент {incident_id} закрыт до 3 часов.")
        return
    print(f"3 часа истекли для {incident_id}")
    asyncio.run_coroutine_threadsafe(
        app.bot.send_message(chat_id=chat_id, text="С момента оповещения прошло 3 часа! Проверьте статус и вновь оповестите."
                                                   " @PR @Ruslank1111"),
        loop
    )

if __name__ == '__main__':
    load_dotenv()
    token = os.getenv("tg")
    if not token:
        raise ValueError("Ошибка! Токен не найден в .env файле.")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Запускаем бота...")
    application.run_polling()
