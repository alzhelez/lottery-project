// api_test.go — API-автотесты приложения на Go (стандартный пакет testing).
// Сценарии API-01…API-15 те же, что в Java и Python (см. tests/api/README.md).
// Запуск: python tests/api/env.py start, затем в этой папке: go test -v ./...
package lotteryapi

// Импорты стандартной библиотеки.
import (
	// bytes — проверка начала файла (BOM, «PK»).
	"bytes"
	// math — модуль разности для сравнения дробных чисел.
	"math"
	// net/http — константа метода DELETE.
	"net/http"
	// strings — поиск подстрок в заголовках и тексте.
	"strings"
	// testing — тестовый фреймворк.
	"testing"
)

// TestAPI01GamesList — список игр: 4 из 20 с тиражами и номером следующего тиража.
func TestAPI01GamesList(t *testing.T) {
	// GET /api/games.
	resp := get(t, "/api/games")
	// Ожидаем 200 OK.
	if resp.Status != 200 {
		t.Fatalf("код %d, ожидался 200", resp.Status)
	}
	// Разбираем JSON.
	body := resp.JSON(t)
	// Версия вида 40.3.0_ДДММГГГГ: две точки и подчёркивание.
	version := body["version"].(string)
	if strings.Count(version, ".") != 2 || !strings.Contains(version, "_") {
		t.Errorf("неожиданный формат версии: %s", version)
	}
	// Ищем 4x20 в списке игр.
	var game map[string]any
	// Перебираем элементы массива games.
	for _, g := range body["games"].([]any) {
		// Каждый элемент — объект.
		if m := g.(map[string]any); m["slug"] == "4x20" {
			// Нашли — запоминаем и выходим из цикла.
			game = m
			break
		}
	}
	// Игры нет — дальше проверять нечего.
	if game == nil {
		t.Fatal("4x20 нет в списке игр")
	}
	// Мок отдаёт 1500 тиражей.
	if num(game["draws"]) != 1500 {
		t.Errorf("тиражей %v, ожидалось 1500", game["draws"])
	}
	// Следующий тираж = последний + 1.
	if num(game["nextNo"]) != num(field(game, "last", "no"))+1 {
		t.Errorf("nextNo %v не равен последнему номеру + 1", game["nextNo"])
	}
	// Игра активна: последний тираж был вчера.
	if field(game, "activity", "active") != true {
		t.Error("4x20 должна быть активной")
	}
}

// TestAPI02GameCard — карточка игры: ссылка на stoloto.ru, количество тиражей, период.
func TestAPI02GameCard(t *testing.T) {
	// GET /api/games/4x20.
	game := get(t, "/api/games/4x20").JSON(t)
	// Ссылка по шаблону https://www.stoloto.ru/<игра>/game/.
	if game["stolotoUrl"] != "https://www.stoloto.ru/4x20/game/" {
		t.Errorf("ссылка: %v", game["stolotoUrl"])
	}
	// 1500 тиражей без пропусков.
	if num(game["draws"]) != 1500 || num(game["missing"]) != 0 {
		t.Errorf("тиражей %v, пропусков %v", game["draws"], game["missing"])
	}
	// Номера идут подряд: последний − первый + 1 == 1500.
	if num(field(game, "last", "no"))-num(field(game, "first", "no"))+1 != 1500 {
		t.Error("номера тиражей идут не подряд")
	}
	// Дата «ДД.ММ.ГГГГ ЧЧ:ММ» — 16 символов.
	if date := field(game, "first", "date").(string); len(date) != 16 || date[2] != '.' {
		t.Errorf("формат даты: %s", date)
	}
}

// TestAPI03UnknownGame — несуществующая и недопустимая игра → 404.
func TestAPI03UnknownGame(t *testing.T) {
	// Таблица случаев: имя подтеста → путь.
	for name, path := range map[string]string{"нет такой игры": "/api/games/nope-game", "выход из папки": "/api/games/..%2Fetc"} {
		// t.Run — отдельный подтест со своим именем в отчёте.
		t.Run(name, func(t *testing.T) {
			// Оба запроса должны вернуть 404.
			if resp := get(t, path); resp.Status != 404 {
				t.Errorf("код %d, ожидался 404", resp.Status)
			}
		})
	}
}

