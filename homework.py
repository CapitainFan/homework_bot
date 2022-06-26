import requests
import telegram
import logging
import time
import os
from logging.handlers import RotatingFileHandler
from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler = RotatingFileHandler(
    os.path.expanduser('~/homework.log'),
    maxBytes=50000000,
    backupCount=5
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info('Бот отправил сообщение: '
                f'{message}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code == HTTPStatus.OK:
        logger.info(
            f'Запрос получен. Статус ответа: {response.status_code}'
        )
        clear_response = response.json()
        if 'error' in clear_response:
            message = clear_response.get('error')
            logger.error(
                f"Ошибка формата ответа сервера {message}"
            )
            raise SystemError('Ошибка формата ответа сервера')
        else:
            return clear_response
    else:
        message = ('Сбой в работе программы: '
                   f'Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа API: {response.status_code}')
        logger.error(message)
        raise response.raise_for_status()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) == dict:
        homeworks = response.get('homeworks')
        if type(homeworks) == list:
            return homeworks
        else:
            error = f'Тип данных {type(homeworks).__name__} не список'
            logger.error(error)
            raise TypeError(error)
    else:
        error = f'Тип данных {type(response).__name__} не словарь'
        logger.error(error)
        raise TypeError(error)


def parse_status(homework):
    """Получает статус конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name:
        homework_status = homework.get('status')
        if homework_status in HOMEWORK_STATUSES.keys():
            verdict = HOMEWORK_STATUSES.get(homework_status)
            message = ('Изменился статус проверки работы '
                       f'"{homework_name}". {verdict}')
            return message
        else:
            error = 'Недокументированный статус домашней работы'
            logger.error(error)
            raise KeyError(error)
    else:
        error = 'Статус домашней работы отсутствует'
        logger.error(error)
        raise KeyError(error)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, token in token_dict.items():
        if not token:
            message = ('Отсутствует обязательная переменная окружения: '
                       f'{name}. Программа принудительно остановлена.')
            logger.critical(message)
            return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                if homeworks:
                    message = parse_status(homeworks[0])
                    current_timestamp = response.get('current_date')
                    if message:
                        logger.debug('Статус домашней работы не изменился')
                    else:
                        send_message(bot, message)
                else:
                    message = 'Домашняя работа не найдена'
                    if message:
                        logger.debug('Статус домашней работы не изменился')
                    else:
                        send_message(bot, message)
                time.sleep(RETRY_TIME)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                time.sleep(RETRY_TIME)
    else:
        error = 'Отсутствует обязательная переменная окружения.'
        logger.critical(error)
        raise NameError(error)


if __name__ == '__main__':
    main()
