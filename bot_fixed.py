import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("8474316673:AAFmmmUzeSTWs1FW3CzM-zRK3F808Ej_scM")  # токен бота
SPREADSHEET_ID = os.getenv("1Trc6yLj6yKXmuPsoUrbgDgucinIMxAVbot6LgsLxHG8")  # ID Google-таблицы
DRIVE_FOLDER_ID = os.getenv("1liDwH_wYCuDQIgvZq54C5hyCHmR9yIlo")  # ID папки на Google Drive

# сервисный аккаунт
creds = Credentials.from_service_account_file("credentials.json", scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

drive_service = build("drive", "v3", credentials=creds)

# -------------------- TELEGRAM --------------------
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# список ресторанов
RESTAURANTS = [
    "Ресторан 1",
    "Ресторан 2",
    "Ресторан 3",
    "Ресторан 4",
    "Ресторан 5",
    "Ресторан 6",
]

# словарь для хранения выбранного ресторана
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
    await message.answer(f"Вы выбрали {message.text}. Напишите отзыв и при необходимости прикрепите фото.")


# --- обработка отзывов ---
@dp.message_handler(content_types=['text', 'photo'])
async def handle_review(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_restaurant:
        await message.answer("Сначала выберите ресторан через /start")
        return

    restaurant = user_restaurant[user_id]
    text_review = message.text if message.text else ""

    # дата
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # если есть фото
    photo_url = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path

        # скачать фото
        photo_name = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        downloaded = await bot.download_file(file_path)
        with open(photo_name, "wb") as f:
            f.write(downloaded.read())

        # загрузить в Google Drive
        file_metadata = {"name": photo_name, "parents": [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(photo_name, mimetype="image/jpeg")
        uploaded = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()

        file_id_drive = uploaded.get("id")
        photo_url = f"https://drive.google.com/file/d/{file_id_drive}/view?usp=sharing"

        os.remove(photo_name)  # удаляем локальный файл

    # пишем в таблицу
    worksheet.append_row([date_str, restaurant, text_review, photo_url])

    # ответ пользователю
    await message.answer(
        "Спасибо за ваш акцент! Команда уже начала работу над улучшением!\n"
        "Чтобы оставить ещё один отзыв, нажмите /start"
    )


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
