import os
import random
import requests
import logging
import sys
import json
import threading
import time
import traceback
import re
import socket

CONFIG_FILE = "config.json"
SERVER_PORT = 44515
LOGS_FILE = "logs.txt"
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


def cleanup_logs_if_need():
    try:
        file_stats = os.stat(LOGS_FILE)
        size_mb = file_stats.st_size / (1024 * 1024)
        if size_mb > LOGS_MAX_SIZE_MB:
            logger.info(f'{LOGS_FILE} file is too large, will delete it.')
            os.remove(LOGS_FILE)
        else:
            print(f'{LOGS_FILE} is not so big ({size_mb} MB), max size is {LOGS_MAX_SIZE_MB} :)')
    except Exception as e:
        logger.error(f'cleanup_logs_if_need() error: {traceback.format_exc()}')


def check_dirs_files():
    dirs = ['tosend', 'deleted']
    for dir in dirs:
        if not os.path.isdir(dir):
            logger.info(f'Creating directory "{dir}" ')
            os.makedirs(dir)


def get_bot_server_ip(log_everything: bool = False) -> str:
    global config
    get_ip_addr = config['get_ip']
    def_ip_addr = config['default_ip']
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
    try:
        resp = requests.get(get_ip_addr, headers=headers)
        recv_ip = resp.text.strip()
        if (len(recv_ip.split('\n')) > 1 or len(recv_ip.split('.')) != 4):
            raise Exception(f'{recv_ip} is not an ip or domain addr.')
        if log_everything:
            logger.info(f'Will use received ip: {recv_ip}')
        return recv_ip
    except Exception as e1:
        err = f'get_bot_server_ip() error while connecting to {get_ip_addr}: {e1}'
        print(err)
        if log_everything:
            logger.error(err)
            logger.error(traceback.format_exc())
            logger.info(f'Will use default_ip: {def_ip_addr}')
        return def_ip_addr


def get_report_by_markers(marker: list, lines: list) -> list:
    rep_lines = []
    print(lines)
    mark_start = marker[0]
    mark_end = marker[1]
    if len(mark_end) == 0:
        mark_end = "$fileend"

    print(f'Marker start:{mark_start}; Marker end:{mark_end};')
    rep_found = False
    for line in lines:
        if not rep_found:
            if re.match(mark_start, line):
                print(f'Found START match in line:{line}')
                rep_found = True
            else:
                print(f'do not match:"{line}"')
        else:
            if mark_end != '$fileend' and re.match(mark_end, line):
                print(f'Found END match in line:{line}')
                if config['include_last_marker'] == True:
                    rep_lines.append(line)
                break

            rep_lines.append(line)

    # print(f'Ret report:{rep_lines}')
    return rep_lines

def prepare_rep_to_send(rep_plain_text: str) -> str:
    str_rep = rep_plain_text.strip()
    str_rep = str(config["restaurant_id"]) + ' [сменный/другие]\n' + str_rep
    logger.info(f'Following data prepared for sending:\n{str_rep}')
    return str_rep


def copy_and_delete_original(fpath) -> str:
    print(f'copy_and_delete_original() called:{fpath}')
    tmp_name = f'rep{random.randint(0, 9999999)}.txt'
    path_orig_copy = os.path.join('deleted', tmp_name)
    open(path_orig_copy, 'wb').write(open(fpath, 'rb').read())  # Copy
    os.remove(fpath)
    return tmp_name


