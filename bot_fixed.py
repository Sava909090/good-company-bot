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
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
import uuid

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

# ID папки на Google Drive для загрузки фото
DRIVE_FOLDER_ID = '1liDwH_wYCuDQIgvZq54C5hyCHmR9yIlo'  # Замените на реальный ID папки

# Настройки для Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]
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

def init_google_services():
    """Инициализация Google Sheets и Drive"""
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # Инициализация Google Sheets
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
        
        # Инициализация Google Drive
        drive_service = build('drive', 'v3', credentials=creds)
        
        logger.info("✅ Google сервисы инициализированы успешно")
        return sheet, drive_service
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Google сервисов: {e}")
        return None, None

def upload_photo_to_drive(drive_service, photo_file, restaurant_name):
    """Загрузка фото на Google Drive"""
    try:
        # Создаем уникальное имя файла
        filename = f"{restaurant_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        
        file_metadata = {
            'name': filename,
            'parents': [DRIVE_FOLDER_ID]
        }
        
        media = MediaFileUpload(photo_file, mimetype='image/jpeg')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # Делаем файл публично доступным
        drive_service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        logger.info(f"✅ Фото успешно загружено: {file['webViewLink']}")
        return file['webViewLink']
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке фото на Drive: {e}")
        return None

def save_to_google_sheet(restaurant, feedback, photo_url=None):
    """Сохранение данных в Google Таблицу"""
    try:
        sheet, drive_service = init_google_services()
        if not sheet:
            return False
        
        # Подготовка данных для сохранения
        values = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Дата в столбец A
            restaurant,                                   # Ресторан в столбец B
            feedback,                                     # Отзыв в столбец C
            photo_url if photo_url else "Нет фото"        # Ссылка на фото в столбец D
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
        "Теперь напишите ваш отзыв или предложение.\n"
        "Вы также можете отправить фото (с подписью или без):",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return FEEDBACK

async def feedback_received(update: Update, context: CallbackContext) -> int:
    """Обработка полученного текстового отзыва"""
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
            "❌ Произошла ошибка при сохранении отзыв. "
            "Пожалуйста, попробуйте позже или свяжитесь с администратором.\n\n"
            "Чтобы попробовать еще раз, нажмите /start"
        )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END

async def handle_photo(update: Update, context: CallbackContext) -> int:
    """Обработка полученного фото"""
    restaurant = context.user_data.get('restaurant', 'Не указан')
    photo_url = None
    
    try:
        # Получаем фото (самое высокое качество)
        photo_file = await update.message.photo[-1].get_file()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            await photo_file.download_to_drive(temp_file.name)
            temp_file_path = temp_file.name
            
        # Инициализируем Google сервисы
        sheet, drive_service = init_google_services()
        if not drive_service:
            raise Exception("Не удалось инициализировать Google Drive")
        
        # Загружаем фото на Drive
        photo_url = upload_photo_to_drive(drive_service, temp_file_path, restaurant)
        
        # Удаляем временный файл
        os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке фото: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке фото. "
            "Текстовый отзыв будет сохранен без фото."
        )
    
    # Получаем текст отзыва (если есть подпись к фото)
    feedback = update.message.caption if update.message.caption else "Фото без подписи"
    
    # Сохраняем в Google Таблицу
    success = save_to_google_sheet(restaurant, feedback, photo_url)
    
    if success:
        if photo_url:
            message = f"✅ Спасибо за ваш отзыв с фото! Данные успешно сохранены.\n\nФото: {photo_url}"
        else:
            message = "✅ Спасибо за ваш отзыв! Он был успешно сохранен."
        
        await update.message.reply_text(
            message + "\n\nКоманда уже начала работу над ним!\n\n"
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
        "Вы можете отправлять текстовые отзывы или фото с подписями!\n"
        "Фото автоматически сохраняются в Google Drive."
    )

def check_google_services_connection():
    """Проверка подключения к Google сервисам"""
    logger.info("=" * 50)
    logger.info("Запуск бота с проверкой подключения...")
    logger.info("=" * 50)
    
    logger.info("Инициализация Google сервисов...")
    try:
        sheet, drive_service = init_google_services()
        if sheet and drive_service:
            # Получаем текущие данные для проверки
            data = sheet.get_all_values()
            logger.info(f"Текущие данные в таблице: {len(data)} строк")
            
            # Проверяем заголовки
            if len(data) > 0:
                headers = data[0]
                logger.info(f"Заголовки таблицы: {headers}")
            
            logger.info("✅ Google сервисы инициализированы успешно")
            return True
        else:
            logger.error("❌ Не удалось инициализировать Google сервисы")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке подключения: {e}")
        return False

def main():
    """Основная функция запуска бота"""
    # Проверяем подключение к Google сервисам
    if not check_google_services_connection():
        logger.error("Не удалось подключиться к Google сервисам. Проверьте настройки.")
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_received),
                MessageHandler(filters.PHOTO, handle_photo)  # Добавлен обработчик фото
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