// TestAPI04JobValidation — некорректный запуск задачи → 400 с понятной ошибкой.
func TestAPI04JobValidation(t *testing.T) {
	// Срез случаев: тело запроса и ожидаемый фрагмент ошибки.
	cases := []struct {
		// name — имя подтеста.
		name string
		// body — тело запроса (строка — отправляется как есть).
		body any
		// want — ожидаемый фрагмент текста ошибки.
		want string
	}{
		// Неизвестный тип задачи.
		{"неизвестный тип", map[string]any{"kind": "rm", "game": "4x20"}, "Неизвестный тип задачи"},
		// Анализ без игры.
		{"без игры", map[string]any{"kind": "analyze"}, "Не указана игра"},
		// Попытка выйти из папки.
		{"недопустимое имя", map[string]any{"kind": "analyze", "game": "../x"}, "Недопустимое имя игры"},
		// Бюджет режима Бога 0 минут.
		{"бюджет 0", map[string]any{"kind": "godmode", "game": "4x20", "budget": 0}, "Бюджет"},
		// Бюджет больше 480 минут.
		{"бюджет 481", map[string]any{"kind": "godmode", "game": "4x20", "budget": 481}, "Бюджет"},
		// Тело не JSON.
		{"не JSON", "not json", "Ожидается JSON"},
	}
	// Проверяем каждый случай отдельным подтестом.
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			// POST /api/jobs.
			resp := post(t, "/api/jobs", c.body)
			// Ожидаем 400.
			if resp.Status != 400 {
				t.Fatalf("код %d, ожидался 400", resp.Status)
			}
			// И нужный текст ошибки.
			if msg := resp.JSON(t)["error"].(string); !strings.Contains(msg, c.want) {
				t.Errorf("ошибка %q не содержит %q", msg, c.want)
			}
		})
	}
}

// TestAPI05AnalysisJob — анализ: задача не дублируется, завершается, результат корректен.
func TestAPI05AnalysisJob(t *testing.T) {
	// Отчёт первого анализа (запускается один раз на прогон).
	result := analysis(t)
	// Подтест: повторный запуск во время работы возвращает ту же задачу.
	t.Run("без дублей", func(t *testing.T) {
		// Запускаем анализ…
		first := post(t, "/api/jobs", map[string]any{"kind": "analyze", "game": "4x20"}).JSON(t)["job"].(map[string]any)
		// …и сразу ещё раз.
		second := post(t, "/api/jobs", map[string]any{"kind": "analyze", "game": "4x20"}).JSON(t)["job"].(map[string]any)
		// id должны совпасть.
		if first["id"] != second["id"] {
			t.Errorf("запущены две копии: %v и %v", first["id"], second["id"])
		}
		// Дожидаемся конца, чтобы не мешать следующим тестам.
		if job := waitJob(t, first["id"].(string)); job["status"] != "done" {
			t.Errorf("статус %v", job["status"])
		}
	})
	// Подтест: содержимое отчёта.
	t.Run("отчёт", func(t *testing.T) {
		// Отчёт по последнему тиражу архива.
		if num(result["last_draw_no"]) != 13896 {
			t.Errorf("last_draw_no = %v", result["last_draw_no"])
		}
		// Раздел сравнения методов.
		ev := result["evaluation"].(map[string]any)
		// Проверка прошла.
		if ev["status"] != "ok" {
			t.Fatalf("статус сравнения методов: %v", ev["status"])
		}
		// Ожидание случайного выбора в 4 из 20 — ровно 1,6.
		if math.Abs(num(field(ev, "baseline", "mean"))-1.6) > 1e-9 {
			t.Errorf("baseline %v", field(ev, "baseline", "mean"))
		}
		// Прогноз: в каждом поле 4 разных числа от 1 до 20.
		for _, block := range field(ev, "next_prediction", "numbers").([]any) {
			// Множество для проверки уникальности.
			seen := map[float64]bool{}
			// Перебираем числа поля.
			for _, v := range block.([]any) {
				// Число из диапазона и без повторов.
				if n := num(v); n < 1 || n > 20 || seen[n] {
					t.Errorf("некорректное число %v в %v", n, block)
				} else {
					seen[n] = true
				}
			}
			// В поле ровно 4 числа.
			if len(seen) != 4 {
				t.Errorf("в поле %d чисел", len(seen))
			}
		}
		// Мок отдаёт выплаты и цену 150 ₽ — оценка в рублях доступна.
		if field(ev, "money", "available") != true || num(field(ev, "money", "price")) != 150 {
			t.Errorf("оценка в рублях: %v", ev["money"])
		}
	})
}

