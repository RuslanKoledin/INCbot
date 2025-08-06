import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Шутки и ответы
jokes = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT == 25 DEC.",
    "Python-программист перед сном: import sleep",
    "Гугл знает всё, а StackOverflow — как это сделать."
]

answers = [
    "Да, скорее всего!",
    "Нет, вряд ли.",
    "Может быть, но это не точно.",
    "Спроси ещё раз позже.",
    "Я думаю, да."
]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if "шутка" in text:
        await update.message.reply_text(random.choice(jokes))

    elif "ответ есть" in text:
        await update.message.reply_text(random.choice(answers))

    else:
        await update.message.reply_text("Напиши 'шутка' для шутки или 'ответ есть' — я подскажу :)")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши 'шутка' или 'ответ есть' — и я отвечу :)")

if __name__ == "__main__":
    TOKEN = "7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ"

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()
