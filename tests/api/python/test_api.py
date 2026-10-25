# test_api.py — API-автотесты приложения на Python (pytest + requests + Allure).
# Набор сценариев API-01…API-15 одинаков для Java, Python и Go (см. tests/api/README.md).
# Перед запуском нужно окружение: python tests/api/env.py start

# math.comb — число сочетаний: из него считаем точный шанс главного приза.
from math import comb

# allure — разметка для отчёта: раздел, название, шаги.
import allure
# pytest — параметризация и фикстуры.
import pytest

# wait_job — ожидание фоновой задачи (описан в conftest.py).
from conftest import wait_job

# Все тесты файла попадают в раздел «API (Python)» отчёта Allure.
pytestmark = [allure.epic("API (Python)")]


@allure.feature("Игры")
@allure.title("API-01. Список игр: 4 из 20 с тиражами и номером следующего тиража")
def test_games_list(api):
    # Отправляем GET /api/games.
    response = api.get("/api/games")
    # Сервер должен ответить 200 OK.
    assert response.status_code == 200
    # Разбираем тело ответа как JSON.
    body = response.json()
    # Версия имеет вид 40.3.0_ДДММГГГГ: три числа через точку, подчёркивание и дата.
    assert body["version"].count(".") == 2 and "_" in body["version"]
    # Находим в списке игру 4x20 (next вернёт первую подходящую или None).
    game = next((g for g in body["games"] if g["slug"] == "4x20"), None)
    # Игра должна быть в списке.
    assert game is not None
    # Мок отдаёт 1500 тиражей 4x20.
    assert game["draws"] == 1500
    # Следующий тираж — последний номер плюс один.
    assert game["nextNo"] == game["last"]["no"] + 1
    # Мок сдвигает даты так, что последний тираж был вчера, — игра активна.
    assert game["activity"]["active"] is True


@allure.feature("Игры")
@allure.title("API-02. Карточка игры: ссылка на stoloto.ru, количество тиражей, период")
def test_game_card(api):
    # GET /api/games/4x20 — сведения об одной игре.
    game = api.get("/api/games/4x20").json()
    # Ссылка на страницу игры строится по шаблону https://www.stoloto.ru/<игра>/game/.
    assert game["stolotoUrl"] == "https://www.stoloto.ru/4x20/game/"
    # Тиражей в архиве 1500, пропусков нет.
    assert (game["draws"], game["missing"]) == (1500, 0)
    # Первый и последний номер: всего ровно 1500 номеров подряд.
    assert game["last"]["no"] - game["first"]["no"] + 1 == 1500
    # Дата в формате ДД.ММ.ГГГГ ЧЧ:ММ — 16 символов, точки на позициях 2 и 5.
    assert len(game["first"]["date"]) == 16 and game["first"]["date"][2] == "."


@allure.feature("Игры")
@allure.title("API-03. Несуществующая и недопустимая игра — 404")
# parametrize — один тест прогоняется для каждого значения из списка.
@pytest.mark.parametrize("slug", ["nope-game", "..%2Fetc"])
def test_unknown_game(api, slug):
    # Запрашиваем игру, которой нет (или имя с попыткой выйти из папки).
    response = api.get(f"/api/games/{slug}")
    # В обоих случаях — 404 Not Found.
    assert response.status_code == 404


@allure.feature("Фоновые задачи")
@allure.title("API-04. Запуск задачи: некорректные запросы отклоняются с 400")
@pytest.mark.parametrize("payload, error", [
    # Неизвестный тип задачи.
    ({"kind": "rm", "game": "4x20"}, "Неизвестный тип задачи"),
    # Анализ без игры.
    ({"kind": "analyze"}, "Не указана игра"),
    # Имя игры с попыткой выйти из папки.
    ({"kind": "analyze", "game": "../x"}, "Недопустимое имя игры"),
    # Бюджет режима Бога меньше минуты.
    ({"kind": "godmode", "game": "4x20", "budget": 0}, "Бюджет"),
    # Бюджет больше 8 часов (480 минут).
    ({"kind": "godmode", "game": "4x20", "budget": 481}, "Бюджет"),
])
def test_job_validation(api, payload, error):
    # POST /api/jobs с некорректным телом.
    response = api.post("/api/jobs", json=payload)
    # Ожидаем 400 Bad Request.
    assert response.status_code == 400
    # Текст ошибки объясняет, что не так.
    assert error in response.json()["error"]


