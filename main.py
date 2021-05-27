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
import logging
import os
import time

import flask
import requests
import telebot
import ujson
from urllib3.exceptions import ProtocolError

import config
from api import auth, get_hometask, get_info, get_lastpage, get_pupils, get_week

logging.basicConfig(filename="logging.log", level=logging.DEBUG)

if not os.path.isfile("database.json"):
    with open("database.json", "w") as f:
        f.write("{}")
with open("database.json", "r", encoding="utf-8") as f:
    TOKENS = ujson.load(f)

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


@app.errorhandler(Exception)
def handle_exception(error):
    """
    Logging all unhandled exceptions.
    """
    logging.error(str(error))
    return "Error", 500


def get_str_of_day(date, delta):
    """
    Generating string for date with some delta in format dd.mm.yy.
    """
    return (date + datetime.timedelta(days=delta)).strftime("%d.%m.%y")


def update_config():
    """
    Updates local config, to cache some data.
    """
    with open("database.json", "w") as fl_stream:
        ujson.dump(TOKENS, fl_stream, ensure_ascii=False)


def check_if_logged(message):
    """
    Check if logged and return id for TOKENS dict.
    """
    if not str(message.from_user.id) in TOKENS.keys():
        if not str(message.chat.id) in TOKENS.keys():
            return False
        return str(message.chat.id)
    return str(message.from_user.id)


def write_to_log(message):
    """
    Writing messages to log.
    """
    logging.error("%s: %s", str(datetime.datetime.today()), str(message))


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
    if not check_if_logged(message):
        logging.debug("No info to get home task for user")
        return config.NO_INFO

    logging.debug("Trying to get pupil_id for home task")
    if TOKENS[check_if_logged(message)]["user_info"]["type"] == "Parent":
        try:
            pupil_id = TOKENS[check_if_logged(message)]["current"]
        except KeyError:
            return config.PUPIL_NOT_SELECTED
    else:
        pupil_id = TOKENS[check_if_logged(message)]["user_info"]["id"]

    logging.debug("Trying to get home task")

    session = requests.Session()

    try:
        hometask = get_hometask(
            TOKENS[check_if_logged(message)]["token"], date, pupil_id, session
        )
    except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
        logging.error("Error on get_hometask request to schools.by")
        return config.SOMETHING_WENT_WRONG

    try:
        logging.debug("Forming answer with home task")
        string = ""
        for row in hometask["lessons"].keys():
            string += "`" + row + ". " + hometask["lessons"][row]["subject"] + ": "
            if hometask["lessons"][row]["lesson_data"]["hometask"] is None or (
                isinstance(
                    hometask["lessons"][row]["lesson_data"]["hometask"]["text"],
                    str,
                )
                and hometask["lessons"][row]["lesson_data"]["hometask"]["text"] == ""
            ):
                string += "Ничего\n`"
            else:
                string += hometask["lessons"][row]["lesson_data"]["hometask"]["text"]
                if (
                    not "not_transferred" in hometask["lessons"][row]["lesson_data"]
                    or not "theme.text"
                    in hometask["lessons"][row]["lesson_data"]["not_transferred"]
                ):
                    if hometask["lessons"][row]["lesson_data"][
                        "theme"
                    ] is not None and (
                        isinstance(
                            hometask["lessons"][row]["lesson_data"]["theme"]["text"],
                            str,
                        )
                        and hometask["lessons"][row]["lesson_data"]["theme"]["text"]
                        != ""
                    ):
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
        logging.debug("Returning answer:\n%s", string)
        return string
    except KeyError:
        logging.debug("Not a working day was requested")
        return config.NOT_VALID


def check_for_credentials(message):
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


def get_quarter(key):
    """
    Getting marks.
    """
    date = datetime.date.today() - datetime.timedelta(
        days=datetime.date.today().weekday()
    )

    logging.debug("Trying to get pupil_id for marks")
    if TOKENS[key]["user_info"]["type"] == "Parent":
        try:
            pupil_id = TOKENS[key]["current"]
        except KeyError:
            return config.PUPIL_NOT_SELECTED
    else:
        pupil_id = TOKENS[key]["user_info"]["id"]

    marks = dict()

    week = dict()

    session = requests.Session()

    logging.debug("Looking for a start of quarter")
    while "holidays" not in week.keys():
        try:
            week = get_week(TOKENS[key]["token"], date, pupil_id, session)
            date -= datetime.timedelta(days=7)
        except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
            logging.error("Error on get_week request to schools.by")
            return config.SOMETHING_WENT_WRONG

    date += datetime.timedelta(days=14)

    week = dict()

    logging.debug("Looking for an end of quarter")
    while "holidays" not in week.keys():
        try:
            week = get_week(TOKENS[key]["token"], date, pupil_id, session)
        except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
            logging.error("Error on get_week request to schools.by")
            return config.SOMETHING_WENT_WRONG

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

    logging.debug("Forming answer with marks")
    answer = ""
    for lesson in marks.keys():
        answer += "`" + str(lesson) + ": "
        for mark in marks[lesson]:
            answer += mark + " "
        answer = answer[:-1]
        answer += "\n`"
    return answer


