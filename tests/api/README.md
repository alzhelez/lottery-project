# API-автотесты: Python, Go, Java

Одни и те же 14 сценариев (API-01…API-14) написаны на трёх языках. Каждая строка кода
прокомментирована: что делает и зачем, — тесты можно читать как учебник.

| Язык | Стек | Папка | Отчёт Allure |
|---|---|---|---|
| Python | pytest + requests + allure-pytest | `python/` | `allure-results/api-python` |
| Go | стандартный `testing` + `net/http` (без зависимостей) | `go/` | `allure-results/api-go` (JUnit XML) |
| Java | TestNG + REST Assured + AssertJ + Allure | `java/` | `allure-results/api-java` |

## Тестовое окружение

Тесты ходят в настоящее приложение (Next.js) и настоящий движок (Python), но вместо
stoloto.ru — локальный мок `tests/mock_stoloto/server.py`. Ваши данные (`data/`) не
затрагиваются: окружение работает с отдельной папкой `tests/api/.data`, Telegram в нём
отключён.

```
python tests/api/env.py start    # мок на :3199, загрузка 1500 тиражей, приложение на :3100
python tests/api/env.py stop     # остановить
python tests/api/env.py run -- <команда>   # поднять, выполнить команду, остановить
```

Перед первым запуском приложение должно быть собрано: `npm run build`.
Адрес приложения для тестов можно поменять переменной `API_BASE_URL`
(для Java ещё и `mvn test -Dapi.baseUrl=...`).

## Запуск

Из корня проекта, когда окружение поднято (`npm run test:api:env`):

| Что | Команда | Нужно установить |
|---|---|---|
| Python | `npm run test:api:py` | `pip install -r python/requirements-dev.txt` |
| Go | `npm run test:api:go` | Go 1.22+ |
| Java | `npm run test:api:java` | JDK 17+ и Maven 3.9+ |
| Всё сразу, с подъёмом окружения | `npm run test:api` (Python) | |
| Отчёт | `npm run allure:report`, затем `npm run allure:open` | |

То же без npm, по папкам:

```
cd tests/api/python && python -m pytest --alluredir=../../../allure-results/api-python
cd tests/api/go     && go test -v ./...
cd tests/api/java   && mvn test
```

### Windows

```
setup.bat                         :: один раз — зависимости
npm run build
npm run test:api:env              :: окно можно не закрывать — окружение работает в фоне
npm run test:api:py
npm run test:api:go
npm run test:api:java
npm run test:api:env:stop
```

Go и Maven ставятся отдельно: <https://go.dev/dl/>, <https://maven.apache.org/download.cgi>
(или `winget install GoLang.Go` и `winget install Apache.Maven`).

### Как Go попадает в Allure

`go test` не умеет писать результаты Allure, поэтому `go test -json` передаётся маленькой
утилите `go/cmd/gojunit`: она переводит события в JUnit XML, а названия тестов берёт из
комментариев над функциями (`// TestAPI01GamesList — список игр: …` → «API-01. Список игр: …»).
Allure читает JUnit XML сам. Утилита возвращает код 1, если хоть один тест упал.

## Сценарии

| № | Что проверяем | Запросы |
|---|---|---|
| API-01 | Список игр: у 4 из 20 1500 тиражей, номер следующего = последний + 1, игра активна, версия вида `40.3.0_ДДММГГГГ` | `GET /api/games` |
| API-02 | Карточка игры: ссылка `https://www.stoloto.ru/4x20/game/`, тиражи без пропусков, дата `ДД.ММ.ГГГГ ЧЧ:ММ` | `GET /api/games/4x20` |
| API-03 | Несуществующая игра и попытка выйти из папки данных (`..%2Fetc`) — 404 | `GET /api/games/{slug}` |
| API-04 | Запуск задачи с ошибками (без игры, неизвестный тип, недопустимое имя, бюджет 0 и 481 мин, не JSON) — 400 с понятным текстом | `POST /api/jobs` |
| API-05 | Анализ: повторный запуск не создаёт вторую задачу, задача завершается, в отчёте базовая линия 1,6 совпадения, контрольный случайный метод, прогноз из 2×4 разных чисел и оценка в рублях по выплатам из архива | `POST /api/jobs`, `GET /api/jobs/{id}`, `GET /api/games/4x20/results` |
| API-06 | Несуществующая задача — 404 | `GET /api/jobs/{id}` |
| API-07 | После анализа прогноз записан в журнал до тиража (ожидает проверки) | `GET /api/games/4x20/journal` |
| API-08 | Шансы: вероятность выигрыша считается точно, выплаты берутся из архива тиражей, свои призы сохраняются и сбрасываются | `GET/PUT /api/games/4x20/odds` |
| API-09 | Генератор билетов: 3 билета по 4 разных числа в поле; проверка комбинации 1-2-3-4 находит «ряд подряд»; неверные запросы — 400 | `POST /api/games/4x20/tickets` |
| API-10 | Экспорт: Excel (zip, «PK»), CSV с BOM и заголовками через «;», неизвестный формат — 400, журнала нет — 404 | `GET /api/games/{slug}/export` |
| API-11 | Шансы всех игр: у бинго калькулятора нет | `GET /api/odds` |
| API-12 | Статус автозапуска: ровно поля `status` и `running` | `GET /api/auto` |
| API-13 | Telegram в тестовом окружении не настроен | `GET /api/telegram` |
| API-14 | Неизвестный вид отчёта — 400 | `GET /api/games/4x20/results?kind=secret` |

Сценарии зависят друг от друга только через общий анализ (API-05 → API-07): анализ
запускается один раз на прогон (фикстура `analysis` в Python, `sync.Once` в Go,
`BaseApiTest.analysis()` в Java). Наборы можно гонять подряд на одном окружении —
тесты, меняющие данные (свои призы в API-08), возвращают всё как было.
