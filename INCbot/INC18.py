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

# Отключаем прокси, если нужно
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

incidents = {}
event_loop = None

# Сопоставление chat_id к названию группы
GROUP_NAMES = {
    -1002783899407: "MBank",
    -1002591060921: "ADM",
    -1002631818202: "ДБО&КЦ",
}

# Список групп для рассылки инцидентов и сообщений о решении
BROADCAST_GROUPS = [-1002591060921, -1002631818202]


def extract_key(text: str) -> str:
    match = re.search(r'Инцидент:\s*(.+?)(\n|$)', text)
    return match.group(1).strip() if match else None


def extract_jira_key(text: str) -> str | None:
    # Ищем ключ JIRA в формате ITSMJIRA-число
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

    print(f"Получено сообщение: {text} в чате {chat_id}")

    # --- Закрытие инцидента ---
    if reply_to and any(
            word in text.lower() for word in ["заработал", "устранено", "решено", "локализован", "восстановлен"]):
        replied_text = reply_to.text

        jira_key = extract_jira_key(replied_text)
        if not jira_key:
            print("❌ Не найден ключ JIRA в сообщении, пытаемся извлечь ключ инцидента.")
            jira_key = extract_key(replied_text)  # fallback

        key = extract_key(replied_text) or jira_key
        if not key:
            print("❌ Не удалось извлечь ключ инцидента.")
            return

        incident_id = f"{chat_id}_{key}"
        incident = incidents.get(incident_id)
        if incident:
            print(f"🔕 Инцидент '{key}' закрыт. Отменяю напоминания.")
            for job_id in incident.get("jobs", []):
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass

            now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
            duration = now - incident["time"]
            duration_str = str(duration).split('.')[0]

            jira_link = ""
            if jira_key:
                jira_link = f"\nJIRA: https://jiraportal.cbk.kg/projects/ITSMJIRA/queues/issue/{jira_key}"

            resolution_message = (
                f"ℹ️ Инцидент '{key}' решён.{jira_link}\n"
                f"Время решения: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Время на решение: {duration_str}"
            )

            await context.bot.send_message(chat_id=chat_id, text=resolution_message)
            for group_id in BROADCAST_GROUPS:
                await context.bot.send_message(chat_id=group_id, text=resolution_message)

            del incidents[incident_id]
        else:
            print(f"⚠️ Инцидент '{key}' не найден.")
        return

    # --- Создание нового инцидента ---
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

        for group_id in BROADCAST_GROUPS:
            await context.bot.send_message(chat_id=group_id, text=text)

        if ("Средний" not in text) and ("Низкий" not in text):
            job_50 = scheduler.add_job(
                notify_50_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=20),
                args=[context.application, chat_id, incident_id],
                id=f"{incident_id}_50"
            )
            job_60 = scheduler.add_job(
                notify_60_minutes,
                trigger='date',
                run_date=now + datetime.timedelta(seconds=40),
                args=[context.application, chat_id, incident_id],
                id=f"{incident_id}_60"
            )
            incidents[incident_id]["jobs"].extend([job_50.id, job_60.id])
        else:
            print("ℹ️ Уровень инцидента не высокий — напоминания не ставим.")

    # --- Изменение приоритета ---
    elif ("Приоритет инцидента поднят до" in text or
          "Приоритет инцидента понижен до" in text or
          "Приоритет инцидента повышен до" in text):
        if reply_to:
            replied_text = reply_to.text
            incident_id = get_incident_key(replied_text, chat_id)
            if not incident_id or incident_id not in incidents:
                print("❌ Не удалось найти связанный инцидент.")
                return

            incident = incidents[incident_id]
            group_name = GROUP_NAMES.get(chat_id, str(chat_id))

            # Получаем ключ инцидента из incident_id
            key = incident_id.split('_', 1)[1]

            # Повышение приоритета
            if ("поднят до" in text or "повышен до" in text) and ("Высокий" in text or "Наивысший" in text):
                print(f"🔼 Приоритет инцидента {group_name} повышен.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Приоритет инцидента '{key}' ({group_name}) повышен."
                )

                for job_id in incident["jobs"]:
                    try:
                        scheduler.remove_job(job_id)
                    except Exception:
                        pass
                incident["jobs"] = []

                # Не обновляем время, чтобы сохранить оригинальную точку отсчета
                now = incident["time"]
                elapsed = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) - now
                remain_50 = max(datetime.timedelta(seconds=20) - elapsed, datetime.timedelta())
                remain_60 = max(datetime.timedelta(seconds=40) - elapsed, datetime.timedelta())

                job_50 = scheduler.add_job(
                    notify_50_minutes,
                    trigger='date',
                    run_date=datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) + remain_50,
                    args=[context.application, chat_id, incident_id],
                    id=f"{incident_id}_50"
                )
                job_60 = scheduler.add_job(
                    notify_60_minutes,
                    trigger='date',
                    run_date=datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek")) + remain_60,
                    args=[context.application, chat_id, incident_id],
                    id=f"{incident_id}_60"
                )
                incident["jobs"].extend([job_50.id, job_60.id])
                print("✅ Напоминания установлены после повышения приоритета.")

            # Понижение приоритета
            elif "понижен до" in text and ("Средний" in text or "Низкий" in text):
                print(f"🔽 Приоритет инцидента {incident_id} понижен. Удаляем напоминания.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Приоритет инцидента '{key}' ({group_name}) понижен."
                )
                for job_id in incident["jobs"]:
                    try:
                        scheduler.remove_job(job_id)
                    except Exception:
                        pass
                incident["jobs"] = []
        else:
            print("❌ Сообщение не является ответом на инцидент.")
    else:
        print("Сообщение не содержит инцидент.")


def notify_50_minutes(application, chat_id, incident_id):
    global event_loop
    if incident_id not in incidents:
        print(f"⏱️ Инцидент {incident_id} уже закрыт (50 мин).")
        return
    print(f"⏰ 50 минут истекли для {incident_id}")
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=chat_id,
            text="С момента создания инцидента прошло 50 минут, через 10 минут необходимо оповестить. @PR @"
        ),
        event_loop
    )


def notify_60_minutes(application, chat_id, incident_id):
    global event_loop
    if incident_id not in incidents:
        print(f"⏱️ Инцидент {incident_id} уже закрыт (60 мин).")
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
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN в .env файле!")

    application = ApplicationBuilder().token(token).build()
    event_loop = asyncio.get_event_loop()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Запускаем бота...")
    application.run_polling()
