import os
import logging
import gspread
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackContext
)
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = '8474316673:AAFmmmUzeSTWs1FW3CzM-zRK3F808Ej_scM'

# ID Google Таблицы
SPREADSHEET_ID = '1Trc6yLj6yKXmuPsoUrbgDgucinIMxAVbot6LgsLxHG8'

# Настройки для Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json'

# Состояния разговора
RESTAURANT, FEEDBACK = range(2)

# Список ресторанов (6 штук)
RESTAURANTS = [
    "Barbaresco",
    "Brut is good", 
    "Good Company",
    "United",
    "Буфет на Большой",
    "Ресторан 6"
]

def init_google_sheets():
    """Инициализация Google Sheets"""
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
        logger.info("✅ Google Sheets инициализирован успешно")
        return sheet
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Google Sheets: {e}")
        return None

def save_to_google_sheet(restaurant, feedback):
    """Сохранение данных в Google Таблицу"""
    try:
        sheet = init_google_sheets()
        if not sheet:
            return False
        
        # Подготовка данных для сохранения
        values = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Дата в столбец A
            restaurant,                                   # Ресторан в столбец B
            feedback                                      # Отзыв в столбец C
        ]
        
        # Добавляем новую строку
        sheet.append_row(values)
        logger.info(f"✅ Данные успешно сохранены: {values}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении в Google Таблицу: {e}")
        return False

async def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога, выбор ресторана"""
    keyboard = [
        [RESTAURANTS[0], RESTAURANTS[1], RESTAURANTS[2]],
        [RESTAURANTS[3], RESTAURANTS[4], RESTAURANTS[5]]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        "🍽️ Добро пожаловать в систему отзывов!\n\n"
        "Пожалуйста, выберите ресторан из списка:",
        reply_markup=reply_markup
    )
    
    return RESTAURANT

async def restaurant_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора ресторана"""
    restaurant = update.message.text
    
    # Проверяем, что выбранный ресторан есть в списке
    if restaurant not in RESTAURANTS:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите ресторан из предложенного списка.\n\n"
            "Нажмите /start чтобы выбрать снова."
        )
        return ConversationHandler.END
    
    context.user_data['restaurant'] = restaurant
    
    await update.message.reply_text(
        f"🏪 Вы выбрали: {restaurant}\n\n"
        "Теперь напишите ваш отзыв или предложение:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return FEEDBACK

async def feedback_received(update: Update, context: CallbackContext) -> int:
    """Обработка полученного отзыва"""
    feedback = update.message.text
    restaurant = context.user_data.get('restaurant', 'Не указан')
    
    # Сохраняем в Google Таблицу
    success = save_to_google_sheet(restaurant, feedback)
    
    if success:
        await update.message.reply_text(
            "✅ Спасибо за ваш отзыв! Он был успешно сохранен.\n\n"
            "Команда уже начала работу над ним!\n\n"
            "Чтобы оставить еще один отзыв, нажмите /start"
        )
    else:
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении отзыва. "
            "Пожалуйста, попробуйте позже или свяжитесь с администратором.\n\n"
            "Чтобы попробовать еще раз, нажмите /start"
        )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена диалога"""
    await update.message.reply_text(
        'Диалог отменен. Чтобы начать заново, нажмите /start',
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def help_command(update: Update, context: CallbackContext) -> None:
    """Команда помощи"""
    await update.message.reply_text(
        "🤖 Бот для сбора отзывов о ресторанах\n\n"
        "Команды:\n"
        "/start - начать процесс оставления отзыва\n"
        "/help - показать эту справку\n\n"
        "Просто нажмите /start и следуйте инструкциям!"
    )

def check_google_sheets_connection():
    """Проверка подключения к Google Sheets"""
    logger.info("=" * 50)
    logger.info("Запуск бота с проверкой подключения...")
    logger.info("=" * 50)
    
    logger.info("Инициализация Google Sheets...")
    try:
        sheet = init_google_sheets()
        if sheet:
            # Получаем текущие данные для проверки
            data = sheet.get_all_values()
            logger.info(f"Текущие данные в таблице: {len(data)} строк")
            logger.info(f"Первые строки таблицы: {data[:3]}")
            
            # Проверяем заголовки
            if len(data) > 0:
                headers = data[0]
                logger.info(f"Заголовки таблицы: {headers}")
            
            logger.info("✅ Google Sheets инициализирован успешно")
            return True
        else:
            logger.error("❌ Не удалось инициализировать Google Sheets")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке подключения: {e}")
        return False

def main():
    """Основная функция запуска бота"""
    # Проверяем подключение к Google Sheets
    if not check_google_sheets_connection():
        logger.error("Не удалось подключиться к Google Sheets. Проверьте настройки.")
        return
    
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            RESTAURANT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, restaurant_choice)
            ],
            FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_received)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Запускаем webhook
    port = int(os.environ.get('PORT', 8443))
    
    # ПРАВИЛЬНЫЙ ВАРИАНТ ДЛЯ HEROKU
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"https://good-company-bot.herokuapp.com/",
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
if __name__ == '__main__':
    main()
