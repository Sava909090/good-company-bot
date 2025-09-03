import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

import gspread

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# -------------------- GOOGLE SHEETS --------------------
gc = gspread.service_account(filename="service_account.json")  # либо через переменную окружения
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

# -------------------- TELEGRAM --------------------
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# список ресторанов
RESTAURANTS = ["Ресторан 1", "Ресторан 2", "Ресторан 3", "Ресторан 4", "Ресторан 5", "Ресторан 6"]

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
    # исправленная обработка текста при фото+текст
    text_review = message.text or message.caption or ""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photo_formula = ""
    photo_link = ""

    if message.photo:
        try:
            file_id = message.photo[-1].file_id
            # формула для вставки в таблицу (просмотр фото)
            photo_formula = f'=IMAGE("https://api.telegram.org/file/bot{BOT_TOKEN}/{(await bot.get_file(file_id)).file_path}")'
            # ссылка на скачивание
            photo_link = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{(await bot.get_file(file_id)).file_path}'
        except Exception as e:
            logging.error(f"Ошибка при обработке фото: {e}")
            await message.answer("Не удалось загрузить фото, попробуйте снова.")

    # запись в таблицу
    worksheet.append_row([date_str, restaurant, text_review, photo_formula, photo_link])

    await message.answer(
        "Спасибо за ваш отзыв! Команда уже начала работу над улучшением!\n"
        "Чтобы оставить ещё один отзыв, нажмите /start"
    )

# -------------------- MAIN --------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
