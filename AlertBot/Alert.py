import os
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()

import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# 🧠 Ключевые слова
KEYWORDS = ['временно', 'недоступно', 'временно недоступно', 'возобновлено', 'восстановлено']

# 🎯 Целевые группы
DBO_CC = []
TARGET_GROUP_IDS = [-1002631818202]
INC_UAT = [-1002631818202]
#INC_UAC = [-1002631818202]


# 🔁 Обработка входящих сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.lower()

    if any(keyword in text for keyword in KEYWORDS):
        for group_id in TARGET_GROUP_IDS:
            try:
                # Если сообщение — ответ
                if msg.reply_to_message:
                    # Переслать оригинал
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.reply_to_message.message_id
                    )
                    # Переслать ответ
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id
                    )
                    print(f"✅ Переслан ответ + оригинал в {group_id} ")
                else:
                    # Только одно сообщение
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id
                    )
                    print(f"✅ Переслано обычное сообщение в {group_id}")

            except Exception as e:
                print(f"❌ Ошибка пересылки в {group_id}: {e}")


# 👆 вверху файла (рядом с другими функциями)
async def print_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    print(f"📌 Chat ID: {chat.id}")


# 🚀 Запуск бота
async def main():
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🤖 Бот запущен. Мониторинг ключевых слов...")
    await app.run_polling()

    # 👇 в main(), перед app.run_polling()
    app.add_handler(MessageHandler(filters.ALL, print_chat_id))


if __name__ == '__main__':
    load_dotenv()
    token = os.getenv("token")
    if not token:
        raise ValueError("Ошибка! Токен не найден в .env файле.")
    asyncio.get_event_loop().run_until_complete(main())
