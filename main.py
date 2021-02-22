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
import collections
import datetime
import json
import logging
import os
import time

import flask
import requests
import telebot

import config

logging.basicConfig(filename="logging.log", level=logging.DEBUG)

if not os.path.isfile("database.json"):
    with open("database.json", "w") as f:
        f.write("{}")
with open("database.json", "r", encoding="utf-8") as f:
    TOKENS = json.load(f)

WEBHOOK_URL_BASE = "https://%s:%s" % (config.WEBHOOK_HOST, config.WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (config.TG_TOKEN)

BOT = telebot.TeleBot(config.TG_TOKEN, parse_mode="MARKDOWN")

app = flask.Flask(__name__)


@app.route(WEBHOOK_URL_PATH, methods=["POST"])
def webhook():
    """
    Processing requests from Telegram.
    """
    if flask.request.headers.get("content-type") == "application/json":
        json_string = flask.request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        BOT.process_new_updates([update])
        return ""
    flask.abort(403)


def get_token(username, password):
    """
    Getting token to access schools.by API.
    """
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


def check_if_logined(message):
    """
    Check if logined and return token.
    """
    token = None
    if not str(message.from_user.id) in TOKENS.keys():
        if not str(message.chat.id) in TOKENS.keys():
            return config.NO_INFO
        token = TOKENS[str(message.chat.id)]
    else:
        token = TOKENS[str(message.from_user.id)]
    return token


def write_to_log(message):
    """
    Writing messages to log.
    """
    logging.warning(str(datetime.datetime.today()) + ": " + str(message) + "\n")


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
    """
    Get hometask by date.
    """
    string = ""
    year, month, day = (
        "20" + str(date.split(".")[2]),
        date.split(".")[1],
        date.split(".")[0],
    )

    token = check_if_logined(message)
    if token == config.NO_INFO:
        return token

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
        request = requests.get(
            "https://schools.by/subdomain-api/pupil/"
            + str(pupil_id)
            + "/daybook/day/"
            + str(year + "-" + month + "-" + day),
            headers=headers,
        )
    except requests.exceptions.ConnectionError:
        try:
            request = requests.get(
                "https://schools.by/subdomain-api/pupil/"
                + str(pupil_id)
                + "/daybook/day/"
                + str(year + "-" + month + "-" + day),
                headers=headers,
            )
        except requests.exceptions.ConnectionError as error:
            write_to_log("RequestsError: {0}".format(error))
            return config.SOMETHING_WENT_WRONG

    hometask = request.json()

    try:
        for row in hometask["lessons"].keys():
            string += "`" + row + ". " + hometask["lessons"][row]["subject"] + ": "
            if hometask["lessons"][row]["lesson_data"]["hometask"] is None:
                string += "Ничего\n`"
            else:
                string += hometask["lessons"][row]["lesson_data"]["hometask"]["text"]
                if (
                    not "not_transferred" in hometask["lessons"][row]["lesson_data"]
                    or not "theme.text"
                    in hometask["lessons"][row]["lesson_data"]["not_transferred"]
                ):
                    if hometask["lessons"][row]["lesson_data"]["theme"] is not None:
                        string += (
                            " Тема: "
                            + hometask["lessons"][row]["lesson_data"]["theme"]["text"]
                        )
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


def check_for_creds(message):
    """
    Check if message is answer to login request message.
    """
    if message.text is not None and len(message.text.split(" ")) == 2:
        try:
            return message.reply_to_message.text == config.LOGIN_TEXT
        except AttributeError:
            return False
        return True
    return False


@BOT.message_handler(commands=["start", "help"])
def info(message):
    """
    Send message with info of bot.
    """
    if (
        str(message.chat.id) in TOKENS.keys()
        or str(message.from_user.id) in TOKENS.keys()
    ):
        token = check_if_logined(message)
        tries = 0
        headers = {"Authorization": "Token " + token + " "}
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
                "String 221 request status isn't equal to 200\n"
                + str(request.text)
                + "\n"
            )
            BOT.reply_to(
                message, config.SOMETHING_WENT_WRONG, disable_notification=True
            )
            return
        user_info = request.json()
        BOT.reply_to(
            message,
            config.LOGIN_INFO.format(
                user_info["last_name"], user_info["first_name"], user_info["subdomain"]
            ),
            disable_notification=True,
        )
    BOT.reply_to(message, config.ABOUT, disable_notification=True)


@BOT.message_handler(func=check_for_creds)
def getting_token(message):
    """
    Authenticating user.
    """
    token = get_token(*message.text.split(" "))
    if token == "Retry later":
        BOT.send_message(message.chat.id, config.RETRY_LATER)
        return
    if token == config.INCORRECT_CREDENTIALS:
        BOT.send_message(message.chat.id, config.INCORRECT_CREDENTIALS)
        return
    if token == "Network error":
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
    with open("database.json", "w") as fl_stream:
        json.dump(TOKENS, fl_stream)