def lastpage(key):
    """
    Getting last page.
    """
    logging.debug("Trying to get pupil_id for last page")
    if TOKENS[key]["user_info"]["type"] == "Parent":
        try:
            pupil_id = TOKENS[key]["current"]
        except KeyError:
            return config.PUPIL_NOT_SELECTED
    else:
        pupil_id = TOKENS[key]["user_info"]["id"]

    session = requests.Session()

    response = get_lastpage(TOKENS[key]["token"], pupil_id, session)

    marks = dict()

    for row in response["rows"]:
        marks[row["class_subject"]["subject"]] = dict()
        marks[row["class_subject"]["subject"]]["quarters"] = list()
        marks[row["class_subject"]["subject"]]["year_mark"] = row["year_mark"]
        if marks[row["class_subject"]["subject"]]["year_mark"] is None:
            marks[row["class_subject"]["subject"]]["year_mark"] = "-"
        for number in row["quarter_marks"]:
            if row["quarter_marks"][number] is None:
                marks[row["class_subject"]["subject"]]["quarters"].append("-")
                continue
            marks[row["class_subject"]["subject"]]["quarters"].append(
                row["quarter_marks"][number]
            )

    marks = collections.OrderedDict(sorted(marks.items()))

    logging.debug("Forming answer with last page")
    answer = ""
    for lesson in marks.keys():
        answer += "`" + str(lesson) + ": "
        for mark in marks[lesson]["quarters"]:
            answer += mark + " "
        answer += "| " + str(marks[lesson]["year_mark"]) + "\n`"
    return answer


@BOT.message_handler(commands=["send"])
def send(message):
    """
    Send some message to all users of the bot, but only from admin's chat.
    """
    if message.chat.id == config.ADMIN_CHAT_ID:
        for chat in TOKENS.keys():
            BOT.send_message(int(chat), message.text[6:], disable_notification=True)


@BOT.message_handler(commands=["start", "help"])
def info(message):
    """
    Send message with info of bot.
    """
    if check_if_logged(message):
        user_info = TOKENS[check_if_logged(message)]["user_info"]

        logging.debug("Sending info about user")
        logging.debug(
            BOT.reply_to(
                message,
                config.LOGIN_INFO.format(
                    user_info["last_name"],
                    user_info["first_name"],
                    user_info["subdomain"],
                ),
                disable_notification=True,
            )
        )
    logging.debug("Sending help/start message")
    logging.debug(BOT.reply_to(message, config.ABOUT, disable_notification=True))


@BOT.message_handler(commands=["stop"])
def stop(message):
    """
    Stops bot by removing chat from database.
    """
    del TOKENS[str(message.chat.id)]
    update_config()
    logging.debug("Removed chat from database")
    logging.debug(BOT.reply_to(message, config.REMOVED))


