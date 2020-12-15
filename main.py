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


def get_ht(date):
    string = ""
    year = int("20" + str(date.split(".")[2]))
    month = int(date.split(".")[1])
    day = int(date.split(".")[0])
    monday = str(
        datetime.datetime.strptime(
            str(year)
            + "-W"
            + str(datetime.date(year, month, day).isocalendar()[1] - 1)
            + "-1",
            "%Y-W%W-%w",
        )
    ).split(" ")[0]

    quarter = 0

    if month > 8 and month < 11:
        quarter = 40
    elif month > 10 and month < 13:
        quarter = 42
    elif month > 0 and month < 4:
        quarter = 43
    elif month > 3 and month < 6:
        quarter = 44

    try:
        r = requests.get(
            "https://gymn29.schools.by/pupil/576266/dnevnik/quarter/"
            + str(quarter)
            + "/week/"
            + str(monday),
            headers=config.HEADERS,
        )
    except requests.exceptions.ConnectionError:
        try:
            r = requests.get(
                "https://gymn29.schools.by/pupil/576266/dnevnik/quarter/"
                + str(quarter)
                + "/week/"
                + str(monday),
                headers=config.HEADERS,
            )
        except requests.exceptions.ConnectionError:
            return config.SOMETHING_WENT_WRONG

    try:
        tree = html.fromstring(r.text)
    except etree.ParserError:
        return "Дата не действительна"

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
            string += (
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
            ) + ": "
            try:
                string += row.xpath("td[2]/div[2]/div")[0].text_content().strip() + "\n"
            except IndexError:
                string += "Ничего\n"
    return "```\n" + string + "\n```"


BOT = telebot.TeleBot(config.TG_TOKEN, parse_mode="MARKDOWN")


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
    BOT.reply_to(message, config.CHOOSE_DATE, reply_markup=keyboard)


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
            + config.HOMETASK_ON
            + " "
            + call.data
            + ":\n"
            + get_ht(call.data),
            disable_notification=True,
        )
        if str(call.from_user.id) in config.CUSTOM_TEXT.keys():
            BOT.answer_callback_query(
                call.id,
                show_alert=True,
                text=config.ANSWER_TEXT + config.CUSTOM_TEXT[str(call.from_user.id)],
            )
        else:
            BOT.answer_callback_query(
                call.id,
                show_alert=True,
                text=config.ANSWER_TEXT,
            )


BOT.polling()
