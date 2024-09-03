import json
import os
import logging
import sys
import threading
import traceback
import telebot
from datetime import datetime

from flask import Flask, request, jsonify

app = Flask(__name__)

HOST = "127.0.0.1"
PORT = 44516
BYTES_PER_REP = 48 * 1000
REST_ID_LEN = 8
REP_TITLE_LEN = 25
LOGS_FILE = "logs_server.txt"
CONFIG_FILE = "server.json"
DB_FILE = "users.json"

LOGS_MAX_SIZE_MB = 20

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

file_handler = logging.FileHandler(LOGS_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

def read_db():
    with open(DB_FILE, 'r') as f:
        lines = f.read()
    try:
        ret_dict = json.loads(lines)
    except Exception as e:
        logger.error(
            f'read_config({DB_FILE}) error: {traceback.format_exc()}, can not parse json from data:{lines}')
        raise Exception('Read DB_FILE exception.')

    logger.info(f'read_db() finished. Loaded DB_FILE {ret_dict}')
    return ret_dict

def dump_db(db: dict):
    logger.info(f'dump_db() called. arg: {db}')
    db_str = json.dumps(db)
    with open(DB_FILE, 'w') as f:
        f.write(db_str)
    logger.info(f'dump_db() finished. DB dumped.')

def read_config() -> dict:
    logger.info(f'read_config() called')

    ret_dict = {}
    lines = ""
    with open(CONFIG_FILE, 'r') as f:
        lines = f.read()
    try:
        ret_dict = json.loads(lines)
    except Exception as e:
        logger.error(
            f'read_config({CONFIG_FILE}) error: {traceback.format_exc()}, can not parse json from data:{lines}')
        raise Exception('Read config exception.')

    logger.info(f'read_config() finished. Loaded config {ret_dict}')
    return ret_dict


def get_subs_for_rest(rest_id: str) -> list:
    subs = []
    for user in db.keys():
        try:
            if db[user]['rest_id'] == rest_id:
                subs.append(user)
        except Exception as e:
            logger.error(f'get_subs_for_rest error: {traceback.format_exc()}, continue...')

    return subs

def send_to_users(rest_id: str, rep_title: str, text: str):
    time_now = datetime.now().strftime("%m-%d-%y-%H-%M-%S")
    rep_title = rep_title.replace(' ', '_')
    rep_file = f'{rest_id}-{rep_title}-{time_now}.txt'
    path = os.path.join('reports', rep_file)
    with open(path, 'w') as f:
        f.write(text)

    subs = get_subs_for_rest(rest_id)
    if not subs:
        logger.warning(f'No subs for {rest_id}')
        return

    doc = open(path, 'rb')
    logger.warning(f'Report will be sent to {len(subs)} subs.')
    for sub_id in subs:
        bot.send_document(sub_id, doc, caption=rep_title)


@app.route('/send_rep', methods=['POST'])
def get_rep():
    print('received json', request.json)
    json = request.json
    if not json:
        raise Exception('No json in request.')
    rest_id = json["rest_id"]
    rep_title = json["rep_title"]
    rep_text = json["rep_text"]
    send_to_users(rest_id, rep_title, rep_text)

    return 'OK'

def run_http_server():
    app.run(host='0.0.0.0', port=config['port'])

def try_login(message) -> str:
    split = message.text.split(' ')
    if len(split) != 2 or message.text[0] != '@':
        return None

    user_id = message.from_user.id
    user_name = message.chat.username
    rest_id = split[0][1:]
    rest_pass = split[1]
    rest_list = config['restaurants']
    found_rest = None
    rest_name = ''
    logger.info(f'Attempt to login from {user_id}:{user_name} with {message.text}')
    for rest in rest_list:
        if rest['rest_id'] == rest_id:
            if rest['rest_pass'] == rest_pass:
                rest_name = rest["rest_name"]
                found_rest = f'{rest_name} : {rest_id}'
                break
            else:
                logger.error(f'Wrong password!')
                return 'Неверный логин или пароль.'

    if not found_rest:
        return 'Данные не найдены.'

    if user_id not in db.keys():
        db[user_id] = {'name': user_name}
        logger.info(f'DB: key for user {user_id} : {user_name} created.')
    if rest_id not in db[user_id]:
        db[user_id].update({'rest_id': rest_id, 'rest_name': rest_name})
        logger.info(f'DB: user {user_id} subscribed to {rest_id} restaurant.')
    dump_db(db)
    return f'Вы успешно подключились к ресторану {found_rest}'

def get_current_user_state(chat_id: str) -> str:
    chat_id = f'{chat_id}'.strip()
    try:
        rest_id = db[chat_id]['rest_id']
        rest_name = db[chat_id]['rest_name']
        return f'Вы подписаны на отчеты {rest_name} (ID:{rest_id})'
    except KeyError as e:
        return f'Подписка пуста.'

config = read_config()
bot = telebot.TeleBot(config['bot_token'])

@bot.message_handler(content_types=['text'])
def get_text_message(message):
    print(f'{message.from_user.id} saying: {message.text}')
    if '/start' in message.text:
        bot.send_message(message.from_user.id, 'Используйте комманду\n@id_объекта пароль\nчто-бы получать отчеты.')
    elif '@' in message.text:
        resp = try_login(message)
        if resp:
            bot.send_message(message.from_user.id, resp)
    elif '/getalllogs' in message.text:
        bot.send_message(message.from_user.id, 'Will do')
        doc = open('logs_server.txt', 'rb')
        bot.send_document(message.from_user.id, doc, caption='LOGS')
    else:
        resp = get_current_user_state(chat_id=message.from_user.id)
        bot.send_message(message.from_user.id, resp)

if __name__ == '__main__':
    logger.info('--------------------')
    logger.info('Report HTTP Server v2 init...')
    global db
    db = read_db()

    thread = threading.Thread(target=run_http_server)
    thread.start()
    bot.infinity_polling(none_stop=True)
