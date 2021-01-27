"""
Main code for this bot.
Copyright (C) 2020  Vadim Vergasov aka VadVergasov

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
import re

import requests
import telebot
from lxml import etree, html

import config

DATES = {
    "01.09.20": "30.10.20",
    "09.11.20": "27.12.20",
    "11.01.21": "28.03.21",
    "05.04.21": "31.05.21",
}


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
    valid = False
    for s in DATES.keys():
        start = datetime.datetime.strptime(s, "%d.%m.%y")
        end = datetime.datetime.strptime(DATES[s], "%d.%m.%y")
        if start <= datetime.datetime.strptime(date, "%d.%m.%y") <= end:
            valid = True
    if not valid:
        return config.NOT_VALID
    if datetime.datetime.strptime(date, "%d.%m.%y").weekday() > 4:
        return config.NOT_VALID
    return "OK"


def get_ht(date, message):
    string = ""
    year, month, day = (
        int("20" + str(date.split(".")[2])),
        int(date.split(".")[1]),
        int(date.split(".")[0]),
    )
    day = datetime.datetime(year, month, day)
    monday = str(day - datetime.timedelta(days=day.weekday())).split(" ")[0]

    quarter = 0

    if 8 < month < 11:
        quarter = 40
    elif 10 < month < 13:
        quarter = 42
    elif 0 < month < 4:
        quarter = 43
    elif 3 < month < 6:
        quarter = 44

    user_info = None
    if not os.path.isfile("database.json"):
        with open("database.json", "w") as f:
            f.write("{}")
    with open("database.json", "r", encoding="utf-8") as f:
        user_info = json.load(f)
    if not str(message.chat.id) in user_info.keys():
        return config.NO_INFO

    headers = config.HEADERS
    pupil_id = None
    if str(message.from_user.id) in user_info[str(message.chat.id)].keys():
        pupil_id = str(user_info[str(message.chat.id)][str(message.from_user.id)]["id"])
        headers["cookie"] = str(
            user_info[str(message.chat.id)][str(message.from_user.id)]["cookie"]
        )
    else:
        pupil_id = str(
            user_info[str(message.chat.id)][
                list(user_info[str(message.chat.id)].keys())[0]
            ]["id"]
        )
        headers["cookie"] = str(
            user_info[str(message.chat.id)][
                list(user_info[str(message.chat.id)].keys())[0]
            ]["cookie"]
        )

    try:
        r = requests.get(
            "https://gymn29.schools.by/pupil/"
            + pupil_id
            + "/dnevnik/quarter/"
            + str(quarter)
            + "/week/"
            + str(monday),
            headers=headers,
        )
    except requests.exceptions.ConnectionError:
        try:
            r = requests.get(
                "https://gymn29.schools.by/pupil/"
                + pupil_id
                + "/dnevnik/quarter/"
                + str(quarter)
                + "/week/"
                + str(monday),
                headers=headers,
            )
        except requests.exceptions.ConnectionError as error:
            write_to_log("RequestsError: {0}".format(error))
            return config.SOMETHING_WENT_WRONG

    try:
        tree = html.fromstring(r.text)
    except etree.ParserError:
        return config.NO_DATE

    date_str = "db_table_" + date

    xpath = "//*[@id='" + date_str + "']/tbody/tr"

    for row in tree.xpath(xpath):
        if (
            len(
                [
                    x
                    for x in re.sub(
                        "\n",
                        "",
                        row.xpath("td[1]/span")[0].text_content().strip().strip(),
                    ).split(" ")
                    if x != ""
                ]
            )
            > 1
        ):
            string += "`" + (
                " ".join(
                    [
                        x
                        for x in re.sub(
                            "\n",
                            "",
                            row.xpath("td[1]/span")[0].text_content().strip().strip(),
                        ).split(" ")
                        if x != ""
                    ]
                )
                + ": "
            )
            try:
                string += row.xpath("td[2]/div[2]/div")[0].text_content().strip()
            except IndexError:
                string += "Ничего"
            try:
                string += (
                    "`\n[Файлы](https://gymn29.schools.by"
                    + str(row.xpath("td[2]/div[1]/div[1]/a[1]/@href")[0])
                    + ")\n"
                )
            except IndexError:
                string += "`\n"
    return "" + string + "\n"


BOT = telebot.TeleBot(config.TG_TOKEN, parse_mode="MARKDOWN")


@BOT.message_handler(commands=["start", "help"])
def info(message):
    BOT.reply_to(message, config.ABOUT, disable_notification=True)


@BOT.message_handler(commands=["set"])
def add_member(message):
    if len(message.text.split(" ")) < 3:
        BOT.reply_to(message, config.INCORRECT_FORMAT, disable_notification=True)
        return
    current_chats = None
    if not os.path.isfile("database.json"):
        with open("database.json", "w") as f:
            f.write("{}")
    with open("database.json", "r", encoding="utf-8") as f:
        current_chats = json.load(f)
    current_chats[str(message.chat.id)] = {
        message.from_user.id: {
            "id": message.text.split(" ")[1],
            "cookie": str(message.text.split(" ")[2:])
            .replace(",", "")
            .replace("'", "")[1:-1],
        }
    }
    with open("database.json", "w") as f:
        json.dump(current_chats, f)
    BOT.reply_to(message, "Ok", disable_notification=True)


@BOT.message_handler(commands=["hometask"])
def send_hometask(message):
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