// TestAPI06UnknownJob — несуществующая задача → 404.
func TestAPI06UnknownJob(t *testing.T) {
	// GET по выдуманному id.
	resp := get(t, "/api/jobs/00000000-0000-0000-0000-000000000000")
	// 404 и сообщение «Задача не найдена».
	if resp.Status != 404 || resp.JSON(t)["error"] != "Задача не найдена" {
		t.Errorf("код %d, тело %s", resp.Status, resp.Body)
	}
}

// TestAPI07JournalAfterAnalysis — после анализа прогноз записан в журнал до тиража.
func TestAPI07JournalAfterAnalysis(t *testing.T) {
	// Номер следующего тиража из отчёта анализа.
	next := num(analysis(t)["last_draw_no"]) + 1
	// GET журнала.
	journal := get(t, "/api/games/4x20/journal").JSON(t)
	// Источники прогнозов на следующий тираж.
	sources := map[string]bool{}
	// Перебираем записи.
	for _, e := range journal["entries"].([]any) {
		// Каждая запись — объект.
		entry := e.(map[string]any)
		// Только записи на следующий тираж.
		if num(entry["draw_no"]) != next {
			continue
		}
		// Тираж ещё не сыгран — статус «ждёт».
		if entry["status"] != "pending" {
			t.Errorf("статус %v, ожидался pending", entry["status"])
		}
		// Запоминаем источник.
		sources[entry["source"].(string)] = true
	}
	// Анализ пишет прогноз лучшего метода и консенсус.
	if !sources["analysis_best"] || !sources["analysis_consensus"] {
		t.Errorf("в журнале нет прогнозов анализа: %v", sources)
	}
}

// pattern ищет исход по ключу («2+2») в таблице шансов.
func pattern(t *testing.T, odds map[string]any, key string) map[string]any {
	// Вспомогательная функция.
	t.Helper()
	// Перебираем исходы.
	for _, p := range odds["patterns"].([]any) {
		// Нашли нужный ключ — возвращаем.
		if m := p.(map[string]any); m["key"] == key {
			return m
		}
	}
	// Ключа нет — ошибка теста.
	t.Fatalf("исхода %s нет", key)
	// Недостижимо.
	return nil
}

// TestAPI08Odds — шансы: точная вероятность, выплаты из архива, свои призы.
func TestAPI08Odds(t *testing.T) {
	// После теста возвращаем исходное состояние призов.
	defer put(t, "/api/games/4x20/odds", map[string]any{"price": nil, "prizes": map[string]any{}})
	// Сбрасываем свои призы на случай, если их оставил другой набор тестов.
	put(t, "/api/games/4x20/odds", map[string]any{"price": nil, "prizes": map[string]any{}})
	// GET шансов.
	odds := get(t, "/api/games/4x20/odds").JSON(t)["odds"].(map[string]any)
	// 4+4: 1 из C(20,4)² = 4845² = 23 474 025.
	if math.Round(num(field(odds, "jackpot", "one_in"))) != 4845*4845 {
		t.Errorf("шанс главного приза: %v", field(odds, "jackpot", "one_in"))
	}
	// Сумма вероятностей всех исходов равна 1.
	total := 0.0
	for _, p := range odds["patterns"].([]any) {
		total += num(p.(map[string]any)["p"])
	}
	if math.Abs(total-1) > 1e-12 {
		t.Errorf("сумма вероятностей %v", total)
	}
	// Выплата за 2+2 — 300 ₽ по официальной таблице выигрышей (она важнее архива).
	if p := pattern(t, odds, "2+2"); num(p["prize"]) != 300 || p["prize_source"] != "rules" {
		t.Errorf("2+2 из таблицы выигрышей: %v", p)
	}
	// Свои цена и приз; мусорный ключ должен быть отброшен.
	odds = put(t, "/api/games/4x20/odds", map[string]any{"price": 200, "prizes": map[string]any{"2+2": 500, "bad key": 1}}).JSON(t)["odds"].(map[string]any)
	// Своя сумма заменила архивную.
	if p := pattern(t, odds, "2+2"); num(p["prize"]) != 500 || p["prize_source"] != "user" {
		t.Errorf("2+2 после PUT: %v", p)
	}
	// Возврат с рубля = ожидаемый выигрыш / цена.
	if math.Abs(num(odds["return_per_ruble"])-num(odds["expected_value"])/200) > 1e-12 {
		t.Errorf("возврат с рубля %v", odds["return_per_ruble"])
	}
}

