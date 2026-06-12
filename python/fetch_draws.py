"""
Скрипт для выгрузки архива тиражей лотереи с сайта stoloto.ru

Использование:
    # Автоопределение даты первого тиража:
    python fetch_draws.py --game 6x45plus

    # С явным указанием даты старта:
    python fetch_draws.py --game 6x45plus --date_from 23.03.2026

    # С указанием имени выходного файла:
    python fetch_draws.py --game 4x20 --output my_draws.txt

Если файл уже существует — скрипт:
    1. Читает его и проверяет дубликаты (по номеру тиража)
    2. Ищет пропуски в нумерации тиражей и добирает их из API
    3. Дозаписывает новые тиражи (от последнего в файле до сегодня)
    4. Проверяет, нет ли ранних тиражей (если первый № > 50)
    5. Проверяет общее количество тиражей на разумность
    6. Сохраняет итоговый файл, отсортированный по номеру тиража
"""

import os
import argparse
import time
from datetime import datetime, timedelta

import requests

# Отключаем системный прокси для прямого доступа к stoloto.ru
for _pv in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(_pv, None)

# ── Заголовки запроса ────────────────────────────────────────────────────────

HEADERS = {
    "accept": "*/*",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/x-www-form-urlencoded",
    "device-platform": "DESKTOP",
    "device-type": "STOLOTO",
    "gosloto-partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
    "gosloto-token": "7ec1530511-3a8b64-498989-81db45-c10b0c6087d137",
    "priority": "u=1, i",
    "referer": "https://www.stoloto.ru/4x20/archive",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Cookie": (
        "_ym_uid=1731078587485748013; adtech_uid=87ae6a7f-3ae5-4195-bb98-7a49ba9eaaa6%3Astoloto.ru; "
        "_ymab_param=6wGSQE-s32z_tMo3HA6UjPNiT6ulXNfWqiU30uOLCsxhi8fNxUyxSXz8_dZrGz87bEUm1B7PtWg6LjtXlN3leFbVBjw; "
        "gosloto_locale=ru; tmr_lvid=4b8b864dc9bb4d37d4343a3d2e4a4b4f; tmr_lvidTS=1731078587210; "
        "top100_id=t1.7713245.978499241.1747042076309; adrcid=ARuE7Tz1zVfGvRN1XfkkoVQ; "
        "afUserId=a98cf891-74af-4baf-9f3f-5ab84bacfaa2-p; "
        "_ga_W13573SET9=GS2.1.s1749551363^$o22^$g1^$t1749551550^$j60^$l0^$h0; "
        "_ga=GA1.2.1294189559.1747042075; uxs_uid=7b10e4d0-50db-11f0-9ad9-5d564e3ee5b7; "
        "_ym_d=1763556109; gnezdo_uid=XV9maWV0rL8gUam5TX9xAg==; "
        "wimhash21=f32d6ac13aeece632868c9ea1407709a; isgua=false; "
        "flocktory-uuid=3a3f7975-ae58-497f-b422-52e4d9812a50-6; K=1766490696331; "
        "advcake_track_id=8e8f99f4-4b42-e976-24cf-be499e97f29f; "
        "advcake_session_id=332c2242-56d6-d2a9-1a06-470fa130db66; "
        "ga=7ec1530511-3a8b64-498989-81db45-c10b0c6087d137; accept_cookies=true; "
        "stlt_clientids=ymcid1731078587485748013|uid2869640593; stlt_referral=www.google.com; "
        "fingerprint=3766476886; AF_SYNC=1771064863869; isBroadcastingShow=false; "
        "adrdel=1771379254911; _ym_isad=2; "
        "acs_3=%7B%22hash%22%3A%221aa3f9523ee6c2690cb34fc702d4143056487c0d%22%2C%22nst%22%3A1771501774307%2C%22sl%22%3A%7B%22224%22%3A1771415374307%2C%221228%22%3A1771415374307%7D%7D; "
        "domain_sid=6R-rOAjRiuErAMJuYNb1Q%3A1771415375422; fingerprint=3887095574; "
        "tmr_detect=0%7C1771420327589"
    ),
}