@allure.feature("Фоновые задачи")
@allure.title("API-04. Тело запроса не JSON — 400")
def test_job_not_json(api):
    # Отправляем строку, а не JSON, но с заголовком application/json.
    response = api.post("/api/jobs", data="not json", headers={"content-type": "application/json"})
    # Сервер должен ответить 400 и сообщить, что ждёт JSON.
    assert response.status_code == 400 and response.json()["error"] == "Ожидается JSON"


@allure.feature("Фоновые задачи")
@allure.title("API-05. Анализ: задача не дублируется, завершается, результат корректен")
def test_analysis_job(api, analysis):
    # Фикстура analysis уже дождалась одного анализа; теперь проверяем защиту от дублей.
    with allure.step("Повторный запуск во время работы возвращает ту же задачу"):
        # Запускаем анализ ещё раз.
        first = api.post("/api/jobs", json={"kind": "analyze", "game": "4x20"}).json()["job"]
        # …и сразу ещё раз, пока первая ещё идёт.
        second = api.post("/api/jobs", json={"kind": "analyze", "game": "4x20"}).json()["job"]
        # Сервер не запускает вторую копию: id совпадают.
        assert first["id"] == second["id"]
        # Дожидаемся завершения, чтобы не мешать следующим тестам.
        assert wait_job(api, first["id"])["status"] == "done"
    with allure.step("Проверяем сохранённый результат анализа"):
        # Отчёт построен по последнему тиражу из архива.
        assert analysis["last_draw_no"] == 13896
        # Сравнение методов прошло (данных достаточно).
        evaluation = analysis["evaluation"]
        assert evaluation["status"] == "ok"
        # Ожидание случайного выбора в 4 из 20: 4·4/20 на каждое поле, сумма 1,6.
        assert abs(evaluation["baseline"]["mean"] - 1.6) < 1e-9
        # Среди методов есть контрольный — случайный выбор.
        assert any(m["control"] for m in evaluation["models"])
        # Прогноз на следующий тираж: два поля по 4 разных числа от 1 до 20.
        for block in evaluation["next_prediction"]["numbers"]:
            assert len(set(block)) == 4 and all(1 <= v <= 20 for v in block)
    with allure.step("Оценка в рублях по выплатам из архива"):
        # Мок отдаёт таблицы выплат и цену билета 150 ₽.
        money = evaluation["money"]
        assert money["available"] and money["price"] == 150


@allure.feature("Фоновые задачи")
@allure.title("API-06. Несуществующая задача — 404")
def test_unknown_job(api):
    # GET по выдуманному id.
    response = api.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    # Задачи нет — 404 и понятное сообщение.
    assert response.status_code == 404 and response.json()["error"] == "Задача не найдена"


@allure.feature("Журнал прогнозов")
@allure.title("API-07. После анализа прогноз записан в журнал до тиража")
def test_journal_after_analysis(api, analysis):
    # GET /api/games/4x20/journal — записи журнала и итоги.
    journal = api.get("/api/games/4x20/journal").json()
    # Берём записи на следующий тираж.
    upcoming = [e for e in journal["entries"] if e["draw_no"] == analysis["last_draw_no"] + 1]
    # Анализ пишет два прогноза: лучшего метода и консенсуса.
    assert {"analysis_best", "analysis_consensus"} <= {e["source"] for e in upcoming}
    # Тираж ещё не сыгран — записи ждут сверки.
    assert all(e["status"] == "pending" for e in upcoming)