// TestAPI09Tickets — генератор билетов и проверка своей комбинации.
func TestAPI09Tickets(t *testing.T) {
	// Генерируем три билета.
	gen := post(t, "/api/games/4x20/tickets", map[string]any{"count": 3}).JSON(t)["tickets"].(map[string]any)
	// Билеты — массив.
	tickets := gen["tickets"].([]any)
	// Их ровно три.
	if len(tickets) != 3 {
		t.Fatalf("билетов %d", len(tickets))
	}
	// В каждом билете по два поля из 4 чисел.
	for _, tk := range tickets {
		for _, block := range tk.(map[string]any)["blocks"].([]any) {
			if len(block.([]any)) != 4 {
				t.Errorf("поле %v", block)
			}
		}
	}
	// Проверяем популярную комбинацию 1-2-3-4.
	check := post(t, "/api/games/4x20/tickets", map[string]any{"check": "1,2,3,4|5,6,7,8"}).JSON(t)["check"].(map[string]any)
	// Комбинация корректна.
	if check["valid"] != true {
		t.Fatalf("комбинация не распознана: %v", check)
	}
	// Собираем коды признаков популярности.
	codes := map[string]bool{}
	for _, b := range check["blocks"].([]any) {
		for _, f := range b.(map[string]any)["flags"].([]any) {
			codes[f.(map[string]any)["code"].(string)] = true
		}
	}
	// Ряд подряд должен быть найден.
	if !codes["runs"] {
		t.Errorf("признак «ряд подряд» не найден: %v", codes)
	}
	// Некорректные запросы — 400.
	for _, body := range []map[string]any{{"count": 0}, {"count": 51}, {"check": "a,b,c"}} {
		if resp := post(t, "/api/games/4x20/tickets", body); resp.Status != 400 {
			t.Errorf("%v: код %d, ожидался 400", body, resp.Status)
		}
	}
}

// TestAPI10Export — экспорт в Excel и CSV.
func TestAPI10Export(t *testing.T) {
	// Excel со всеми таблицами.
	xlsx := get(t, "/api/games/4x20/export?format=xlsx")
	// Тип — таблица Excel, файл — zip (начинается с «PK»).
	if !strings.Contains(xlsx.Header.Get("Content-Type"), "spreadsheetml") || !bytes.HasPrefix(xlsx.Body, []byte("PK")) {
		t.Errorf("xlsx: %s", xlsx.Header.Get("Content-Type"))
	}
	// CSV тиражей.
	csv := get(t, "/api/games/4x20/export?format=csv&what=draws")
	// BOM — метка UTF-8 для Excel.
	bom := []byte{0xEF, 0xBB, 0xBF}
	if !bytes.HasPrefix(csv.Body, bom) {
		t.Error("в CSV нет BOM")
	}
	// Первая строка после BOM — заголовки.
	header := strings.SplitN(string(bytes.TrimPrefix(csv.Body, bom)), "\n", 2)[0]
	if strings.TrimSpace(header) != "Тираж;Дата;Поле 1;Поле 2" {
		t.Errorf("заголовок CSV: %q", header)
	}
	// Неизвестный формат — 400.
	if resp := get(t, "/api/games/4x20/export?format=pdf"); resp.Status != 400 {
		t.Errorf("format=pdf: код %d", resp.Status)
	}
	// Журнала устаревшей игры нет — 404.
	if resp := get(t, "/api/games/duel/export?format=csv&what=journal"); resp.Status != 404 {
		t.Errorf("журнал duel: код %d", resp.Status)
	}
}

