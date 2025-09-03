import logging
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

import gspread
from google.oauth2.service_account import Credentials

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# -------------------- GOOGLE SHEETS --------------------
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if not credentials_json:
    raise ValueError("Переменная окружения GOOGLE_CREDENTIALS не найдена")

info = json.loads(credentials_json)
creds = Credentials.from_service_account_info(info, scopes=[
    "https://www.googleapis.com/auth/spreadsheets"
])

gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

# -------------------- TELEGRAM --------------------
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# список ресторанов
RESTAURANTS = ["Ресторан 1", "Ресторан 2", "Ресторан 3", "Ресторан 4", "Ресторан 5", "Ресторан 6"]

# выбранный ресторан по пользователю
user_restaurant = {}

# --- меню старта ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in RESTAURANTS:
        kb.add(KeyboardButton(r))
    await message.answer("Выберите ресторан:", reply_markup=kb)

# --- выбор ресторана ---
@dp.message_handler(lambda msg: msg.text in RESTAURANTS)
async def choose_restaurant(message: types.Message):
    user_restaurant[message.from_user.id] = message.text
    await message.answer(f"Вы выбрали {message.text}. Напишите отзыв и/или прикрепите фото.")

# --- обработка отзывов ---
@dp.message_handler(content_types=['text', 'photo'])
async def handle_review(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_restaurant:
        await message.answer("Сначала выберите ресторан через /start")
        return

    restaurant = user_restaurant[user_id]
    text_review = message.caption if message.caption else (message.text if message.text else "")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image_formula = ""
    download_link = ""

    # --- обработка фото ---
    if message.photo:
        try:
            # Берём file_id самой большой (последней) фотографии
            file_id = message.photo[-1].file_id
            file_info = await bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

            # В столбце D будет картинка через =IMAGE()
            image_formula = f'=IMAGE("{file_url}")'

            # В столбце E будет ссылка для скачивания
            download_link = f'=HYPERLINK("{file_url}";"Скачать")'

        except Exception as e:
            logging.error(f"Ошибка при обработке фото: {e}")
            await message.answer("Не удалось обработать фото, попробуйте снова.")

    # --- запись в таблицу ---
    worksheet.append_row([date_str, restaurant, text_review, image_formula, download_link], value_input_option="USER_ENTERED")

    # --- ответ пользователю ---
    await message.answer(
        "Спасибо за ваш отзыв! Команда уже начала работу над улучшением!\n"
        "Чтобы оставить ещё один отзыв, нажмите /start"
    )

# -------------------- MAIN --------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
