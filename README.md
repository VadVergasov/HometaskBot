HometaskBot
===========
Simple to use Telegram bot, that can send hometask from schools.by, belorussian e-diary platform.

Setup
-----------

```bash
git clone https://github.com/VadVergasov/HometaskBot.git
cd HometaskBot
python3 -m venv bot-env
bot-env\Scripts\activate.bat # For Windows.
source bot-env/bin/activate # For Linux and MacOS
pip install -r requirements.txt
```

Copy config.py.template to config.py insert all required values (example can be found in examples folder), then run by

```bash
python3 main.py
```
Basic usage
 -----
How to login: type `/login`. Bot will reply to this command with a message. You should reply to bot's message with your credentials in format `username password`. This will save your token and let you use the bot. 
<!--more-->
To get hometask, you should type `/hometask`. That will return button list with days in week. First and last buttons used to switch previous/upcoming weeks accordingly.
<!--more-->
`/set` command is useful for using bot in group chat. Typing this command will link the group's diary to the diary of the person who sent the command. *Note. Person, who sent the command should have token, registered in bot (in simple words, logged into the bot)*

Bad thing
-----
Entering parent's credentials and then asking for hometask will crash bot.

License
------------
Licensed under GPLv3. See LICENSE file.

