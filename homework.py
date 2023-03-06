import logging.config
import os
import time
from functools import wraps
from http import HTTPStatus
from typing import Dict, List, Callable

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600  # 10 минут в секундах
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def func_logger(func: Callable) -> Callable:
    """Логгирование запуска функции.

    Args:
        func (Callable): Декорируемая функция.

    Returns:
        Возвращает функцию-обретку.

    """

    @wraps(func)
    def inner(*args, **kwargs):
        logging.info('Успешное выполнение: %s', func.__name__)
        return func(*args, **kwargs)

    return inner


def check_tokens() -> bool:
    """Проверка наличия переменных окружения.

    Returns:
        bool: Возвращаемое зачение. True - функция сработала удачно,
        иначе False.

    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


@func_logger
def send_message(bot: telegram.Bot, text: str) -> None:
    """Отправка собщения в Telegram-чат.

    Args:
        bot (telegram.Bot): используемый бот для отправки сообщения.
        text (str): поссылаемое сообщение, которое содержит статус проеврки.

    Raises:
        TelegramError: Все ошибки, связанные с Telegram.

    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except telegram.TelegramError:
        logging.exception('Невозможно отправить соощение: %s', text)
        raise telegram.TelegramError
    logging.debug('Сообщение отправлено')


def get_api_answer(timestamp: int) -> Dict[str, List[Dict[str, int]]]:
    """Делает запрос к API Яндекс Практикума.

    Args:
        timestamp (int): Задает текущее время.

    Returns:
        Dict: Вощвращает ответ API, приведенный к типам данных Python.

    Raises:
        StatusCodeError: Ошибка, вызванная, если статусе ответа не 200.

    """
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
    except requests.RequestException:
        logging.exception('request_error')
    if response.status_code != HTTPStatus.OK:
        raise exceptions.StatusCodeError('Недоступность эндпоинта')
    return response.json()


def check_response(
    response: Dict[
        str,
        List[Dict[str, int]],
    ],
) -> List[Dict[str, int]]:
    """Проверка ответа API на тип данных.

    Args:
        response (Dict): Ответ API, приведенный к типам данных Python.

    Returns:
        List: Список из ответа API, содержащий информацию о домашних работах.

    Raises:
        TypeError: Ошибка, вызванная, при неправильнном типе данных.

    """
    if (
        isinstance(response, dict)
        and all(key in response for key in ('current_date', 'homeworks'))
        and isinstance(response['homeworks'], list)
    ):
        return response['homeworks']
    raise TypeError


def parse_status(homework: List[Dict[str, int]]) -> str:
    """Извлекает статус домашней работы.

    Args:
        homework (List): Список из ответа API,
                содержащий информацию о домашних работах.

    Returns:
        str: Сообщение о статусе работы.

    Raises:
        NotValidStatus: Невалидный статус домашней работы.
        KeyError: неправильный ключ иои его отсутствие.

    """
    try:
        homework_name, status = homework['homework_name'], homework['status']
    except KeyError as hm_name_key_error:
        raise KeyError(f'{hm_name_key_error}')
    if status not in HOMEWORK_VERDICTS:
        raise exceptions.NotValidStatus(
            'Неправильный статус домашки или статус отсутствует',
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def get_message(response: Dict[str, List[Dict[str, int]]]) -> str:
    """Извлекает сообщение о статусе домашней работы.

    Args:
        response (Dict): Ответ API, приведенный к типам данных Python.

    Returns:
        str: Сообщение о статусе работы.

    """
    homework = check_response(response)
    homework = homework[0]
    return parse_status(homework)


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    logging.debug('OK')
    status_current = ''
    current_error = ''
    if check_tokens():
        while True:
            response = get_api_answer(timestamp)
            try:
                message = get_message(response)
            except Exception as error:
                logging.error(error)
                if str(error) != current_error:
                    message = f'Сбой в работе программы: {error}'
            if message != status_current:
                status_current = message
                current_error = ''
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
    else:
        logging.critical('Отсутствуют перенные окружения!')


if __name__ == '__main__':
    logging.config.fileConfig(
        fname='logger.conf',
        disable_existing_loggers=False,
    )
    logging.getLogger()
    main()