@allure.feature("Шансы")
@allure.title("API-08. Шансы: точная вероятность, выплаты из архива, свои призы")
def test_odds(api):
    with allure.step("Точная вероятность главного приза"):
        # GET /api/games/4x20/odds.
        odds = api.get("/api/games/4x20/odds").json()["odds"]
        # 4+4 — угадать оба поля: 1 из C(20,4)² = 23 474 025.
        assert round(odds["jackpot"]["one_in"]) == comb(20, 4) ** 2
        # Сумма вероятностей всех исходов — 1.
        assert abs(sum(p["p"] for p in odds["patterns"]) - 1) < 1e-12
    with allure.step("Без своих данных используется официальная таблица выигрышей"):
        # Сбрасываем свои призы, если их ввёл другой набор тестов.
        api.put("/api/games/4x20/odds", json={"price": None, "prizes": {}})
        odds = api.get("/api/games/4x20/odds").json()["odds"]
        # Находим исход 2+2.
        row = next(p for p in odds["patterns"] if p["key"] == "2+2")
        # 2+2 — 300 ₽ по таблице выигрышей тиража (загружается вместе с тиражами);
        # она важнее медианы архива.
        assert row["prize"] == 300 and row["prize_source"] == "rules"
        # Цена билета тоже из архива.
        assert odds["price"] == 150 and odds["price_source"] == "archive"
    with allure.step("Свои призы важнее архива, лишние ключи отбрасываются"):
        # PUT: своя цена и приз за 2+2, плюс мусорный ключ.
        odds = api.put("/api/games/4x20/odds",
                       json={"price": 200, "prizes": {"2+2": 500, "bad key": 1}}).json()["odds"]
        row = next(p for p in odds["patterns"] if p["key"] == "2+2")
        # Своя сумма заменила архивную.
        assert row["prize"] == 500 and row["prize_source"] == "user"
        # Своя цена используется в расчёте возврата.
        assert odds["price"] == 200 and odds["price_source"] == "user"
        # Возврат с рубля — ожидаемый выигрыш, делённый на цену.
        assert abs(odds["return_per_ruble"] - odds["expected_value"] / 200) < 1e-12
    # Возвращаем исходное состояние, чтобы не влиять на другие наборы тестов.
    api.put("/api/games/4x20/odds", json={"price": None, "prizes": {}})


@allure.feature("Билеты")
@allure.title("API-09. Генератор билетов и проверка своей комбинации")
def test_tickets(api):
    with allure.step("Генерация трёх билетов"):
        # POST /api/games/4x20/tickets c количеством билетов.
        body = api.post("/api/games/4x20/tickets", json={"count": 3}).json()["tickets"]
        # Получили ровно три билета.
        assert len(body["tickets"]) == 3
        # В каждом поле — 4 разных числа от 1 до 20.
        for ticket in body["tickets"]:
            for block in ticket["blocks"]:
                assert len(set(block)) == 4 and all(1 <= v <= 20 for v in block)
    with allure.step("Проверка популярной комбинации"):
        # Ряд 1, 2, 3, 4 — типичный «популярный» выбор.
        check = api.post("/api/games/4x20/tickets", json={"check": "1,2,3,4|5,6,7,8"}).json()["check"]
        # Комбинация распознана как корректная…
        assert check["valid"] is True
        # …и у неё есть признаки популярности (ряд подряд).
        codes = {f["code"] for b in check["blocks"] for f in b["flags"]}
        assert "runs" in codes
    with allure.step("Некорректные запросы"):
        # 0 билетов, 51 билет и буквы в комбинации — всё 400.
        for payload in ({"count": 0}, {"count": 51}, {"check": "a,b,c"}):
            assert api.post("/api/games/4x20/tickets", json=payload).status_code == 400


@allure.feature("Экспорт")
@allure.title("API-10. Экспорт в Excel и CSV")
def test_export(api):
    with allure.step("Excel"):
        # GET экспорта всех таблиц в xlsx.
        response = api.get("/api/games/4x20/export", params={"format": "xlsx"})
        # Тип файла — таблица Excel.
        assert "spreadsheetml" in response.headers["content-type"]
        # Файл xlsx — это zip-архив, он начинается с байтов «PK».
        assert response.content[:2] == b"PK"
    with allure.step("CSV тиражей"):
        response = api.get("/api/games/4x20/export", params={"format": "csv", "what": "draws"})
        # В начале — BOM (метка UTF-8), чтобы Excel правильно показал кириллицу.
        assert response.content.startswith(b"\xef\xbb\xbf")
        # Первая строка — заголовки через точку с запятой.
        header = response.content.decode("utf-8-sig").splitlines()[0]
        assert header == "Тираж;Дата;Поле 1;Поле 2"
        # Имя файла подсказывается браузеру через Content-Disposition.
        assert 'filename="4x20_draws.csv"' in response.headers["content-disposition"]
    with allure.step("Ошибки"):
        # Неизвестный формат — 400.
        assert api.get("/api/games/4x20/export", params={"format": "pdf"}).status_code == 400
        # Журнала у устаревшей игры нет — 404.
        assert api.get("/api/games/duel/export", params={"format": "csv", "what": "journal"}).status_code == 404


