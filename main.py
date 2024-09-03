import base64
import datetime
import os
import random
import requests
import logging
import sys
import json
import threading
import time
import traceback


CONFIG_FILE = "config.json"
LOGS_FILE = "logs.txt"
LOGS_MAX_SIZE_MB = 20
REST_ID_LEN = 8
REP_TITLE_LEN = 25

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


def get_bot_server_addr(log_everything: bool = False) -> str:
    global config
    get_addr_addr = config['get_addr']
    def_addr_addr = config['default_addr']
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
    try:
        resp = requests.get(get_addr_addr, headers=headers)
        recv_addr = resp.text.strip()
        if (len(recv_addr.split('\n')) > 1 or len(recv_addr.split('.')) != 4):
            raise Exception(f'{recv_addr} is not an ip or domain addr.')
        if log_everything:
            logger.info(f'Will use received ip: {recv_addr}')
        return recv_addr
    except Exception as e1:
        err = f'get_bot_server_addr() error while connecting to {get_addr_addr}: {e1}'
        print(err)
        if log_everything:
            logger.error(err)
            logger.error(traceback.format_exc())
            logger.info(f'Will use default_addr: {def_addr_addr}')
        return def_addr_addr


def get_report_by_markers(marker: list, lines: list) -> list:
    rep_lines = []
    print(lines)
    mark_name = marker[0]
    mark_start = marker[1]
    mark_end = marker[2]
    if len(mark_end) == 0:
        mark_end = "$default"

    print(f'Marker start:{mark_start}; Marker end:{mark_end};')
    rep_found = False
    for line in lines:
        line = line.replace('\n', '')
        if not rep_found:   # Если не наткнулись на начало отчета
            if mark_start in line:
                rep_name_line = mark_name
                rep_lines.append(rep_name_line)
                if config['include_markers'] == True:
                    rep_lines.append(line)
                print(f'Found START match in line:{line}')
                rep_found = True
            else:
                print(f'do not match:"{line}"')
        else:   # Если уже читаем отчет
            if mark_end != '$default' and mark_end in line:
                print(f'Found END match in line:{line}')
                if config['include_markers'] == True:
                    rep_lines.append(line)
                break

            rep_lines.append(line)

    # print(f'Ret report:{rep_lines}')
    return rep_lines


def copy_and_delete_original(tmp_name, fpath) -> str:
    print(f'copy_and_delete_original() called:{fpath}')
    path_orig_copy = os.path.join('deleted', tmp_name)
    open(path_orig_copy, 'wb').write(open(fpath, 'rb').read())  # Copy
    os.remove(fpath)


def save_report_tosend_folder(tmp_name, rep_lines: list):
    rep_plain_text = '\n'.join([i for i in rep_lines[0:]])
    path = os.path.join('tosend', f'{tmp_name}.txt')
    logger.info(f'Following data prepared for sending:\n{rep_plain_text}')
    with open(path, 'w') as f:
        f.write(rep_plain_text)

def get_letter(pos: int):
    letters = 'abcdefghlmn'
    ret = ''
    for let in list(str(pos)):
        ret += letters[int(let):int(let)+1]
    return ret

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
                report_found = False
                lines = None
                tmp_name = f'rep{random.randint(0, 9999999)}'
                print(f'Reading file {file}')
                with open(file, 'r') as f:
                    lines = f.readlines()
                    #lines = data.split('\n')
                i = 0
                for marker in config['markers']:
                    print('------------------------')
                    print(f'Current marker {marker}')
                    report_lines = get_report_by_markers(marker, lines)
                    if len(report_lines) > 0:
                        report_found = True
                        tmp_name_rep = tmp_name + '-' + get_letter(i)
                        save_report_tosend_folder(tmp_name_rep, report_lines)
                    else:
                        print('Report not found')
                    i += 1
                if report_found:
                    logger.info(f'Report(s) found in {file}, will copy it to {tmp_name} and delete.')
                    copy_and_delete_original(tmp_name, file)

        except Exception as e:
            logger.error(f'check_for_reports_loop() error: {e} {traceback.format_exc()}')

        print(f'check_for_reports_loop sleep {config["sleep_parse_sec"]} sec.')
        time.sleep(config["sleep_parse_sec"])

def encode_key(str):
    string_bytes = str.encode("ascii")
    base64_bytes = base64.b64encode(string_bytes)
    base64_string = base64_bytes.decode("ascii")
    return base64_string


def send_file_to_server(addr: str, fpath: str):
    logger.info('###############################')
    data_plain_text = None
    with open(fpath, 'r') as f:
        data = f.read()

    nl_pos = data.find('\n')
    rep_title = data[0:nl_pos]
    rep_data = data[data.find('\n'):]
    json_data = {
        "rest_id": config["restaurant_id"],
        "rep_title": rep_title,
        "rep_text": rep_data
    }
    resp = requests.post(addr + '/send_rep', json = json_data)
    resp_text = resp.text.strip()
    logger.info(f'Resp:{resp_text}')
    if resp.ok:
        logger.info('OK received :)')
        return True

    logger.info(f'Bad response:{resp_text}')
    return False


def send_reports_loop():
    tosend_dir = 'tosend'
    while True:
        print('send_reports_loop() invoked')
        try:
            cleanup_logs_if_need()

            addr_to_send = get_bot_server_addr()
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
    get_bot_server_addr(log_everything=True)
    thread = threading.Thread(target=check_for_reports_loop)
    thread2 = threading.Thread(target=send_reports_loop)
    logger.info('Report Client v2 started :)')
    thread.start()
    thread2.start()