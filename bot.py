from typing import Any
import yaml
from aiogram import Bot, Dispatcher, F
from aiogram.dispatcher import router
from aiogram.filters import Command
from aiogram.handlers import InlineQueryHandler
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResult, InlineQueryResultsButton, InlineQueryResultArticle, \
    InputTextMessageContent, CallbackQuery
from aiogram.types import Message, InlineQuery
from entities import get_booking_options, is_spot_free, get_parking_spot_by_name, create_reservation

# Текст, который будет выводить бот в сообщениях
TEXT_BUTTON_1 = "Забронировать место на парковке"
TEXT_BUTTON_2 = "Отправь отчёт по брони"
START_MESSAGE = "Привет!\nМеня зовут Анна.\nПомогу забронировать место на парковке."
HELP_MESSAGE = "Напиши мне что-нибудь"
ALL_SPOT_ARE_BUSY_MESSAGE = "К сожалению, все места заняты 😢"
DATE_REQUEST_MESSAGE = 'Сейчас посмотрим, что я могу Вам предложить...'

parking_spots_obj = [] # Список всех праковочных мест


def get_inline_keyboard_for_booking(available_options: dict) -> InlineKeyboardMarkup:
    buttons_list = []

    # Создаём кнопку для каждой доступной даты
    for key, value in available_options.items():

        one_button: InlineKeyboardButton = InlineKeyboardButton(
            text=key.strftime("%d/%m/%Y"),
            callback_data=f'book {key} {value[0]}')
        buttons_list.append(one_button)

    # Создаем объект инлайн-клавиатуры
    keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup(
        inline_keyboard=[buttons_list])
    return keyboard


# Получаем данные из файла настроек
with open('settings.yml', 'r') as file:
    CONSTANTS = yaml.safe_load(file)
API_TOKEN = CONSTANTS['API_TOKEN']

bot: Bot = Bot(token=API_TOKEN)
dp: Dispatcher = Dispatcher()

button_1: KeyboardButton = KeyboardButton(text=TEXT_BUTTON_1)
button_2: KeyboardButton = KeyboardButton(text=TEXT_BUTTON_2)

# Создаем объект клавиатуры, добавляя в него кнопки
keyboard: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
    keyboard=[[button_1, button_2]],
    resize_keyboard=True
)


# Этот хэндлер будет срабатывать на команду "/start"
@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
    await message.answer(
        START_MESSAGE,
        reply_markup=keyboard
    )


# Этот хэндлер будет срабатывать на команду "/help"
@dp.message(Command(commands=['help']))
async def process_help_command(message: Message):
    await message.answer(HELP_MESSAGE)


# Этот хэндлер будет срабатывать на просьбу забронировать место и удалять клавиатуру
@dp.message(F.text == TEXT_BUTTON_1)
async def process_answer(message: Message):
    available_options = get_booking_options()
    print(available_options)

    if len(available_options) > 0:
        inline_keyboard = get_inline_keyboard_for_booking(available_options)

        await message.reply(
            text=DATE_REQUEST_MESSAGE,
            reply_markup=inline_keyboard
        )
    else:
        await message.reply(
            text=ALL_SPOT_ARE_BUSY_MESSAGE,
            reply_markup=ReplyKeyboardRemove()
        )


@dp.callback_query(lambda c: c.data.startswith('book'))
async def process_button_callback(callback_query: CallbackQuery):
    # Получаем данные из нажатой кнопки
    button_data = callback_query.data

    query_data = button_data.split()
    booking_date = query_data[1]
    booking_spot = query_data[2]
    requester_username = callback_query.from_user.username

    booking_spot_obj = get_parking_spot_by_name(booking_spot, parking_spots_obj)
    if booking_spot_obj is None:
        print("Ошибка. Парковочное место не найдено.")

    # Проверяем, что слот свободен.
    # Если это так, то создаём запись в БД
    if is_spot_free(booking_spot_obj, booking_date):
        create_reservation(
            spot_id=booking_spot_obj.id,
            date=booking_date,
            username=requester_username
        )

    # Отправляем ответ пользователю
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f'Хорошо)\nЗабронировала Вам место "{booking_spot}" на {booking_date}'
    )


if __name__ == '__main__':
    dp.run_polling(bot)


def run_bot(parking_spots):
    global parking_spots_obj
    parking_spots_obj = parking_spots

    print("Запускаю бота...")
    dp.run_polling(bot)