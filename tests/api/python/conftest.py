# conftest.py — общие фикстуры API-тестов на Python.
# pytest сам находит этот файл и подключает фикстуры ко всем тестам в папке.

# os — читаем адрес приложения из переменной окружения API_BASE_URL.
import os
# time — паузы между опросами статуса фоновой задачи.
import time

# pytest — тестовый фреймворк: фикстуры, параметризация, проверки assert.
import pytest
# requests — HTTP-клиент: отправляет запросы к API приложения.
import requests

# Адрес приложения: берём из окружения (его задаёт tests/api/env.py), иначе — значение по умолчанию.
BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:3100")
# Сколько секунд ждём завершения фоновой задачи (анализ на тестовых данных идёт несколько секунд).
JOB_TIMEOUT_S = 180


# scope="session" — одна сессия requests на все тесты: соединения переиспользуются.
@pytest.fixture(scope="session")
def api() -> requests.Session:
    # Создаём сессию — объект, который хранит общие настройки запросов.
    session = requests.Session()
    # Каждый запрос ждём не дольше 60 секунд, чтобы зависший сервер не вешал тесты.
    session.request = _with_timeout(session.request, 60)
    # Отдаём сессию тестам; код после yield выполнится, когда все тесты закончатся.
    yield session
    # Закрываем соединения.
    session.close()


def _with_timeout(request_fn, seconds):
    # Обёртка: подставляет timeout во все вызовы, если тест не указал свой.
    def wrapped(method, url, **kwargs):
        # setdefault — не перетирает timeout, если он уже передан.
        kwargs.setdefault("timeout", seconds)
        # Относительные пути («/api/games») превращаем в полный адрес.
        return request_fn(method, url if url.startswith("http") else BASE_URL + url, **kwargs)
    # Возвращаем обёрнутую функцию.
    return wrapped


def wait_job(api: requests.Session, job_id: str) -> dict:
    # Опрашиваем статус фоновой задачи, пока она не перестанет быть «running».
    deadline = time.time() + JOB_TIMEOUT_S
    # Повторяем, пока не вышло время.
    while time.time() < deadline:
        # GET /api/jobs/{id} — текущее состояние задачи.
        job = api.get(f"/api/jobs/{job_id}").json()["job"]
        # Задача закончилась (done, error или cancelled) — возвращаем её.
        if job["status"] != "running":
            return job
        # Иначе ждём полсекунды и спрашиваем снова.
        time.sleep(0.5)
    # Время вышло — тест падает с понятным сообщением.
    pytest.fail(f"Задача {job_id} не завершилась за {JOB_TIMEOUT_S} с")


# Фикстура уровня сессии: анализ 4x20 запускается один раз и нужен нескольким тестам.
@pytest.fixture(scope="session")
def analysis(api) -> dict:
    # Запускаем задачу анализа игры 4x20.
    job = api.post("/api/jobs", json={"kind": "analyze", "game": "4x20"}).json()["job"]
    # Дожидаемся завершения.
    finished = wait_job(api, job["id"])
    # Анализ должен закончиться успешно, иначе дальнейшие проверки бессмысленны.
    assert finished["status"] == "done", finished.get("error")
    # Читаем сохранённый результат анализа.
    return api.get("/api/games/4x20/results", params={"kind": "analysis"}).json()["result"]
