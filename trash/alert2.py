import os
import nest_asyncio
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

nest_asyncio.apply()
load_dotenv()
token = os.getenv("token")
if not token:
    raise ValueError("❌ Ошибка! Токен не найден в .env файле.")

# 🎯 Целевые группы, куда бот будет отправлять сообщения
TARGET_GROUP_IDS = [-1002631818202]

# 🗂 Словарь для хранения последних "временно недоступно" сообщений
LAST_TOPUP = {}  # chat_id -> (text, timestamp)


# 🔁 Обработка входящих сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    lowered = text.lower()
    chat_id = msg.chat_id
    now = datetime.datetime.now()

    # 🔴 1. Обработка "временно недоступно"
    if "пополнение mbank через" in lowered and "временно недоступно" in lowered:
        LAST_TOPUP[chat_id] = (text, now)

        for group_id in TARGET_GROUP_IDS:
            try:
                await context.bot.send_message(chat_id=group_id, text=text)
                print(f"✅ Сбой переслан в {group_id}: {text}")
            except Exception as e:
                print(f"❌ Ошибка пересылки в {group_id}: {e}")
        return

    # 🟢 2. Обработка "восстановлено" или "возобновлено"
    if "восстановлено" in lowered or "возобновлено" in lowered:
        if chat_id in LAST_TOPUP:
            prev_text, prev_time = LAST_TOPUP.pop(chat_id)

            # Убираем "временно недоступно" и составляем новое сообщение
            prefix = prev_text.split("временно недоступно")[0].strip()
            restored = f"{prefix} восстановлено"

            for group_id in TARGET_GROUP_IDS:
                try:
                    await context.bot.send_message(chat_id=group_id, text=restored)
                    print(f"✅ Восстановление отправлено в {group_id}: {restored}")
                except Exception as e:
                    print(f"❌ Ошибка отправки восстановления в {group_id}: {e}")
            return

    # 🟡 3. Пересылка любых сообщений с ключевыми словами (если нужно)
    KEYWORDS = ['временно', 'недоступно']
    if any(k in lowered for k in KEYWORDS):
        for group_id in TARGET_GROUP_IDS:
            try:
                await context.bot.forward_message(
                    chat_id=group_id,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id
                )
                print(f"📤 Переслано сообщение с ключевым словом в {group_id}")
            except Exception as e:
                print(f"❌ Ошибка пересылки: {e}")


# 📌 Отладка: вывод ID чата
async def print_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    print(f"📌 Chat ID: {chat.id}")


# 🚀 Запуск бота
async def main():
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.ALL, print_chat_id))  # для отладки, можно удалить
    print("🤖 Бот запущен. Мониторинг сообщений...")
    await app.run_polling()


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
