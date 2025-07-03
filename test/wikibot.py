import wikipedia
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

wikipedia.set_lang("ru")  # Устанавливаем язык

# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    try:
        summary = wikipedia.summary(query, sentences=2)
        await update.message.reply_text(summary)
    except wikipedia.exceptions.DisambiguationError as e:
        await update.message.reply_text(f"Слишком много значений: {e.options[:5]}...")
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Ничего не найдено по вашему запросу.")
    except Exception as e:
        await update.message.reply_text("Произошла ошибка.")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши любой вопрос, и я найду ответ в Википедии.")

if __name__ == "__main__":
    TOKEN = "7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ"

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()
