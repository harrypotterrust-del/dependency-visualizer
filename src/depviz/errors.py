"""Исключения программы и оформление места ошибки."""

from typing import Iterable, List, Optional


class ConfigError(Exception):
    """Ошибка конфигурации: одно или несколько сообщений для пользователя.

    Сообщения хранятся списком ``messages`` - по одному на проблему,
    поэтому программа показывает все ошибки файла за один запуск.
    """

    def __init__(self, messages: Iterable[str]) -> None:
        """Сохранить сообщения ``messages`` об ошибках."""
        self.messages: List[str] = list(messages)
        super().__init__("\n".join(self.messages))


def location(path: str, line: Optional[int] = None) -> str:
    """Вернуть место ошибки: файл и, если известна, номер строки."""
    if line is None:
        return path
    return f"{path}, строка {line}"
