import nest_asyncio
nest_asyncio.apply()

import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)


# 🔐 Токен бота
TOKEN = '8152393673:AAHAk_1pHe0RJFT3syRv32WIm5cMZYX--MM'
#7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ
# 🧠 Ключевые слова
KEYWORDS = ['временно', 'недоступно', 'временно недоступно', 'возобновлено', 'восстановлено']

# 🎯 Целевые группы и темы
TARGETS = [
    {"group_id": -1002195114285, "thread_id": 6512},
    # Добавь больше при необходимости
]

# 🔁 Обработка входящих сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.lower()

    if any(keyword in text for keyword in KEYWORDS):
        for target in TARGETS:
            group_id = target["group_id"]
            thread_id = target["thread_id"]

            try:
                # Если сообщение — ответ
                if msg.reply_to_message:
                    # 1. Переслать оригинал
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.reply_to_message.message_id,
                        message_thread_id=thread_id
                    )
                    # 2. Переслать ответ
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id,
                        message_thread_id=thread_id
                    )
                    print(f"✅ Переслан ответ + оригинал в {group_id}/{thread_id}")
                else:
                    # Только одно сообщение
                    await context.bot.forward_message(
                        chat_id=group_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id,
                        message_thread_id=thread_id
                    )
                    print(f"✅ Переслано обычное сообщение в {group_id}/{thread_id}")

            except Exception as e:
                print(f"❌ Ошибка пересылки в {group_id}: {e}")

# 🚀 Запуск бота
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🤖 Бот запущен. Мониторинг ключевых слов...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
