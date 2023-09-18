from datetime import datetime, timedelta
from typing import Union

import yaml
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery)
from aiogram.types import Message
from entities import (
    get_booking_options, is_spot_free, get_parking_spot_by_name, get_user_by_username, get_user_by_name,
    create_reservation, is_user_admin, Reservation, ParkingSpot)

""" Текст, который будет выводить бот в сообщениях """
TEXT_BUTTON_1 = "Забронируй мне место на парковке"
TEXT_BUTTON_2 = "Отправь отчёт по брони"
TEXT_BUTTON_3 = "Добавить пользователя"
START_MESSAGE = "Привет!\nМеня зовут Анна.\nПомогу забронировать место на парковке."
HELP_MESSAGE = "Напиши мне что-нибудь"
ALL_SPOT_ARE_BUSY_MESSAGE = "К сожалению, все места заняты 😢"
DATE_REQUEST_MESSAGE = 'Сейчас посмотрим, что я могу Вам предложить...'
ACCESS_IS_NOT_ALLOWED_MESSAGE = "Обмануть меня захотели? Ваш логин я записала и передам руководству какой Вы хулиган!"
UNKNOWN_USER_MESSAGE_1 = "Простите, я с незнакомцами не разговариваю 🙄"
UNKNOWN_USER_MESSAGE_2 = "💅🏻"
BEFORE_SEND_REPORT_MESSAGE = "Конечно! Вот Ваш отчёт:\n\n"

ROLE_ADMINISTRATOR = "ADMINISTRATOR"
ROLE_AUDITOR = "AUDITOR"
ROLE_CLIENT = "CLIENT"

all_roles_obj = []
all_users_obj = []
all_spots_obj = []


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


def is_message_from_unknown_user(message: Union[Message, CallbackQuery]) -> bool:
    requester_username = message.from_user.username
    requester_user = get_user_by_username(requester_username)

    if requester_user is None:
        requester_first_name = message.from_user.first_name
        requester_last_name = message.from_user.last_name
        requester_user = get_user_by_name(requester_first_name, requester_last_name)
        if requester_user is None:
            return True

    return False


def create_start_menu_keyboard(
        is_show_book_button: bool,
        is_show_report_button: bool,
        is_show_add_user_button: bool,
) -> ReplyKeyboardMarkup:
    """ Создаёт клавиатуру, которая будет выводиться на команду /start """
    book_button: KeyboardButton = KeyboardButton(text=TEXT_BUTTON_1)
    report_button: KeyboardButton = KeyboardButton(text=TEXT_BUTTON_2)
    add_user_button: KeyboardButton = KeyboardButton(text=TEXT_BUTTON_3)

    buttons_list = []

    if is_show_book_button:
        buttons_list.append(book_button)
    if is_show_report_button:
        buttons_list.append(report_button)
    if is_show_add_user_button:
        buttons_list.append(add_user_button)

    # Создаем объект клавиатуры, добавляя в него кнопки
    keyboard: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
        keyboard=[buttons_list],
        resize_keyboard=True
    )

    return keyboard


@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
    """ Этот хэндлер обрабатывает команду "/start" """

    if is_message_from_unknown_user(message):
        await message.reply(
            UNKNOWN_USER_MESSAGE_1
        )
        await message.answer(
            UNKNOWN_USER_MESSAGE_2
        )
        return 0

    await message.answer(
        START_MESSAGE,
        reply_markup=create_start_menu_keyboard(True, True, True)
    )


# Этот хэндлер будет срабатывать на команду "/help"
@dp.message(Command(commands=['help']))
async def process_help_command(message: Message):
    await message.answer(HELP_MESSAGE)


@dp.message(F.text == TEXT_BUTTON_1)
async def process_answer(message: Message):
    """ Этот хэндлер срабатывает на просьбу забронировать место """
    if is_message_from_unknown_user(message):
        await message.reply(
            UNKNOWN_USER_MESSAGE_1
        )
        await message.answer(
            UNKNOWN_USER_MESSAGE_2
        )
        return 0

    available_options = get_booking_options()

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
    """ Обработчик события нажатия на inline-кнопку с предлагаемой датой брони """
    if is_message_from_unknown_user(callback_query):
        await callback_query.reply(
            UNKNOWN_USER_MESSAGE_1
        )
        await callback_query.answer(
            UNKNOWN_USER_MESSAGE_2
        )
        return 0

    # Получаем данные из нажатой кнопки
    button_data = callback_query.data

    query_data = button_data.split()
    booking_date = query_data[1]
    booking_spot = query_data[2]

    requester_username = callback_query.from_user.username

    if requester_username == "":
        requester_username = callback_query.from_user.first_name

    booking_spot_obj = get_parking_spot_by_name(booking_spot, all_spots_obj)
    if booking_spot_obj is None:
        print("Ошибка. Парковочное место не найдено.")

    #
    # Если у пользователя нет username, будет ошибка
    #
    requester_user = get_user_by_username(requester_username)
    if requester_user is None:
        requester_first_name = callback_query.from_user.first_name
        requester_last_name = callback_query.from_user.last_name
        requester_user = get_user_by_name(requester_first_name, requester_last_name)
        if requester_user is None:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text="Произошла какая-то ошибка. Мне так жаль 😢")
            return 0

    # Проверяем, что слот свободен.
    # Если это так, то создаём запись в БД
    if is_spot_free(booking_spot_obj, booking_date):
        create_reservation(
            spot_id=booking_spot_obj.id,
            date=booking_date,
            user=requester_user
        )

    # Отправляем ответ пользователю
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f'Хорошо) \nЗабронировала Вам место "{booking_spot}" на {booking_date}'
    )


if __name__ == '__main__':
    dp.run_polling(bot)


def run_bot(data: dict):
    global all_users_obj
    global all_roles_obj
    global all_spots_obj
    all_users_obj = data["all_users_obj"]
    all_roles_obj = data["all_roles_obj"]
    all_spots_obj = data["all_spots_obj"]

    print("Запускаю бота...")
    dp.run_polling(bot)


@dp.message(F.text == TEXT_BUTTON_2)
async def process_answer(message: Message):
    """ Обработчик запроса на выгрузку отчёта по занятым местам """
    requester_username = message.from_user.username
    is_allowed = is_user_admin(requester_username)

    if not is_allowed:
        await bot.send_message(
            chat_id=message.chat.id,
            text=ACCESS_IS_NOT_ALLOWED_MESSAGE
        )
        return
    # Вычисление даты две недели назад
    two_weeks_ago = datetime.now() - timedelta(weeks=2)
    # Выполнение запроса на выборку
    reservations = Reservation.select().where(Reservation.booking_date >= two_weeks_ago)
    report = ""

    # Вывод результатов
    for reservation in reservations:
        report += f"Дата бронирования: {reservation.booking_date}. "
        report += f"Место: {reservation.parking_spot_id.name}. "
        report += f"Пользователь: {reservation.username}.\n\n"

    await bot.send_message(
        chat_id=message.chat.id,
        text=f"{BEFORE_SEND_REPORT_MESSAGE}{report}"
    )
