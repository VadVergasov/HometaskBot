"""
Working with schools.by API.
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
import logging

import requests


def auth(username, password):
    """
    Authinticating and getting token.
    """
    request = requests.post(
        "https://schools.by/api/auth",
        data={"username": username, "password": password},
    )
    if request.status_code != 200:
        logging.error(str(request.text))
        raise SystemError("Can't access API")
    token = request.json()["token"]
    return token


def get_info(token):
    """
    Get user info from schools.by
    """
    headers = {"Authorization": "Token " + token + " "}
    request = requests.get(
        "https://schools.by/subdomain-api/user/current", headers=headers
    )
    if request.status_code != 200:
        logging.error(str(request.text))
        raise SystemError("Can't access API")
    return request.json()


def get_pupils(token, parent_id):
    """
    Get all pupil_ids by parent_id
    """
    headers = {"Authorization": "Token " + token + " "}
    request = requests.get(
        "https://schools.by/subdomain-api/parent/" + str(parent_id) + "/pupils/",
        headers=headers,
    )
    if request.status_code != 200:
        logging.error(str(request.text))
        raise SystemError("Can't access API")
    return request.json()


def get_hometask(token, date, pupil_id):
    """
    Get hometask by date for pupil
    """
    year, month, day = (
        "20" + str(date.split(".")[2]),
        date.split(".")[1],
        date.split(".")[0],
    )
    headers = {"Authorization": "Token " + token + " "}
    request = requests.get(
        "https://schools.by/subdomain-api/pupil/"
        + str(pupil_id)
        + "/daybook/day/"
        + str(year + "-" + month + "-" + day),
        headers=headers,
    )
    if request.status_code != 200:
        logging.error(str(request.text))
        raise SystemError("Can't access API")
    return request.json()


def get_week(token, date, pupil_id):
    """
    Get hometask on week.
    """
    headers = {"Authorization": "Token " + token + " "}
    request = requests.get(
        "https://schools.by/subdomain-api/pupil/"
        + str(pupil_id)
        + "/daybook/week/"
        + date.strftime("%Y-%m-%d"),
        headers=headers,
    )
    if request.status_code != 200:
        logging.error(str(request.text))
        raise SystemError("Can't access API")
    return request.json()