@allure.feature("Шансы")
@allure.title("API-11. Шансы всех игр: игр без выбора чисел нет в списке")
def test_odds_all_games(api):
    # GET /api/odds — шансы по всем играм с тиражами.
    odds = api.get("/api/odds").json()["odds"]
    # Для 4 из 20 калькулятор работает.
    assert odds["4x20"]["supported"] is True
    # Русское лото (бинго: числа не выбираются) убрано из программы — его нет в списке.
    assert "ruslotto" not in odds


@allure.feature("Сервис")
@allure.title("API-12. Статус автозапуска")
def test_auto_status(api):
    # GET /api/auto.
    body = api.get("/api/auto").json()
    # В ответе есть статус последнего цикла и признак «идёт сейчас».
    assert set(body) == {"status", "running"} and isinstance(body["running"], bool)


@allure.feature("Сервис")
@allure.title("API-13. Telegram в тестовом окружении не настроен")
def test_telegram_status(api):
    # GET /api/telegram.
    body = api.get("/api/telegram").json()
    # Токена и чата нет — уведомления выключены.
    assert body["configured"] is False and body["has_token"] is False


@allure.feature("Сервис")
@allure.title("API-14. Результаты: неизвестный вид отчёта — 400")
def test_results_bad_kind(api):
    # kind может быть только analysis или godmode.
    response = api.get("/api/games/4x20/results", params={"kind": "secret"})
    # Иначе — 400 и сообщение об ошибке.
    assert response.status_code == 400 and response.json()["error"] == "Неверный запрос"


@allure.feature("Мои билеты")
@allure.title("API-15. Мои билеты: сверка с тиражом, итог, неверные запросы, удаление")
def test_my_tickets(api):
    with allure.step("Билет на последний загруженный тираж сверяется сразу"):
        # Номер последнего тиража 4 из 20 — из списка игр.
        last = next(g for g in api.get("/api/games").json()["games"] if g["slug"] == "4x20")["last"]["no"]
        # POST /api/my-tickets: игра, числа двух полей, тираж и цена.
        response = api.post("/api/my-tickets", json={"game": "4x20", "numbers": "1,2,3,4|5,6,7,8",
                                                      "draw_no": last, "price": 150})
        # Билет принят.
        assert response.status_code == 200
        # Одна строка — тираж уже сыгран, поэтому статус «сверен» и угадано по каждому полю.
        ticket = response.json()["added"][0]
        assert ticket["status"] == "checked" and len(ticket["hits_by_block"]) == 2 and ticket["price"] == 150
    with allure.step("Итог по игре"):
        # GET /api/my-tickets?game=4x20 — билеты, итог и данные для формы.
        body = api.get("/api/my-tickets", params={"game": "4x20"}).json()
        # Потрачено не меньше цены нашего билета; ближайший тираж — после последнего.
        assert body["summary"]["checked"] >= 1 and body["summary"]["spent"] >= 150
        assert body["form"]["next_no"] > last
    with allure.step("Неверные запросы — 400"):
        # Три числа вместо четырёх, буквы, чужая папка.
        for payload in ({"game": "4x20", "numbers": "1,2,3"}, {"game": "4x20", "numbers": "a,b"},
                        {"game": "../etc", "numbers": "1"}):
            assert api.post("/api/my-tickets", json=payload).status_code == 400
    with allure.step("Удаление"):
        # DELETE по игре и номеру билета — 200, повторно — 400 (билета уже нет).
        params = {"game": "4x20", "id": ticket["id"]}
        assert api.delete("/api/my-tickets", params=params).status_code == 200
        assert api.delete("/api/my-tickets", params=params).status_code == 400
