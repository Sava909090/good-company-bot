import logging
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
APP_NAME = os.getenv("HEROKU_APP_NAME")  # имя приложения Heroku

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")
if not APP_NAME:
    raise ValueError("HEROKU_APP_NAME не найден в переменных окружения")

# читаем GOOGLE_CREDENTIALS из переменных окружения
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if not credentials_json:
    raise ValueError("Переменная окружения GOOGLE_CREDENTIALS не найдена")

info = json.loads(credentials_json)
creds = Credentials.from_service_account_info(info, scopes=[
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
    "Барбареско",
    "Good Company",
    "Brut is good",
    "United",
    "Буфет на Большой",
    "Brut Lee",
]

# словарь для хранения выбранного ресторана
user_restaurant = {}


@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in RESTAURANTS:
        kb.add(KeyboardButton(r))
    await message.answer("Выберите ресторан:", reply_markup=kb)


@dp.message_handler(lambda msg: msg.text in RESTAURANTS)
async def choose_restaurant(message: types.Message):
    user_restaurant[message.from_user.id] = message.text
    await message.answer(f"Вы выбрали {message.text}. Напишите отзыв и при необходимости прикрепите фото.")


@dp.message_handler(content_types=['text', 'photo'])
async def handle_review(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_restaurant:
        await message.answer("Сначала выберите ресторан через /start")
        return

    restaurant = user_restaurant[user_id]
    text_review = message.text if message.text else ""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    photo_url = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path

        photo_name = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        downloaded = await bot.download_file(file_path)
        with open(photo_name, "wb") as f:
            f.write(downloaded.read())

        file_metadata = {"name": photo_name, "parents": [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(photo_name, mimetype="image/jpeg")
        uploaded = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()

        file_id_drive = uploaded.get("id")
        photo_url = f"https://drive.google.com/file/d/{file_id_drive}/view?usp=sharing"
        os.remove(photo_name)

    worksheet.append_row([date_str, restaurant, text_review, photo_url])

    await message.answer(
        "Спасибо за ваш акцент! Команда уже начала работу над улучшением!\n"
        "Чтобы оставить ещё один отзыв, нажмите /start"
    )


# -------------------- WEBHOOK --------------------
async def on_startup(app):
    webhook_url = f"https://{APP_NAME}.herokuapp.com/webhook/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)


async def on_shutdown(app):
    await bot.delete_webhook()


def main():
    from aiogram.dispatcher.webhook import get_new_configured_app
    app = get_new_configured_app(dp, path=f"/webhook/{BOT_TOKEN}")
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


if __name__ == "__main__":
    main()
