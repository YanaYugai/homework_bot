import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict, List

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

import exceptions

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens() -> bool:
    """Проверка наличия переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка собщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено')
    except TelegramError as telegram_error:
        logger.error(f'{telegram_error}. Невозможно отправить сообщение!')


def get_api_answer(timestamp: int) -> Dict[str, List[Dict[str, int]]]:
    """Делает запрос к API Яндекс Практикума."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if response.status_code != HTTPStatus.OK:
            raise exceptions.StatusCodeError('Недоступность эндпоинта')
        response = response.json()
        return response
    except requests.RequestException as request_error:
        logger.error(request_error)


def check_response(
        response: Dict[
        str,
        List[Dict[str, int]],
        ]) -> List[Dict[str, int]]:
    """Проверка ответа API на тип данных."""
    try:
        homework = response['homeworks']
    except KeyError as key_error:
        raise KeyError(f'{key_error}. Неправильный ключ или ключ отсутствует.')
    if not isinstance(homework, list):
        raise TypeError(
            f'Неправильный тип данных ответа API: {type(homework)}',
        )
    return homework


def parse_status(homework: List[Dict[str, int]]) -> str:
    """Извлекает статус домашней работы."""
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise exceptions.NotValidStatus(
            'Неправильный статус домашки или статус отсутствует',
        )
    verdict = HOMEWORK_VERDICTS[status]
    try:
        homework_name = homework['homework_name']
    except KeyError as hm_name_key_error:
        raise KeyError(f'{hm_name_key_error}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    status_current = ''
    current_error = ''
    if check_tokens():
        while True:
            try:
                response = get_api_answer(timestamp)
                print(response)
                homework = check_response(response)
                print(homework)
                homework = homework[0]
                message = parse_status(homework)
                if message != status_current:
                    send_message(bot, message)
                    status_current = message
                current_error = ''
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                logging.error(error)
                if str(error) != current_error:
                    message = f'Сбой в работе программы: {error}'
                    send_message(bot, message)
                time.sleep(RETRY_PERIOD)
    else:
        logger.critical('Отсутствуют перенные окружения!')


if __name__ == '__main__':
    main()