BASE_URL        = "https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive"
PAGE_SIZE       = 50
DATE_WINDOW_DAYS = 365
SEARCH_EPOCH    = datetime(2009, 1, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════

def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def fmt_datetime(iso_str: str) -> str:
    """'2026-04-10T15:30:00.000+03:00'  →  '10.04.2026 15:30'"""
    try:
        dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_str


def parse_file_date(date_str: str) -> datetime:
    """'10.04.2026 15:30'  →  datetime"""
    return datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")


# Game format hints: (block1_count, block2_count)
# For games with dict structured: (count_from_played, count_from_notPlayed or 0)
GAME_FORMAT_HINTS = {
    '4x20': (4, 4),
    '4x20plus': (4, 1),
    '6x45plus': (6, 1),
    '6x45': (6, 0),
    '5x36plus': (5, 1),
    '5x36': (5, 0),
    '5x2': (5, 2),
    '7x49': (7, 0),
    '6x36': (6, 0),
    '6x49': (6, 0),
    '6x49plus': (6, 1),
    'rapido': (8, 1),
    'top3': (3, 0),
    'keno2': (20, 1),
    'keno': (20, 0),
    'zabeg': (6, 0),
    'zabegalochka': (6, 0),
    'duel': (6, 0),
    '12x24': (12, 0),
    'bingo75': (15, 0),
    # --- Additional games from stoloto API ---
    # 'klava' removed: game no longer exists (redirects to 5x36plus)
    'rapido2': (8, 1),
    'rapido-ultra': (8, 1),
    'rapido-drive': (8, 1),
    'nards-pro': (0, 0),   # dict format (played/notPlayed)
    'nards-start': (0, 0),  # dict format
    'nards-drive': (0, 0),  # dict format
    'nards-ultra': (0, 0),  # dict format
    'football-gold': (0, 0),     # dict format
    'football-silver': (0, 0),   # dict format
    'football-bronze': (0, 0),   # dict format
    'football-brilliant': (0, 0), # dict format
    '5x36lite': (5, 0),
    '5x36lite2': (5, 0),
    'fzp': (0, 0),       # dict format (notPlayed only)
    'gzhl': (0, 0),      # dict format (notPlayed only)
    'lovi_moment': (0, 0),
    'ruslotto': (0, 0),  # dict format (notPlayed only)
    'dvazhdydva': (4, 0),
    'oxota': (4, 0),
    'oxota-vyzov': (4, 0),
    'crazycombo': (0, 0),  # dict or special format
    '1224': (12, 0),
    'ostatki-sladki': (0, 0),
    'luckycard': (0, 0),
    'zabava': (0, 0),
    'udachanasdachu': (6, 0),
    'rocketbingo': (0, 0),  # dict format
    'spec': (1, 0),
}


def _int_list(raw) -> list[int]:
    """Convert raw API values to a clean list of positive ints."""
    nums = []
    for v in raw:
        try:
            n = int(v)
            if 0 < n:
                nums.append(n)
        except (ValueError, TypeError):
            pass
    return nums


def extract_blocks(combination: dict, game_name: str = '') -> tuple[str, str]:
    """Extract block1 and block2 numbers from API combination dict.

    Returns (block1_str, block2_str) — comma-separated number strings.
    Empty string means no numbers for that block.

    Handles all Stoloto API formats:
      A) structured is a flat list:  [22, 10, 44, 2, 7, 35]
      B) structured is a dict:     {"played": [15,20,...], "notPlayed": [3]}
      C) structured is a dict:     {"notPlayed": [59,74,...]}
      D) structured is list-of-dicts: [{"first":[7,9,1], "second":[1]}]
      E) structured is a dict:     {"played": [...], "parity": "ODD", "column": 5}
    """
    block1_str = ""
    block2_str = ""

    if not combination:
        return block1_str, block2_str

    structured = combination.get("structured")
    if structured is None:
        return block1_str, block2_str

    # Format D — list of dicts (e.g., [{"first":[7,9,1], "second":[1]}])
    if isinstance(structured, list) and structured and isinstance(structured[0], dict):
        d = structured[0]
        if isinstance(d, dict):
            first = d.get("first")
            second = d.get("second")
            if isinstance(first, list):
                f_nums = _int_list(first)
                if f_nums:
                    block1_str = ", ".join(str(n) for n in f_nums)
            if isinstance(second, list):
                s_nums = _int_list(second)
                if s_nums:
                    block2_str = ", ".join(str(n) for n in s_nums)
            if block1_str or block2_str:
                return block1_str, block2_str
        return block1_str, block2_str

    # Formats B, C, E — dict with played/notPlayed keys
    if isinstance(structured, dict):
        played = structured.get("played")
        not_played = structured.get("notPlayed")
        if isinstance(played, list) and played:
            p_nums = _int_list(played)
            if p_nums:
                # For games with format hint (0,0) like dict-format games,
                # put all numbers from 'played' into block1
                hint = GAME_FORMAT_HINTS.get(game_name)
                if hint and hint[0] > 0 and len(p_nums) >= hint[0]:
                    block1_str = ", ".join(str(n) for n in p_nums[:hint[0]])
                    if hint[1] > 0:
                        remaining = p_nums[hint[0]:hint[0]+hint[1]]
                        if remaining:
                            block2_str = ", ".join(str(n) for n in remaining)
                else:
                    block1_str = ", ".join(str(n) for n in p_nums)
        if isinstance(not_played, list) and not_played:
            np_nums = _int_list(not_played)
            if np_nums:
                block2_str = ", ".join(str(n) for n in np_nums)
        if block1_str or block2_str:
            return block1_str, block2_str

    # Format A — flat list of numbers
    if isinstance(structured, list) and structured:
        all_nums = _int_list(structured)
        if all_nums:
            hint = GAME_FORMAT_HINTS.get(game_name)
            if hint:
                b1_count, b2_count = hint
                if b2_count > 0 and len(all_nums) >= b1_count + b2_count:
                    block1_str = ", ".join(str(n) for n in all_nums[:b1_count])
                    block2_str = ", ".join(str(n) for n in all_nums[b1_count:b1_count + b2_count])
                elif b1_count > 0:
                    # Take exactly b1_count numbers (important: don't take more!)
                    block1_str = ", ".join(str(n) for n in all_nums[:b1_count])
                    # Remaining go to block2 if expected
                    if b2_count > 0 and len(all_nums) > b1_count:
                        block2_str = ", ".join(str(n) for n in all_nums[b1_count:b1_count + b2_count])
                elif b1_count == 0 and b2_count == 0:
                    # Unknown format hint (0,0) — put all in block1
                    block1_str = ", ".join(str(n) for n in all_nums)
                else:
                    block1_str = ", ".join(str(n) for n in all_nums)
            else:
                # Unknown game format — put all numbers in block1 (3-part fallback)
                block1_str = ", ".join(str(n) for n in all_nums)

    return block1_str, block2_str


def draw_to_line(draw: dict, game_name: str = '') -> str:
    """Convert an API draw dict to a file line.

    Output format: DATE||NUMBER||BLOCK1||BLOCK2 (4-part)
    Falls back to: DATE||NUMBER||ALL_NUMBERS (3-part) if blocks can't be separated.
    """
    date_str = fmt_datetime(draw.get("date", ""))
    number   = draw.get("number", "")

    b1, b2 = extract_blocks(draw.get("combination", {}), game_name)

    # Fallback: use winningCombination if structured didn't work
    if not b1 and not b2:
        wc = draw.get("winningCombination", [])
        if isinstance(wc, list) and wc:
            nums = _int_list(wc)
            if nums:
                hint = GAME_FORMAT_HINTS.get(game_name)
                if hint:
                    b1_count, b2_count = hint
                    if b2_count > 0 and len(nums) >= b1_count + b2_count:
                        b1 = ", ".join(str(n) for n in nums[:b1_count])
                        b2 = ", ".join(str(n) for n in nums[b1_count:b1_count + b2_count])
                    else:
                        b1 = ", ".join(str(n) for n in nums[:b1_count]) if b1_count > 0 else ", ".join(str(n) for n in nums)
                else:
                    b1 = ", ".join(str(n) for n in nums)

    if b1 and b2:
        return f"{date_str}||{number}||{b1}||{b2}"
    elif b1:
        return f"{date_str}||{number}||{b1}"
    else:
        return f"{date_str}||{number}||"


def _last_day_of_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year, 12, 31)
    return datetime(year, month + 1, 1) - timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════════════