// TestAPI11OddsAllGames — шансы всех игр: игр без выбора чисел (бинго) в списке нет.
func TestAPI11OddsAllGames(t *testing.T) {
	// GET /api/odds.
	odds := get(t, "/api/odds").JSON(t)["odds"].(map[string]any)
	// 4 из 20 поддерживается.
	if field(odds, "4x20", "supported") != true {
		t.Error("4x20 должна поддерживаться")
	}
	// Русское лото (числа не выбираются) убрано из программы.
	if _, ok := odds["ruslotto"]; ok {
		t.Errorf("ruslotto не должно быть в списке: %v", odds["ruslotto"])
	}
}

// TestAPI12AutoStatus — статус автозапуска.
func TestAPI12AutoStatus(t *testing.T) {
	// GET /api/auto.
	body := get(t, "/api/auto").JSON(t)
	// Ровно два поля: status и running.
	if _, ok := body["status"]; !ok || len(body) != 2 {
		t.Errorf("поля ответа: %v", body)
	}
	// running — логическое значение.
	if _, ok := body["running"].(bool); !ok {
		t.Errorf("running: %v", body["running"])
	}
}

// TestAPI13TelegramStatus — в тестовом окружении Telegram не настроен.
func TestAPI13TelegramStatus(t *testing.T) {
	// GET /api/telegram.
	body := get(t, "/api/telegram").JSON(t)
	// Уведомления выключены, токена нет.
	if body["configured"] != false || body["has_token"] != false {
		t.Errorf("telegram: %v", body)
	}
}

// TestAPI14ResultsBadKind — неизвестный вид отчёта → 400.
func TestAPI14ResultsBadKind(t *testing.T) {
	// kind может быть только analysis или godmode.
	resp := get(t, "/api/games/4x20/results?kind=secret")
	// 400 и сообщение.
	if resp.Status != 400 || resp.JSON(t)["error"] != "Неверный запрос" {
		t.Errorf("код %d, тело %s", resp.Status, resp.Body)
	}
}

// TestAPI15MyTickets — мои билеты: сверка с тиражом, итог, неверные запросы, удаление.
func TestAPI15MyTickets(t *testing.T) {
	// Номер последнего тиража 4 из 20 — из списка игр.
	var last float64
	for _, g := range get(t, "/api/games").JSON(t)["games"].([]any) {
		game := g.(map[string]any)
		if game["slug"] == "4x20" {
			last = game["last"].(map[string]any)["no"].(float64)
		}
	}
	// Билет на последний тираж: он уже сыгран — сверяется сразу.
	resp := post(t, "/api/my-tickets", map[string]any{"game": "4x20", "numbers": "1,2,3,4|5,6,7,8", "draw_no": int(last), "price": 150})
	if resp.Status != 200 {
		t.Fatalf("код %d, тело %s", resp.Status, resp.Body)
	}
	ticket := resp.JSON(t)["added"].([]any)[0].(map[string]any)
	// Статус «сверен», угадано по каждому из двух полей.
	if ticket["status"] != "checked" || len(ticket["hits_by_block"].([]any)) != 2 {
		t.Errorf("билет не сверен: %v", ticket)
	}
	// Итог по игре: потрачено не меньше цены билета, ближайший тираж — после последнего.
	body := get(t, "/api/my-tickets?game=4x20").JSON(t)
	summary := body["summary"].(map[string]any)
	if summary["spent"].(float64) < 150 || body["form"].(map[string]any)["next_no"].(float64) <= last {
		t.Errorf("итог: %v, форма: %v", summary, body["form"])
	}
	// Неверные запросы — 400.
	for _, payload := range []map[string]any{{"game": "4x20", "numbers": "1,2,3"}, {"game": "4x20", "numbers": "a,b"}, {"game": "../etc", "numbers": "1"}} {
		if r := post(t, "/api/my-tickets", payload); r.Status != 400 {
			t.Errorf("%v: код %d", payload, r.Status)
		}
	}
	// Удаление: 200, повторно — 400 (билета уже нет).
	path := "/api/my-tickets?game=4x20&id=" + ticket["id"].(string)
	if r := do(t, http.MethodDelete, path, nil); r.Status != 200 {
		t.Errorf("удаление: код %d", r.Status)
	}
	if r := do(t, http.MethodDelete, path, nil); r.Status != 400 {
		t.Errorf("повторное удаление: код %d", r.Status)
	}
}
