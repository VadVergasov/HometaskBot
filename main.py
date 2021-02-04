"""
Main code for this bot.
Copyright (C) 2021  Vadim Vergasov aka VadVergasov

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import datetime
import json
import os

import requests
import telebot

import config

if not os.path.isfile("database.json"):
    with open("database.json", "w") as f:
        f.write("{}")
with open("database.json", "r", encoding="utf-8") as f:
    TOKENS = json.load(f)


def get_token(username, password):
    try:
        tries = 0
        request = requests.post(
            "https://schools.by/api/auth",
            data={"username": username, "password": password},
        )
        while tries < 10 and request.status_code == 200:
            try:
                if (
                    request.json()["details"]
                    == "Невозможно войти с предоставленными учетными данными."
                ):
                    return config.INCORRECT_CREDENTIALS
            except:
                pass
            request = requests.post(
                "https://schools.by/api/auth",
                data={"username": username, "password": password},
            )
            tries += 1
        if request.status_code != 200:
            return "Retry later"
        token = request.json()["token"]
        return token
    except ConnectionResetError:
        return "Network error"


def write_to_log(message):
    with open("log.txt", "a+") as fl:
        fl.write(str(message) + "\n")


def check_date(date):
    """
    Check if date is correct or not.
    """
    try:
        datetime.datetime.strptime(date, "%d.%m.%y")
    except ValueError:
        return config.INCORRECT_FORMAT
    if datetime.datetime.strptime(date, "%d.%m.%y").weekday() > 4:
        return config.NOT_VALID
    return "OK"


def get_ht(date, message):
    string = ""
    year, month, day = (
        "20" + str(date.split(".")[2]),
        date.split(".")[1],
        date.split(".")[0],
    )

    token = None
    if not str(message.from_user.id) in TOKENS.keys():
        if not str(message.chat.id) in TOKENS.keys():
            return config.NO_INFO
        token = TOKENS[str(message.chat.id)]
    else:
        token = TOKENS[str(message.from_user.id)]

    headers = {"Authorization": "Token " + token + " "}

    request = requests.get(
        "https://schools.by/subdomain-api/user/current", headers=headers
    )
    tries = 0
    while request.status_code != 200 and tries < 10:
        request = requests.get(
            "https://schools.by/subdomain-api/user/current", headers=headers
        )
        tries += 1
    if request.status_code != 200:
        write_to_log(
            "String 99 request status isn't equal to 200\n" + str(request.text) + "\n"
        )
        return config.SOMETHING_WENT_WRONG
    user_info = request.json()

    pupil_id = user_info["id"]

    try:
        r = requests.get(
            "https://schools.by/subdomain-api/pupil/"
            + str(pupil_id)
            + "/daybook/day/"
            + str(year + "-" + month + "-" + day),
            headers=headers,
        )
    except requests.exceptions.ConnectionError:
        try:
            r = requests.get(
                "https://schools.by/subdomain-api/pupil/"
                + str(pupil_id)
                + "/daybook/day/"
                + str(year + "-" + month + "-" + day),
                headers=headers,
            )
        except requests.exceptions.ConnectionError as error:
            write_to_log("RequestsError: {0}".format(error))
            return config.SOMETHING_WENT_WRONG

    hometask = r.json()

    try:
        for row in hometask["lessons"].keys():
            string += "`" + row + ". " + hometask["lessons"][row]["subject"] + ": "
            if hometask["lessons"][row]["lesson_data"]["hometask"] == None:
                string += "Ничего\n`"
            else:
                string += hometask["lessons"][row]["lesson_data"]["hometask"]["text"]
                if (
                    len(
                        hometask["lessons"][row]["lesson_data"]["hometask"][
                            "attachments"
                        ]
                    )
                    != 0
                ):
                    string += "`"
                    for attachment in hometask["lessons"][row]["lesson_data"][
                        "hometask"
                    ]["attachments"]:
                        string += "\n[Файл](" + str(attachment["file"]) + ")\n"
                else:
                    string += "`\n"
        return string
    except KeyError:
        return config.NOT_VALID


BOT = telebot.TeleBot(config.TG_TOKEN, parse_mode="MARKDOWN")


def check(message):
    """
    Check if admin
    """
    id = BOT.get_me().id
    if (
        BOT.get_chat_member(message.chat.id, str(id)).can_delete_messages
        or message.chat.type == "private"
    ):
        return True
    BOT.reply_to(message, config.NO_ADMIN)
    return False


def check_for_creds(message):
    try:
        if len(message.text.split(" ")) == 2:
            try:
                message.reply_to_message.chat.id
            except AttributeError:
                return False
            return True
        return False
    except:
        return False


@BOT.message_handler(commands=["start", "help"])
def info(message):
    if not check(message):
        return
    BOT.reply_to(message, config.ABOUT, disable_notification=True)


@BOT.message_handler(func=check_for_creds)
def getting_token(message):
    token = get_token(*message.text.split(" "))
    if token == "Retry later":
        BOT.send_message(message.chat.id, config.RETRY_LATER)
        return
    elif token == config.INCORRECT_CREDENTIALS:
        BOT.send_message(message.chat.id, config.INCORRECT_CREDENTIALS)
        return
    elif token == "Network error":
        BOT.send_message(message.chat.id, config.RETRY_LATER)
        return
    TOKENS[str(message.from_user.id)] = token
    tries = 0
    headers = {"Authorization": "Token " + TOKENS[str(message.from_user.id)] + " "}
    request = requests.get(
        "https://schools.by/subdomain-api/user/current", headers=headers
    )
    while request.status_code != 200 and tries < 10:
        request = requests.get(
            "https://schools.by/subdomain-api/user/current", headers=headers
        )
        tries += 1
    if request.status_code != 200:
        write_to_log(
            "String 211 request status isn't equal to 200\n" + str(request.text) + "\n"
        )
        return config.SOMETHING_WENT_WRONG
    user_info = request.json()
    BOT.send_message(
        message.chat.id,
        config.LOGGED_IN.format(
            user_info["last_name"], user_info["first_name"], user_info["subdomain"]
        ),
    )
    with open("database.json", "w") as fl:
        json.dump(TOKENS, fl)
    if message.chat.type != "private":
        BOT.delete_message(
            message.reply_to_message.chat.id,
            message.reply_to_message.message_id,
        )
        BOT.delete_message(
            message.chat.id,
            message.message_id,
        )


@BOT.message_handler(commands=["login"])
def login(message):
    if not check(message):
        return
    BOT.reply_to(message, config.LOGIN_TEXT, disable_notification=True)


@BOT.message_handler(commands=["set"])
def add_member(message):
    if not check(message):
        return
    if not str(message.from_user.id) in TOKENS.keys():
        BOT.reply_to(message, config.NO_INFO)
        return
    TOKENS[str(message.chat.id)] = TOKENS[str(message.from_user.id)]
    with open("database.json", "w") as fl:
        json.dump(TOKENS, fl)
    BOT.reply_to(message, "Ok", disable_notification=True)


@BOT.message_handler(commands=["hometask"])
def send_hometask(message):
    if not check(message):
        return
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            text=(start_of_week - datetime.timedelta(days=7)).strftime("%d.%m.%y")
            + " - "
            + (start_of_week - datetime.timedelta(days=1)).strftime("%d.%m.%y"),
            callback_data=(start_of_week - datetime.timedelta(days=7)).strftime(
                "%d.%m.%y"
            )
            + " - "
            + (start_of_week - datetime.timedelta(days=1)).strftime("%d.%m.%y"),
        )
    )  # previous button.
    for i in range(5):
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=(start_of_week + datetime.timedelta(days=i)).strftime("%d.%m.%y"),
                callback_data=(start_of_week + datetime.timedelta(days=i)).strftime(
                    "%d.%m.%y"
                ),
            )
        )
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            text=(start_of_week + datetime.timedelta(days=7)).strftime("%d.%m.%y")
            + " - "
            + (start_of_week + datetime.timedelta(days=13)).strftime("%d.%m.%y"),
            callback_data=(start_of_week + datetime.timedelta(days=7)).strftime(
                "%d.%m.%y"
            )
            + " - "
            + (start_of_week + datetime.timedelta(days=13)).strftime("%d.%m.%y"),
        )
    )  # next_button.
    BOT.reply_to(
        message, config.CHOOSE_DATE, reply_markup=keyboard, disable_notification=True
    )


@BOT.callback_query_handler(func=lambda call: True)
def callback(call):
    if len(call.data.split(" ")) == 3:
        start_of_week = datetime.datetime.strptime(
            str(call.data).split(" ")[0], "%d.%m.%y"
        )
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=(start_of_week - datetime.timedelta(days=7)).strftime("%d.%m.%y")
                + " - "
                + (start_of_week - datetime.timedelta(days=1)).strftime("%d.%m.%y"),
                callback_data=(start_of_week - datetime.timedelta(days=7)).strftime(
                    "%d.%m.%y"
                )
                + " - "
                + (start_of_week - datetime.timedelta(days=1)).strftime("%d.%m.%y"),
            )
        )  # previous button.
        for i in range(5):
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    text=(start_of_week + datetime.timedelta(days=i)).strftime(
                        "%d.%m.%y"
                    ),
                    callback_data=(start_of_week + datetime.timedelta(days=i)).strftime(
                        "%d.%m.%y"
                    ),
                )
            )
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=(start_of_week + datetime.timedelta(days=7)).strftime("%d.%m.%y")
                + " - "
                + (start_of_week + datetime.timedelta(days=13)).strftime("%d.%m.%y"),
                callback_data=(start_of_week + datetime.timedelta(days=7)).strftime(
                    "%d.%m.%y"
                )
                + " - "
                + (start_of_week + datetime.timedelta(days=13)).strftime("%d.%m.%y"),
            )
        )  # next_button.

        BOT.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboard,
        )
        BOT.answer_callback_query(
            call.id, show_alert=False, text=config.WEEK_CHANGE_TEXT
        )
    else:
        if check_date(call.data) != "OK":
            BOT.send_message(
                call.message.chat.id,
                "["
                + str(call.from_user.first_name)
                + "](tg://user?id="
                + str(call.from_user.id)
                + "), "
                + check_date(call.data),
                disable_notification=True,
            )
            return
        with open("log.txt", "a") as f:
            f.write(
                str(call.from_user.first_name)
                + " "
                + str(call.from_user.last_name)
                + " "
                + str(call.from_user.username)
                + " "
                + str(call.from_user.id)
                + " Chat id : "
                + str(call.message.chat.id)
                + "\n"
            )
        BOT.send_message(
            call.message.chat.id,
            text="["
            + str(call.from_user.first_name)
            + "](tg://user?id="
            + str(call.from_user.id)
            + "), "
            + str(config.HOMETASK_ON)
            + " "
            + str(call.data)
            + ":\n"
            + get_ht(call.data, call.message.reply_to_message),
            disable_notification=True,
        )
        if str(call.from_user.id) in config.CUSTOM_TEXT.keys():
            BOT.answer_callback_query(
                call.id,
                show_alert=False,
                text=config.ANSWER_TEXT + config.CUSTOM_TEXT[str(call.from_user.id)],
            )
        else:
            BOT.answer_callback_query(
                call.id,
                show_alert=False,
                text=config.ANSWER_TEXT,
            )


commands = []
for command in config.COMMANDS.keys():
    commands.append(telebot.types.BotCommand(command, config.COMMANDS[command]))

BOT.set_my_commands(commands)

BOT.polling()