#  РАБОТА С ФАЙЛОМ
# ══════════════════════════════════════════════════════════════════════════════

class DrawRecord:
    """Одна строка файла: дата-время, номер тиража, числа."""

    __slots__ = ("line", "number", "dt")

    def __init__(self, line: str):
        self.line = line.strip()
        parts = self.line.split("||")
        if len(parts) < 2:
            raise ValueError(f"Неверный формат строки: {line!r}")
        self.dt     = parse_file_date(parts[0])
        self.number = int(parts[1])


def load_file(path: str) -> list[DrawRecord]:
    """
    Читает файл и возвращает список DrawRecord.
    Строки с ошибками парсинга пропускаются с предупреждением.
    """
    records = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(DrawRecord(line))
            except (ValueError, IndexError) as e:
                print(f"  [!] Строка {i} пропущена (ошибка парсинга): {e}")
    return records


def deduplicate(records: list[DrawRecord]) -> tuple[list[DrawRecord], int]:
    """
    Убирает дубликаты по номеру тиража (оставляет первое вхождение).
    Возвращает (очищенный список, количество удалённых дублей).
    """
    seen: set[int] = set()
    unique: list[DrawRecord] = []
    dup_count = 0
    for rec in records:
        if rec.number in seen:
            dup_count += 1
        else:
            seen.add(rec.number)
            unique.append(rec)
    return unique, dup_count


def find_gaps(records: list[DrawRecord]) -> list[int]:
    """
    Ищет пропущенные номера тиражей.
    Предполагается непрерывная нумерация без пропусков у лотереи.
    Возвращает отсортированный список отсутствующих номеров.
    """
    if not records:
        return []
    numbers = sorted(r.number for r in records)
    expected = set(range(numbers[0], numbers[-1] + 1))
    return sorted(expected - set(numbers))


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАПРОСЫ К API
# ══════════════════════════════════════════════════════════════════════════════