def save_report_tosend_folder(tmp_name, rep_lines: list):
    max_msg_size = 1900
    rep_plain_text = '\n'.join([i for i in rep_lines[0:]])
    if not len(rep_plain_text) > max_msg_size:
        path = os.path.join('tosend', tmp_name)
        rep_to_send = prepare_rep_to_send(rep_plain_text)
        with open(path, 'w') as f:
            f.write(rep_to_send)
        logger.info(f'Report saved to {path}')
    else:
        messages = []
        tmp_message_data = rep_plain_text
        logger.info(f'Message to long, will be divided')
        for i in range(10):
            if len(tmp_message_data) > max_msg_size:
                rep_part = tmp_message_data[0:max_msg_size]
                rep_part = f'[часть {i+1}]\n{rep_part}'
                tmp_message_data = tmp_message_data[max_msg_size:]
                messages.append(rep_part)
            else:
                rep_part = tmp_message_data[0:]
                rep_part = f'[часть {i + 1}]\n{rep_part}'
                messages.append(rep_part)
                break
        for i in range(len(messages)):
            path = os.path.join('tosend', f'{i}-{tmp_name}')
            rep_to_send = prepare_rep_to_send(messages[i])
            with open(path, 'w') as f:
                f.write(rep_to_send)
            logger.info(f'Report part {i} saved to {path}')


def check_for_reports_loop():
    while True:
        print('check_for_reports_loop() invoked')
        try:
            files = []
            printer_dir = config["printer_dir"]
            for file in os.listdir(printer_dir):
                fpath = os.path.join(printer_dir, file)
                if not os.path.isdir(fpath) and file != ".DS_Store":
                    files.append(fpath)

            print(f'Files to check:{files}')

            for file in files:
                lines = None
                print(f'Reading file {file}')
                with open(file, 'r') as f:
                    lines = f.readlines()
                    #lines = data.split('\n')
                for marker in config['markers']:
                    print('------------------------')
                    print(f'Current marker {marker}')
                    report_lines = get_report_by_markers(marker, lines)
                    if len(report_lines) > 0:
                        tmp_name = copy_and_delete_original(file)
                        save_report_tosend_folder(tmp_name, report_lines)
                    else:
                        print('Report not found')

        except Exception as e:
            logger.error(f'check_for_reports_loop() error: {e} {traceback.format_exc()}')

        print(f'check_for_reports_loop sleep {config["sleep_parse_sec"]} sec.')
        time.sleep(config["sleep_parse_sec"])


def send_file_to_server(addr: str, fpath: str):
    logger.info('###############################')
    data_plain_text = None
    with open(fpath, 'r') as f:
        data = f.read()
        data_plain_text = data.encode('utf8')

    resp = b'NONE'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as clientsocket:
        logger.info('Sending...')
        clientsocket.connect((addr, SERVER_PORT))
        clientsocket.send(data_plain_text)
        logger.info('Sent. Waiting for resp...')
        resp = clientsocket.recv(128)
        logger.info(f'Resp:{resp}')

    resp_str = resp.decode("utf8")
    if 'OK' in resp_str:
        logger.info('OK received :)')
        return True

    logger.info(f'Bad response:{resp_str}')
    return False


def send_reports_loop():
    tosend_dir = 'tosend'
    while True:
        print('send_reports_loop() invoked')
        try:
            cleanup_logs_if_need()

            addr_to_send = get_bot_server_ip()
            for file in sorted(os.listdir(tosend_dir)):
                fpath = os.path.join(tosend_dir, file)
                if not os.path.isdir(fpath) and file != ".DS_Store":
                    logger.info(f'Trying to send {fpath} to {addr_to_send}')
                    try:
                        is_sent_ok = send_file_to_server(addr_to_send, fpath)
                        if is_sent_ok:
                            os.remove(fpath)
                    except Exception as e:
                        logger.error(f'send_reports_loop(), send_file_to_server() level: {e} {traceback.format_exc()}')

        except Exception as e:
            logger.error(f'send_reports_loop() error: {e} {traceback.format_exc()}')

        print(f'send_reports_loop sleep {config["sleep_send_sec"]} sec.')
        time.sleep(config["sleep_send_sec"])


if __name__ == '__main__':
    logger.info('--------------------')
    cleanup_logs_if_need()
    logger.info('Report Client v2 init...')
    check_dirs_files()
    global config
    config = read_config()
    get_bot_server_ip(log_everything=True)
    thread = threading.Thread(target=check_for_reports_loop)
    thread2 = threading.Thread(target=send_reports_loop)
    logger.info('Report Client v2 started :)')
    thread.start()
    thread2.start()