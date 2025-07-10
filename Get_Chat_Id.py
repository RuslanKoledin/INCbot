import os
import nest_asyncio
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

nest_asyncio.apply()  # 🔄 Позволяет работать с уже запущенным event loop

# 💬 Печатает chat_id
async def print_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📌 Chat ID: {update.effective_chat.id}")

# 🚀 Основная функция
async def main():
    load_dotenv()
    token = os.getenv("token")
    if not token:
        raise ValueError("❌ Токен не найден в .env!")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, print_chat_id))

    print("🤖 Бот запущен. Напиши сообщение в группу или чат...")
    await app.run_polling()

# 🔁 Запуск с поддержкой nest_asyncio
if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