def _api_get(game: str, date_from: datetime, date_to: datetime,
             page: int = 1, count: int = PAGE_SIZE, retries: int = 5) -> tuple[list, bool]:
    """Fetch a page of draws from the API.

    Returns:
        (draws_list, was_rate_limited)
        was_rate_limited=True means the empty result is due to rate limiting,
        not genuine end-of-data. Caller should retry.
    """
    params = {
        "game":      game,
        "date_from": fmt_date(date_from),
        "date_to":   fmt_date(date_to),
        "count":     count,
        "page":      page,
    }
    for attempt in range(retries + 1):
        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
            if resp.status_code == 429:
                # Rate limited — wait and retry with exponential backoff
                wait = min(2 ** (attempt + 1), 60)  # v39.5.1: max 60s (was 30s)
                print(f"  [!] Rate limited (429), ожидание {wait}с...", end=" ", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            draws = data.get("draws", []) if isinstance(data, dict) else []
            return draws, False
        except requests.RequestException as exc:
            if attempt < retries:
                wait = min(2 ** (attempt + 1), 60)  # v39.5.1: max 60s (was 30s)
                print(f"  [!] Ошибка запроса (попытка {attempt+1}/{retries+1}): {exc}", end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"  [!] Ошибка запроса: {exc}")
            return [], True  # rate_limited=True so caller retries
        except ValueError:
            print("  [!] Не удалось разобрать JSON")
            return [], False  # genuine parse error, don't retry
    # All retries exhausted (all 429)
    print(f"  [!] Превышен лимит повторов ({retries+1}) для стр. {page}")
    return [], True  # rate_limited=True


def has_draws(game: str, date_from: datetime, date_to: datetime) -> bool:
    """Check if any draws exist in the given date range. Retries on rate-limit."""
    for _ in range(3):
        draws, rate_limited = _api_get(game, date_from, date_to, page=1, count=1)
        if not rate_limited:
            return len(draws) > 0
        time.sleep(5)
    return False


def fetch_window(game: str, date_from: datetime, date_to: datetime) -> list:
    """Забирает все тиражи в периоде, перелистывая страницы.

    v39.5.1: Retry on rate-limited empty results instead of breaking.
    """
    all_draws = []
    page = 1
    empty_rate_limited_streak = 0
    MAX_EMPTY_STREAK = 3

    while True:
        print(
            f"  Запрос: {fmt_date(date_from)} – {fmt_date(date_to)}, "
            f"стр. {page} ...",
            end=" ",
            flush=True,
        )
        draws, rate_limited = _api_get(game, date_from, date_to, page=page)
        print(f"получено {len(draws)} тиражей")

        if not draws:
            if rate_limited and empty_rate_limited_streak < MAX_EMPTY_STREAK:
                # v39.5.1: Empty result due to rate limiting — retry with backoff
                empty_rate_limited_streak += 1
                wait = min(10 * empty_rate_limited_streak, 60)
                print(f"  [!] Пустой ответ (rate-limit), повтор через {wait}с...", flush=True)
                time.sleep(wait)
                continue
            break  # Genuine end of data

        # Got draws — reset streak
        empty_rate_limited_streak = 0
        all_draws.extend(draws)
        if len(draws) < PAGE_SIZE:
            break  # Last page

        page += 1
        # v39.3.0: Reduced sleep — old formula 0.3*(1+page*0.1) was too slow
        # at page 200 (6.3s/page). New: 0.15 base + 0.02*page, capped at 1.5s
        sleep_time = min(0.15 + 0.02 * page, 1.5)
        time.sleep(sleep_time)

    return all_draws


def fetch_all_draws(game: str, start: datetime) -> list:
    """Выгружает все тиражи от start до сегодня окнами по DATE_WINDOW_DAYS."""
    today = datetime.today()
    all_draws = []
    window_start = start

    while window_start <= today:
        window_end = min(window_start + timedelta(days=DATE_WINDOW_DAYS - 1), today)
        print(f"\n[Окно] {fmt_date(window_start)} → {fmt_date(window_end)}")
        all_draws.extend(fetch_window(game, window_start, window_end))
        window_start = window_end + timedelta(days=1)

    return all_draws


# ── Поиск тиражей по конкретным пропущенным номерам ─────────────────────────

def fetch_draws_by_numbers(game: str, missing_numbers: list[int]) -> dict[int, str]:
    """
    Пытается найти тиражи с конкретными номерами.

    Стратегия: группируем соседние номера в «кластеры», затем для каждого
    кластера расширяем поиск по дате ±SCAN_DAYS от ближайших известных записей.
    Поскольку API не принимает номер тиража как фильтр, мы берём широкий
    временной диапазон вокруг пропуска и ищем нужный номер в ответе.

    Возвращает {number: line_string} для найденных тиражей.
    """
    if not missing_numbers:
        return {}

    # Сканируем с большим запасом по дате — ±90 дней на кластер
    SCAN_DAYS = 90

    found: dict[int, str] = {}
    target_set = set(missing_numbers)

    # Разбиваем пропуски на кластеры соседних номеров
    clusters: list[list[int]] = []
    cluster: list[int] = []
    for num in sorted(missing_numbers):
        if not cluster or num - cluster[-1] <= 10:
            cluster.append(num)
        else:
            clusters.append(cluster)
            cluster = [num]
    if cluster:
        clusters.append(cluster)

    for cl in clusters:
        lo, hi = cl[0], cl[-1]
        print(
            f"\n  [Пропуски] Ищем тиражи №{lo}–{hi} "
            f"(широкий диапазон дат ±{SCAN_DAYS} дн.) ..."
        )

        # Используем дату первого тиража как ориентир для окна поиска
        # Берём 01.01.2009 как нижнюю границу и сегодня как верхнюю,
        # но сужаем запрос до разумного окна вокруг кластера.
        # Так как мы не знаем точную дату — сканируем широко.
        scan_from = SEARCH_EPOCH
        scan_to   = datetime.today()

        # Если диапазон слишком большой — разбиваем на подокна
        delta = (scan_to - scan_from).days
        sub_start = scan_from
        while sub_start <= scan_to and target_set - found.keys():
            sub_end = min(sub_start + timedelta(days=DATE_WINDOW_DAYS - 1), scan_to)
            draws = fetch_window(game, sub_start, sub_end)
            for d in draws:
                num = d.get("number")
                if num in target_set and num not in found:
                    found[num] = draw_to_line(d, game)
                    print(f"    ✓ Найден тираж №{num}")
            # Если все из кластера нашли — прекращаем сканирование
            if not (set(cl) - found.keys()):
                break
            sub_start = sub_end + timedelta(days=1)
            time.sleep(0.3)

    not_found = target_set - found.keys()
    if not_found:
        print(
            f"\n  [!] Не удалось найти тиражи: "
            + ", ".join(f"№{n}" for n in sorted(not_found))
            + "\n      Возможно, они отсутствуют в архиве API."
        )

    return found


# ══════════════════════════════════════════════════════════════════════════════
#  АВТООПРЕДЕЛЕНИЕ ДАТЫ ПЕРВОГО ТИРАЖА
# ══════════════════════════════════════════════════════════════════════════════

def detect_first_draw_date(game: str) -> datetime:
    """
    Находит дату самого первого тиража тремя этапами бинарного поиска:
        год → месяц → день  (~20–25 лёгких запросов с count=1)
    
    Если бинарный поиск не находит тиражи — пробуем прямой запрос за последний год.
    Если и это не помогает — пробуем фиксированную дату 01.01.2009.
    """
    today = datetime.today()
    print("\n[Автоопределение] Ищем дату первого тиража...")

    try:
        years = list(range(SEARCH_EPOCH.year, today.year + 1))
        first_year = _binary_search(
            game,
            units=years,
            make_range=lambda y: (datetime(y, 1, 1), datetime(y, 12, 31)),
            label="год",
        )
        if first_year is None:
            raise RuntimeError("binary_search_year_failed")

        first_month = _binary_search(
            game,
            units=list(range(1, 13)),
            make_range=lambda m: (
                datetime(first_year, m, 1),
                _last_day_of_month(first_year, m),
            ),
            label="месяц",
        ) or 1

        last_day = _last_day_of_month(first_year, first_month).day
        first_day = _binary_search(
            game,
            units=list(range(1, last_day + 1)),
            make_range=lambda d: (
                datetime(first_year, first_month, d),
                datetime(first_year, first_month, d),
            ),
            label="день",
        ) or 1

        result = datetime(first_year, first_month, first_day)
        print(f"[Автоопределение] ✓ Первый тираж: {fmt_date(result)}\n")
        return result
    except Exception as e:
        print(f"[Автоопределение] Бинарный поиск не удался: {e}")
        
        # Fallback 1: try recent year (in case binary search was rate-limited)
        print("[Автоопределение] Попытка: прямой запрос за последний год...")
        one_year_ago = datetime(today.year - 1, today.month, today.day)
        if has_draws(game, one_year_ago, today):
            print(f"[Автоопределение] ✓ Найдены тиражи за последний год, начинаем с {fmt_date(one_year_ago)}\n")
            return one_year_ago
        
        # Fallback 2: try from SEARCH_EPOCH directly (full history)
        print(f"[Автоопределение] Попытка: загрузка с {fmt_date(SEARCH_EPOCH)}...")
        if has_draws(game, SEARCH_EPOCH, datetime(SEARCH_EPOCH.year + 1, 1, 1)):
            print(f"[Автоопределение] ✓ Найдены тиражи, начинаем с {fmt_date(SEARCH_EPOCH)}\n")
            return SEARCH_EPOCH
        
        # Fallback 3: try 01.01.2020 as a safe bet for most games
        fallback_date = datetime(2020, 1, 1)
        print(f"[Автоопределение] Попытка: загрузка с {fmt_date(fallback_date)}...")
        if has_draws(game, fallback_date, today):
            print(f"[Автоопределение] ✓ Найдены тиражи, начинаем с {fmt_date(fallback_date)}\n")
            return fallback_date
        
        raise RuntimeError(
            f"Тиражи для игры «{game}» не найдены. "
            "Возможно, игра не имеет архива или API недоступен."
        )


def _binary_search(game, units, make_range, label, max_errors=3):
    lo, hi = 0, len(units) - 1
    found  = None
    errors = 0
    while lo <= hi:
        mid  = (lo + hi) // 2
        d_from, d_to = make_range(units[mid])
        try:
            exists = has_draws(game, d_from, d_to)
            errors = 0  # reset error counter on success
        except Exception:
            exists = False
            errors += 1
            if errors >= max_errors:
                print(f"  [!] Слишком много ошибок API, прерываем поиск")
                return found
            time.sleep(min(2.0, 0.5 * (errors + 1)))  # gradual backoff, max 2s
            continue
        status = "✓ есть" if exists else "  нет"
        print(
            f"  {label.capitalize():>7} {str(units[mid]):>4}  "
            f"({fmt_date(d_from)} – {fmt_date(d_to)})  {status}"
        )
        time.sleep(0.2)
        if exists:
            found = units[mid]
            hi = mid - 1
        else:
            lo = mid + 1
    return found


# ══════════════════════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════

def save_to_file(lines: list[str], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n✓ Файл сохранён: {output_path}  ({len(lines)} тиражей)")

    # v25.0: Validate last 5 lines of the written file
    _validate_written_file(output_path, num_lines=5)


# ══════════════════════════════════════════════════════════════════════════════
#  ВАЛИДАЦИЯ ЗАПИСАННОГО ФАЙЛА
# ══════════════════════════════════════════════════════════════════════════════

def _validate_written_file(output_path: str, num_lines: int = 5) -> None:
    """v25.0: Validate the last N lines of a written draw file.

    For each line, checks:
      - Has at least 3 parts separated by '||'
      - Numbers in block1 and block2 are valid integers

    Logs warnings to stderr for any invalid lines found.
    """
    import sys as _sys
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            all_lines = [line.strip() for line in f if line.strip()]
        if not all_lines:
            print("  [ВНИМАНИЕ] Файл пуст после записи!", file=_sys.stderr)
            return
        # Take last N lines
        check_lines = all_lines[-num_lines:]
        warnings = 0
        for i, line in enumerate(check_lines, start=len(all_lines) - num_lines + 1):
            parts = line.split("||")
            if len(parts) < 3:
                print(f"  [ВНИМАНИЕ] Строка {i}: меньше 3 частей (||): '{line[:80]}'", file=_sys.stderr)
                warnings += 1
                continue
            # Validate block1 numbers (parts[2])
            block1_str = parts[2].strip()
            if block1_str:
                try:
                    [int(x.strip()) for x in block1_str.split(",") if x.strip()]
                except (ValueError, TypeError):
                    print(f"  [ВНИМАНИЕ] Строка {i}: невалидные числа в block1: '{block1_str[:60]}'", file=_sys.stderr)
                    warnings += 1
            # Validate block2 numbers (parts[3]) if exists
            if len(parts) >= 4 and parts[3].strip():
                block2_str = parts[3].strip()
                try:
                    [int(x.strip()) for x in block2_str.split(",") if x.strip()]
                except (ValueError, TypeError):
                    print(f"  [ВНИМАНИЕ] Строка {i}: невалидные числа в block2: '{block2_str[:60]}'", file=_sys.stderr)
                    warnings += 1
        if warnings == 0:
            pass  # All good, no message needed
    except Exception as e:
        print(f"  [ВНИМАНИЕ] Ошибка валидации файла {output_path}: {e}", file=_sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
#  ЛОГИКА ОБНОВЛЕНИЯ СУЩЕСТВУЮЩЕГО ФАЙЛА
# ══════════════════════════════════════════════════════════════════════════════

def _reformat_line_to_4part(line: str, game_name: str) -> str:
    """Re-format a 3-part draw line to 4-part using GAME_FORMAT_HINTS.

    Input:  DATE||NUM||ALL_NUMBERS  (3-part)
    Output: DATE||NUM||BLOCK1||BLOCK2  (4-part)
    If already 4-part or game unknown, returns line unchanged.
    """
    if not line or not game_name:
        return line
    parts = line.split("||")
    if len(parts) != 3:
        return line  # Already 4-part or invalid
    hint = GAME_FORMAT_HINTS.get(game_name)
    if not hint:
        return line
    b1_count, b2_count = hint
    try:
        nums = [int(x.strip()) for x in parts[2].split(",") if x.strip()]
        if len(nums) < b1_count + b2_count and b2_count > 0:
            return line  # Not enough numbers, leave unchanged
        if b2_count > 0:
            block1 = nums[:b1_count]
            block2 = nums[b1_count:b1_count + b2_count]
            return f"{parts[0]}||{parts[1]}||{', '.join(str(n) for n in block1)}||{', '.join(str(n) for n in block2)}"
        else:
            # Single block game — keep as 3-part
            return line
    except (ValueError, IndexError):
        return line


def update_existing_file(game: str, output_file: str) -> None:
    """
    Читает существующий файл, устраняет дубликаты, добирает пропуски,
    дозаписывает новые тиражи, проверяет ранние периоды и выдаёт
    предупреждение если архив подозрительно мал.
    """
    print(f"\n[Файл] Найден существующий файл: {output_file}")
    print("[Файл] Анализ...")

    records = load_file(output_file)
    if not records:
        print("[!] Файл пустой или не содержит корректных строк. Начинаем заново.")
        start = detect_first_draw_date(game)
        _full_download_and_save(game, start, output_file)
        return

    total_read = len(records)

    # ── 0. Re-format 3-part lines to 4-part ─────────────────────────────────
    if game in GAME_FORMAT_HINTS:
        reformat_count = 0
        with open(output_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        new_lines = []
        for line in all_lines:
            stripped = line.strip()
            if stripped and '||' in stripped:
                parts = stripped.split('||')
                if len(parts) == 3 and GAME_FORMAT_HINTS.get(game, (0, 0))[1] > 0:
                    new_line = _reformat_line_to_4part(stripped, game)
                    if new_line != stripped:
                        reformat_count += 1
                    new_lines.append(new_line + '\n')
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        if reformat_count > 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"  Переформатировано {reformat_count} строк из 3-part в 4-part")
            # Re-read after re-formatting
            records = load_file(output_file)
        else:
            print("  Формат файла: OK (4-part или одно-блочная игра) ✓")
    else:
        print("  Переформатирование: пропущено (неизвестный формат игры)")

    # ── 1. Дубликаты ──────────────────────────────────────────────────────────
    records, dup_count = deduplicate(records)
    if dup_count:
        print(f"  Дубликаты: удалено {dup_count} шт.")
    else:
        print("  Дубликаты: не обнаружены ✓")

    # ── 2. Пропуски в нумерации ───────────────────────────────────────────────
    gaps = find_gaps(records)
    if gaps:
        print(f"  Пропуски : найдено {len(gaps)} номеров → {_format_gaps(gaps)}")
        print("  Запрашиваем пропущенные тиражи из API...")
        fetched = fetch_draws_by_numbers(game, gaps)
        for num, line in fetched.items():
            records.append(DrawRecord(line))
        print(f"  Пропуски : восстановлено {len(fetched)} из {len(gaps)}")
    else:
        print("  Пропуски : не обнаружены ✓")

    # ── 3. Новые тиражи (от даты последней записи до сегодня) ────────────────
    records.sort(key=lambda r: r.number)
    last_dt   = max(r.dt for r in records)
    last_num  = max(r.number for r in records)
    today     = datetime.today()

    # Стартуем с той же ДАТЫ (без времени), что и последний тираж в файле.
    # Новые тиражи этого же дня, вышедшие после записанного, тоже попадут.
    # Уже имеющиеся номера отфильтруются ниже — дублей не будет.
    fetch_from = datetime(last_dt.year, last_dt.month, last_dt.day)

    known_numbers = {r.number for r in records}

    if fetch_from.date() <= today.date():
        print(
            f"\n[Обновление] Загружаем тиражи начиная с {fmt_date(fetch_from)} "
            f"по {fmt_date(today)} (последний в файле: №{last_num})..."
        )
        new_draws = fetch_all_draws(game, fetch_from)
        new_draws_filtered = [
            d for d in new_draws if d.get("number") not in known_numbers
        ]
        for d in new_draws_filtered:
            records.append(DrawRecord(draw_to_line(d, game)))
        if new_draws_filtered:
            print(f"  Добавлено новых тиражей: {len(new_draws_filtered)}")
        else:
            print("  Новых тиражей не найдено ✓")
    else:
        print("\n[Обновление] Файл актуален, новых тиражей нет ✓")

    # ── 4. Финальная сортировка и сохранение ──────────────────────────────────
    records.sort(key=lambda r: r.number)

    new_count = len(new_draws_filtered) if fetch_from.date() <= today.date() else 0
    changed   = dup_count > 0 or len(gaps) > 0 or new_count > 0
    if changed:
        save_to_file([r.line for r in records], output_file)
    else:
        print(f"\n✓ Файл не изменился ({len(records)} тиражей)")

    # ── 5. Проверка ранних тиражей (early-period gap detection) ───────────────
    #     Если первый тираж в файле имеет большой номер (например > 50),
    #     возможно файл был создан неполным из-за rate limiting / timeout.
    #     Проверяем, есть ли более ранние тиражи в API.
    _EARLY_CHECK_THRESHOLD = 50

    records.sort(key=lambda r: r.number)
    earliest_number = records[0].number
    earliest_dt = records[0].dt

    if earliest_number > _EARLY_CHECK_THRESHOLD:
        early_check_to = earliest_dt - timedelta(days=1)
        if SEARCH_EPOCH < early_check_to:
            print(
                f"\n[Ранние тиражи] Первый в файле: №{earliest_number} "
                f"(от {fmt_date(earliest_dt)}). "
                f"Проверяем, нет ли более ранних..."
            )
            try:
                early_draws = fetch_window(game, SEARCH_EPOCH, early_check_to)
                early_added = 0
                current_known = {r.number for r in records}
                for d in early_draws:
                    num = d.get("number")
                    if num is not None and num < earliest_number and num not in current_known:
                        records.append(DrawRecord(draw_to_line(d, game)))
                        current_known.add(num)
                        early_added += 1
                if early_added > 0:
                    records.sort(key=lambda r: r.number)
                    print(f"  [Ранние тиражи] Найдено и добавлено: {early_added} тиражей")
                    save_to_file([r.line for r in records], output_file)
                else:
                    print("  [Ранние тиражи] Ранних тиражей не найдено ✓")
            except Exception as e:
                print(f"  [Ранние тиражи] Ошибка при проверке: {e}")
        else:
            print(
                f"\n[Ранние тиражи] Первый тираж №{earliest_number} "
                f"— дата близка к SEARCH_EPOCH, проверка не требуется ✓"
            )
    else:
        print(
            f"\n[Ранние тиражи] Первый тираж №{earliest_number} "
            f"— порог ({_EARLY_CHECK_THRESHOLD}) не превышен, проверка не требуется ✓"
        )

    # ── 6. Проверка общего количества тиражей (sanity check) ───────────────────
    #     Если количество тиражей подозрительно мало для охватываемого периода,
    #     предупреждаем о возможной неполноте архива.
    records.sort(key=lambda r: r.number)
    final_count = len(records)
    final_first_dt = records[0].dt
    final_last_dt = max(r.dt for r in records)
    date_span_days = (final_last_dt - final_first_dt).days
    if date_span_days > 0:
        # Conservative lower bound: ~0.3 draws/day covers most game frequencies
        # (daily games ≈1/day, weekly games ≈0.14/day, twice-weekly ≈0.29/day)
        min_expected = int(date_span_days * 0.3)
        if final_count < min_expected and min_expected > 10:
            print(
                f"\n[!] ВНИМАНИЕ: Файл содержит {final_count} тиражей "
                f"за {date_span_days} дней "
                f"({fmt_date(final_first_dt)} – {fmt_date(final_last_dt)}). "
                f"Ожидается минимум ~{min_expected} тиражей. "
                f"Возможно, архив неполный. Рекомендуется удалить файл "
                f"и выполнить полную перезагрузку (без --date_from)."
            )


def _format_gaps(gaps: list[int]) -> str:
    """Компактное представление пропусков: 5, 7–12, 20 → '5, 7–12, 20'"""
    if not gaps:
        return ""
    parts = []
    start = prev = gaps[0]
    for n in gaps[1:]:
        if n == prev + 1:
            prev = n
        else:
            parts.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = n
    parts.append(f"{start}" if start == prev else f"{start}–{prev}")
    return ", ".join(parts)


def _full_download_and_save(game: str, start: datetime, output_file: str) -> None:
    """Полная выгрузка с нуля.

    v39.5.1: After initial download, checks for gaps and fills them.
    """
    print(f"\nВыгрузка с {fmt_date(start)} по {fmt_date(datetime.today())}...")
    print("─" * 50)
    draws = fetch_all_draws(game, start)
    if not draws:
        print("\n[!] Тиражи не найдены. Проверьте название игры.")
        return

    # Deduplicate by draw number
    seen = set()
    unique_draws = []
    for d in draws:
        num = d.get("number")
        if num is not None and num not in seen:
            seen.add(num)
            unique_draws.append(d)
    if len(unique_draws) < len(draws):
        print(f"  Дубликаты API: удалено {len(draws) - len(unique_draws)}")
        draws = unique_draws

    draws.sort(key=lambda d: d.get("number", 0))

    # v39.5.1: Check for gaps in draw numbers and fill them
    draw_nums = [d.get("number") for d in draws if d.get("number") is not None]
    if len(draw_nums) > 10:
        expected = set(range(draw_nums[0], draw_nums[-1] + 1))
        actual = set(draw_nums)
        gaps = sorted(expected - actual)
        if gaps:
            print(f"\n  [v39.5.1] Найдено {len(gaps)} пропусков после первой загрузки, добираем...")
            fetched = fetch_draws_by_numbers(game, gaps)
            for num, line in fetched.items():
                # Parse the line back to a draw dict
                parts = line.split("||")
                draw_date = parts[0] if len(parts) > 0 else ""
                draw_num = int(parts[1]) if len(parts) > 1 else num
                # Find a matching draw from fetched or create a minimal dict
                # Re-fetch the draw data from the window
                found = False
                for d in draws:
                    if d.get("number") == num:
                        found = True
                        break
                if not found:
                    # We have the line but need the raw dict for draw_to_line
                    # Store line for later use
                    draws.append({"_line": line, "number": num, "date": draw_date})
            # Convert draws with _line to proper format
            final_lines = []
            for d in draws:
                if "_line" in d:
                    final_lines.append(d["_line"])
                else:
                    final_lines.append(draw_to_line(d, game))
            save_to_file(final_lines, output_file)

            # Verify final count
            with open(output_file, 'r', encoding='utf-8') as f:
                final_lines_count = sum(1 for line in f if line.strip() and "||" in line)
            print(f"  [v39.5.1] Итого после заполнения пропусков: {final_lines_count} тиражей")
            return

    save_to_file([draw_to_line(d, game) for d in draws], output_file)


# ══════════════════════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Выгрузка архива тиражей лотереи с stoloto.ru"
    )
    parser.add_argument(
        "--game", required=True,
        help="Название игры, например: 6x45plus, 4x20, rapido",
    )
    parser.add_argument(
        "--date_from", default=None,
        help=(
            "Дата первого тиража в формате ДД.ММ.ГГГГ (необязательно). "
            "Если не указана — определяется автоматически. "
            "Игнорируется, если файл уже существует."
        ),
    )
    parser.add_argument(
        "--output", default=None,
        help="Имя выходного файла (по умолчанию: <game>_draws.txt)",
    )
    args = parser.parse_args()

    import os
    output_file = args.output or f"{args.game}_draws.txt"

    print(f"Игра  : {args.game}")
    print(f"Файл  : {output_file}")
    print("─" * 50)

    # ── Файл уже существует → режим проверки и обновления ────────────────────
    if os.path.exists(output_file):
        update_existing_file(args.game, output_file)
        return

    # ── Файл не существует → полная первичная выгрузка ───────────────────────
    if args.date_from:
        try:
            start = datetime.strptime(args.date_from, "%d.%m.%Y")
            print(f"Старт : {fmt_date(start)}  (задан вручную)")
        except ValueError:
            print(f"[!] Неверный формат даты '{args.date_from}'. Ожидается ДД.ММ.ГГГГ.")
            return
    else:
        try:
            start = detect_first_draw_date(args.game)
        except RuntimeError as e:
            print(f"\n[!] {e}")
            return

    _full_download_and_save(args.game, start, output_file)


if __name__ == "__main__":
    main()
