import datetime
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import os

# Отключаем прокси, если нужно
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Bishkek"))
scheduler.start()

incidents = {}
event_loop = None

# Список групп для рассылки инцидентов и сообщений о решении
BROADCAST_GROUPS = [-1002591060921, -1002631818202]

def extract_key(text: str) -> str:
    match = re.search(r'Инцидент:\s*(.+?)(\n|$)', text)
    return match.group(1).strip() if match else None

def get_incident_key(text: str, chat_id: int) -> str | None:
    for key, value in incidents.items():
        if value["chat_id"] == chat_id and value["text"] in text:
            return key
    return None

def is_priority_low(text: str) -> bool:
    """Проверка, средний или низкий приоритет в тексте"""
    return ("Средний" in text) or ("Низкий" in text)

async def send_notify_50(application, chat_id):
    await application.bot.send_message(
        chat_id=chat_id,
        text="С момента создания прошло 50 минут, через 10 минут надо оповестить. @PR @"
    )

async def send_notify_60(application, chat_id):
    await application.bot.send_message(
        chat_id=chat_id,
        text="Оповестите! @PR @Ruslank1111!!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    reply_to = update.message.reply_to_message

    print(f"Получено сообщение: {text} в чате {chat_id}")

    # --- Закрытие инцидента ---
    if reply_to and any(word in text.lower() for word in ["заработал", "устранено", "решено"]):
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
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass

            now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
            duration = now - incident["time"]
            duration_str = str(duration).split('.')[0]

            resolution_message = (
                f"ℹ️ Инцидент '{key}' решён.\n"
                f"Время решения: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Время на решение: {duration_str}"
            )
            # Отправляем в исходный чат
            await context.bot.send_message(chat_id=chat_id, text=resolution_message)

            # И пересылаем в группы рассылки
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

        if not is_priority_low(text):
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
                run_date=now + datetime.timedelta(seconds=60),
                args=[context.application, chat_id, incident_id],
                id=f"{incident_id}_60"
            )
            incidents[incident_id]["jobs"].extend([job_50.id, job_60.id])
        else:
            print("ℹ️ Уровень инцидента не высокий — напоминания не ставим.")

    # --- Изменение приоритета ---
    elif "Приоритет инцидента поднят до" in text or "Приоритет инцидента понижен до" in text:
        if reply_to:
            replied_text = reply_to.text
            incident_id = get_incident_key(replied_text, chat_id)
            if not incident_id or incident_id not in incidents:
                print("❌ Не удалось найти связанный инцидент.")
                return

            incident = incidents[incident_id]
            group_name = GROUP_NAMES.get(chat_id, str(chat_id))

            # Повышение приоритета
            if "поднят до" in text and ("Высокий" in text or "Наивысший" in text):
                print(f"🔼 Приоритет инцидента {incident_id} повышен.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Приоритет инцидента {incident_id} ({group_name}) повышен."
                )
                # Если напоминаний еще нет, добавляем
                if not incident["jobs"]:
                    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
                    job_50 = scheduler.add_job(
                        notify_50_minutes,
                        trigger='date',
                        run_date=now + datetime.timedelta(seconds=10),
                        args=[context.application, chat_id, incident_id],
                        id=f"{incident_id}_50"
                    )
                    job_60 = scheduler.add_job(
                        notify_60_minutes,
                        trigger='date',
                        run_date=now + datetime.timedelta(seconds=25),
                        args=[context.application, chat_id, incident_id],
                        id=f"{incident_id}_60"
                    )
                    incident["jobs"].extend([job_50.id, job_60.id])
                    print("✅ Напоминания установлены после повышения приоритета.")
                else:
                    # Проверяем, сколько прошло времени с создания инцидента
                    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bishkek"))
                    elapsed = now - incident["time"]

                    # Если прошло больше 50 минут — сразу отправляем уведомление
                    if elapsed >= datetime.timedelta(minutes=50):
                        print(f"⚠️ Инцидент {incident_id} - прошло уже более 50 минут. Немедленно отправляем уведомление.")
                        await send_notify_50(context.application, chat_id)

                    # Если прошло больше 60 минут — сразу отправляем уведомление
                    if elapsed >= datetime.timedelta(minutes=60):
                        print(f"⚠️ Инцидент {incident_id} - прошло уже более 60 минут. Немедленно отправляем уведомление.")
                        await send_notify_60(context.application, chat_id)

            # Понижение приоритета — удаляем напоминания
            elif "понижен до" in text and ("Средний" in text or "Низкий" in text):
                print(f"🔽 Приоритет инцидента {incident_id} понижен. Удаляем напоминания.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Приоритет инцидента {incident_id} ({group_name}) понижен."
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
            text="С момента создания прошло 50 минут, через 10 минут надо оповестить. @PR @"
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
    application = ApplicationBuilder().token("7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ").build()
    event_loop = asyncio.get_event_loop()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Запускаем бота...")
    asyncio.run(application.run_polling())