@BOT.message_handler(func=check_for_credentials)
def getting_token(message):
    """
    Authenticating user.
    """
    token = None
    logging.debug("Deleting message with credentials")
    logging.debug(BOT.delete_message(message.chat.id, message.message_id))
    logging.debug("Sending message, that will be edited")
    message_from_bot = BOT.send_message(message.chat.id, config.PLEASE_WAIT)
    logging.debug(message_from_bot)
    session = requests.Session()
    try:
        logging.debug("Trying to auth user")
        token = auth(*message.text.split(" "), session)
    except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
        logging.error("Error on auth request to schools.by")
        logging.debug(
            BOT.edit_message_text(
                chat_id=message_from_bot.chat.id,
                message_id=message_from_bot.message_id,
                text=config.SOMETHING_WENT_WRONG,
            )
        )
        return
    except KeyError:
        logging.debug("Incorrect credentials")
        logging.debug(
            BOT.edit_message_text(
                chat_id=message_from_bot.chat.id,
                message_id=message_from_bot.message_id,
                text=config.INCORRECT_CREDENTIALS,
            )
        )
        return

    TOKENS[str(message.from_user.id)] = dict()
    TOKENS[str(message.from_user.id)]["token"] = token

    try:
        TOKENS[str(message.from_user.id)]["user_info"] = get_info(
            TOKENS[str(message.from_user.id)]["token"], session
        )
    except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
        logging.error("Error on get_info request to schools.by")
        logging.debug(
            BOT.edit_message_text(
                chat_id=message_from_bot.chat.id,
                message_id=message_from_bot.message_id,
                text=config.SOMETHING_WENT_WRONG,
            )
        )
        return

    if TOKENS[str(message.from_user.id)]["user_info"]["type"] == "Parent":
        try:
            TOKENS[str(message.from_user.id)]["pupils"] = get_pupils(
                token, TOKENS[str(message.from_user.id)]["user_info"]["id"], session
            )
        except (SystemError, ConnectionError, ConnectionResetError, ProtocolError):
            logging.error("Error on get_pupils request to schools.by")
            logging.debug(
                BOT.edit_message_text(
                    chat_id=message_from_bot.chat.id,
                    message_id=message_from_bot.message_id,
                    text=config.SOMETHING_WENT_WRONG,
                )
            )
            return

    logging.debug("Replying, that user is authenticated")
    logging.debug(
        BOT.edit_message_text(
            chat_id=message_from_bot.chat.id,
            message_id=message_from_bot.message_id,
            text=config.LOGGED_IN.format(
                TOKENS[str(message.from_user.id)]["user_info"]["last_name"],
                TOKENS[str(message.from_user.id)]["user_info"]["first_name"],
                TOKENS[str(message.from_user.id)]["user_info"]["subdomain"],
            ),
        )
    )
    update_config()


@BOT.message_handler(commands=["marks"])
def get_marks(message):
    """
    Replying to message in Telegram.
    """
    if message.chat.type != "private":
        logging.debug("Not a private chat, can't get marks")
        logging.debug(BOT.reply_to(message, config.GROUP_NOT_ALLOWED))
        return
    if not check_if_logged(message):
        logging.debug("No info to get marks")
        logging.debug(BOT.reply_to(message, config.NO_INFO))
        return
    logging.debug("Replying with marks")
    bots_message = BOT.reply_to(message, config.PLEASE_WAIT)
    logging.debug(bots_message)
    logging.debug(
        BOT.edit_message_text(
            chat_id=bots_message.chat.id,
            message_id=bots_message.message_id,
            text=get_quarter(check_if_logged(message)),
        )
    )


@BOT.message_handler(commands=["lastpage"])
def last(message):
    """
    Replying to /lastpage command.
    """
    if message.chat.type != "private":
        logging.debug("Not a private chat, can't get last page")
        logging.debug(BOT.reply_to(message, config.GROUP_NOT_ALLOWED))
        return
    if not check_if_logged(message):
        logging.debug("No info to get last page")
        logging.debug(BOT.reply_to(message, config.NO_INFO))
        return
    logging.debug("Replying with last page")
    bots_message = BOT.reply_to(message, config.PLEASE_WAIT)
    logging.debug(bots_message)
    logging.debug(
        BOT.edit_message_text(
            chat_id=bots_message.chat.id,
            message_id=bots_message.message_id,
            text=lastpage(check_if_logged(message)),
        )
    )


@BOT.message_handler(commands=["login"])
def login(message):
    """
    Replying to /login command.
    """
    if message.chat.type == "private":
        logging.debug("Replying to a login message")
        logging.debug(
            BOT.reply_to(message, config.LOGIN_TEXT, disable_notification=True)
        )
    else:
        logging.debug("Not a private chat, can't log in")
        logging.debug(
            BOT.reply_to(message, config.GROUP_NOT_ALLOWED, disable_notification=True)
        )


@BOT.message_handler(commands=["set"])
def set_default(message):
    """
    Setting default diary for chat.
    """
    if not check_if_logged(message):
        logging.debug("No info for seting as default")
        logging.debug(BOT.reply_to(message, config.NO_INFO))
        return
    logging.debug("Setting to default")
    TOKENS[str(message.chat.id)] = TOKENS[str(message.from_user.id)]
    update_config()
    logging.debug("Replying to inform, that user is now default for chat")
    logging.debug(BOT.reply_to(message, "Ok", disable_notification=True))


