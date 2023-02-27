class StatusCodeError(Exception):
    """Ошибка при недоступности эндпойнта."""

    pass


class NotValidStatus(Exception):
    """Ошибка при невалидном статусе домашней работы."""

    pass