def get_quarter(date, token):
    """
    Getting marks.
    """
    date = date - datetime.timedelta(days=date.weekday())
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
            "String 326 request status isn't equal to 200\n" + str(request.text) + "\n"
        )
        return config.SOMETHING_WENT_WRONG
    user_info = request.json()

    pupil_id = user_info["id"]

    marks = dict()

    week = dict()
    while "holidays" not in week.keys():
        date -= datetime.timedelta(days=7)
        tries = 0
        request = requests.get(
            "https://schools.by/subdomain-api/pupil/"
            + str(pupil_id)
            + "/daybook/week/"
            + date.strftime("%Y-%m-%d")
        )
        while request.status_code != 200 and tries < 10:
            request = requests.get(
                "https://schools.by/subdomain-api/pupil/"
                + str(pupil_id)
                + "/daybook/week/"
                + date.strftime("%Y-%m-%d"),
                headers=headers,
            )
            tries += 1
        if request.status_code != 200:
            write_to_log(
                "String 351 request status isn't equal to 200\n"
                + str(request.text)
                + "\n"
            )
            return config.SOMETHING_WENT_WRONG
        week = request.json()

    date += datetime.timedelta(days=7)

    week = dict()

    while "holidays" not in week.keys():
        tries = 0
        request = requests.get(
            "https://schools.by/subdomain-api/pupil/"
            + str(pupil_id)
            + "/daybook/week/"
            + date.strftime("%Y-%m-%d")
        )
        while request.status_code != 200 and tries < 10:
            request = requests.get(
                "https://schools.by/subdomain-api/pupil/"
                + str(pupil_id)
                + "/daybook/week/"
                + date.strftime("%Y-%m-%d"),
                headers=headers,
            )
            tries += 1
        if request.status_code != 200:
            write_to_log(
                "String 351 request status isn't equal to 200\n"
                + str(request.text)
                + "\n"
            )
            return config.SOMETHING_WENT_WRONG
        week = request.json()

        if "holidays" in week.keys():
            break

        for day in week.keys():
            for lesson in week[day]["lessons"].keys():
                if (
                    week[day]["lessons"][lesson]["mark"] == "н"
                    or week[day]["lessons"][lesson]["mark"] is None
                    or week[day]["lessons"][lesson]["mark"] == ""
                ):
                    continue
                if week[day]["lessons"][lesson]["subject"] not in marks.keys():
                    marks[week[day]["lessons"][lesson]["subject"]] = list()
                marks[week[day]["lessons"][lesson]["subject"]].append(
                    week[day]["lessons"][lesson]["mark"]
                )

        date += datetime.timedelta(days=7)

    marks = collections.OrderedDict(sorted(marks.items()))

    answer = ""
    for lesson in marks.keys():
        answer += "`" + str(lesson) + ": "
        for mark in marks[lesson]:
            answer += mark + " "
        answer = answer[:-1]
        answer += "\n`"
    return answer


@BOT.message_handler(commands=["marks"])
def get_marks(message):
    """
    Replying to message in Telegram.
    """
    if message.chat.type != "private":
        BOT.reply_to(message, config.GROUP_NOT_ALLOWED)
        return
    if not str(message.from_user.id) in TOKENS.keys():
        BOT.reply_to(message, config.NO_INFO)
        return
    token = check_if_logined(message)
    current = datetime.date.today()
    BOT.reply_to(message, get_quarter(current, token))


@BOT.message_handler(commands=["login"])
def login(message):
    """
    Replying to /login command.
    """
    if message.chat.type == "private":
        BOT.reply_to(message, config.LOGIN_TEXT, disable_notification=True)
    else:
        BOT.reply_to(message, config.GROUP_NOT_ALLOWED, disable_notification=True)


@BOT.message_handler(commands=["set"])
def set_default(message):
    """
    Setting default diary for chat.
    """
    if not str(message.from_user.id) in TOKENS.keys():
        BOT.reply_to(message, config.NO_INFO)
        return
    TOKENS[str(message.chat.id)] = TOKENS[str(message.from_user.id)]
    with open("database.json", "w") as fl_stream:
        json.dump(TOKENS, fl_stream)
    BOT.reply_to(message, "Ok", disable_notification=True)


@BOT.message_handler(commands=["hometask"])
def send_hometask(message):
    """
    Sending message with dates to choose.
    """
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
    """
    Answering for Telegram's callback.
    """
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
        with open("log.txt", "a") as fl_stream:
            fl_stream.write(
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

BOT.remove_webhook()

time.sleep(1)

BOT.set_webhook(
    url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
    certificate=open(config.WEBHOOK_SSL_CERT, "r"),
)

app.run(
    host=config.WEBHOOK_LISTEN,
    port=config.LISTEN_PORT,
    ssl_context=(config.WEBHOOK_SSL_CERT, config.WEBHOOK_SSL_PRIV),
    debug=False,
)