@BOT.message_handler(commands=["hometask"])
def send_hometask(message):
    """
    Sending message with dates to choose.
    """
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday
    keyboard = telebot.types.InlineKeyboardMarkup()
    logging.debug("Configuring reply keyboard")
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
    logging.debug("Answering to message with dates")
    bots_message = BOT.reply_to(
        message,
        config.CHOOSE_DATE,
        reply_markup=keyboard,
        disable_notification=True,
    )
    logging.debug(bots_message)
    if message.chat.type == "private":
        BOT.unpin_all_chat_messages(message.chat.id)
        logging.debug(
            BOT.pin_chat_message(
                message.chat.id, bots_message.message_id, disable_notification=True
            )
        )


@BOT.message_handler(commands=["select"])
def select_pupil(message):
    """
    Selecting pupil.
    """
    if not check_if_logged(message):
        logging.debug("No info for selecting pupil")
        logging.debug(BOT.reply_to(message, config.NO_INFO))
        return
    if TOKENS[check_if_logged(message)]["user_info"]["type"] != "Parent":
        logging.debug("Not a parent")
        logging.debug(BOT.reply_to(message, config.NOT_A_PARENT))
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    logging.debug("Configuring reply keyboard")
    for pupil in TOKENS[check_if_logged(message)]["pupils"]:
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=pupil["last_name"] + " " + pupil["first_name"],
                callback_data="ID: " + str(pupil["id"]),
            )
        )
    logging.debug("Answering to message with pupils")
    logging.debug(
        BOT.reply_to(
            message,
            config.CHOOSE_PUPIL,
            reply_markup=keyboard,
            disable_notification=True,
        )
    )


@BOT.callback_query_handler(func=lambda call: True)
def callback(call):
    """
    Answering for Telegram's callback.
    """
    logging.debug("Starting processing callback %s", str(call.data))
    if call.data[:3] == "ID:":
        logging.debug("Setting default pupil")
        pupil_id = int(call.data.split(" ")[1])
        TOKENS[check_if_logged(call.message.reply_to_message)]["current"] = pupil_id
        update_config()
        pupil_name = None
        for pupil in TOKENS[check_if_logged(call.message.reply_to_message)]["pupils"]:
            if int(pupil["id"]) == pupil_id:
                pupil_name = pupil["last_name"] + " " + pupil["first_name"]
                break
        logging.debug("Answering to callback to set pupil")
        logging.debug(
            BOT.answer_callback_query(
                call.id, show_alert=False, text=config.SELECTED_PUPIL.format(pupil_name)
            )
        )
    elif len(call.data.split(" ")) == 3:
        logging.debug("Changing week")
        start_of_week = datetime.datetime.strptime(
            str(call.data).split(" ")[0], "%d.%m.%y"
        )
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=get_str_of_day(start_of_week, -7)
                + " - "
                + get_str_of_day(start_of_week, -1),
                callback_data=get_str_of_day(start_of_week, -7)
                + " - "
                + get_str_of_day(start_of_week, -1),
            )
        )  # previous button.
        for number in range(5):
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    text=get_str_of_day(start_of_week, number),
                    callback_data=get_str_of_day(start_of_week, number),
                )
            )
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text=get_str_of_day(start_of_week, 7)
                + " - "
                + get_str_of_day(start_of_week, 13),
                callback_data=get_str_of_day(start_of_week, 7)
                + " - "
                + get_str_of_day(start_of_week, 13),
            )
        )  # next_button.

        logging.debug("Editing previous message to change week")
        logging.debug(
            BOT.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboard,
            )
        )
        logging.debug("Answering to callback to change week")
        logging.debug(
            BOT.answer_callback_query(
                call.id, show_alert=False, text=config.WEEK_CHANGE_TEXT
            )
        )
    else:
        logging.debug("Getting home task")
        if check_date(call.data) != "OK":
            logging.debug(
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
            )
            return
        write_to_log(
            str(call.from_user.first_name)
            + " "
            + str(call.from_user.last_name)
            + " "
            + str(call.from_user.username)
            + " "
            + str(call.from_user.id)
            + " Chat id : "
            + str(call.message.chat.id)
        )
        logging.debug("Sending hometask")
        logging.debug(
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
        )
        logging.debug("Answering to callback from home task")
        if str(call.from_user.id) in config.CUSTOM_TEXT.keys():
            logging.debug(
                BOT.answer_callback_query(
                    call.id,
                    show_alert=False,
                    text=config.ANSWER_TEXT
                    + config.CUSTOM_TEXT[str(call.from_user.id)],
                )
            )
        else:
            logging.debug(
                BOT.answer_callback_query(
                    call.id,
                    show_alert=False,
                    text=config.ANSWER_TEXT,
                )
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

if __name__ == "__main__":
    app.run(
        host=config.WEBHOOK_LISTEN,
        port=config.LISTEN_PORT,
        debug=False,
    )
