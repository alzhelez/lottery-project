// client_test.go — вспомогательный HTTP-клиент для API-тестов на Go.
// Только стандартная библиотека: net/http, encoding/json, testing.
// Файл оканчивается на _test.go, поэтому собирается лишь при запуске `go test`.
package lotteryapi

// Импортируем пакеты стандартной библиотеки.
import (
	// bytes — превращаем тело запроса ([]byte) в io.Reader.
	"bytes"
	// encoding/json — кодирование и разбор JSON.
	"encoding/json"
	// io — чтение тела ответа целиком.
	"io"
	// net/http — HTTP-клиент.
	"net/http"
	// os — читаем адрес приложения из переменной окружения.
	"os"
	// strings — проверка префикса адреса.
	"strings"
	// sync — sync.Once: анализ запускается один раз на весь прогон.
	"sync"
	// testing — тестовый фреймворк Go.
	"testing"
	// time — тайм-ауты и паузы при ожидании задачи.
	"time"
)

// baseURL — адрес приложения: из API_BASE_URL или значение по умолчанию.
func baseURL() string {
	// Читаем переменную окружения.
	if v := os.Getenv("API_BASE_URL"); v != "" {
		// Задана — используем её без завершающего «/».
		return strings.TrimRight(v, "/")
	}
	// Не задана — адрес тестового окружения tests/api/env.py.
	return "http://127.0.0.1:3100"
}

// client — общий HTTP-клиент с тайм-аутом 60 секунд на запрос.
var client = &http.Client{Timeout: 60 * time.Second}

// Response — ответ сервера: код, заголовки и тело в виде байтов.
type Response struct {
	// Status — HTTP-код (200, 400, 404…).
	Status int
	// Header — заголовки ответа.
	Header http.Header
	// Body — тело ответа целиком.
	Body []byte
}

// JSON разбирает тело ответа в map (объект JSON); при ошибке тест падает.
func (r Response) JSON(t *testing.T) map[string]any {
	// t.Helper() — в сообщении об ошибке будет строка вызывающего теста, а не этой функции.
	t.Helper()
	// Сюда разберём объект.
	var out map[string]any
	// json.Unmarshal заполняет out из байтов тела.
	if err := json.Unmarshal(r.Body, &out); err != nil {
		// Тело не JSON — останавливаем тест.
		t.Fatalf("ответ не JSON (%d): %s", r.Status, string(r.Body))
	}
	// Возвращаем разобранный объект.
	return out
}

// do отправляет запрос и возвращает Response; сетевые ошибки останавливают тест.
func do(t *testing.T, method, path string, body any) Response {
	// Помечаем как вспомогательную функцию.
	t.Helper()
	// Тело запроса — пустое, если body == nil.
	var reader io.Reader
	// Если тело передано…
	if body != nil {
		// …и это уже строка — отправляем как есть (нужно для теста «не JSON»)…
		if s, ok := body.(string); ok {
			reader = strings.NewReader(s)
		} else {
			// …иначе кодируем значение в JSON.
			data, err := json.Marshal(body)
			// Ошибка кодирования — ошибка в самом тесте.
			if err != nil {
				t.Fatal(err)
			}
			// Оборачиваем байты в Reader.
			reader = bytes.NewReader(data)
		}
	}
	// Собираем запрос: метод, полный адрес, тело.
	req, err := http.NewRequest(method, baseURL()+path, reader)
	// Не удалось собрать запрос (например, неверный адрес).
	if err != nil {
		t.Fatal(err)
	}
	// С телом — сообщаем серверу, что это JSON.
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	// Отправляем запрос.
	resp, err := client.Do(req)
	// Сервер недоступен — тест падает с подсказкой.
	if err != nil {
		t.Fatalf("сервер недоступен (%s): %v — запустите python tests/api/env.py start", baseURL(), err)
	}
	// Тело нужно закрыть, чтобы не держать соединение.
	defer resp.Body.Close()
	// Читаем тело целиком.
	data, err := io.ReadAll(resp.Body)
	// Ошибка чтения — тест падает.
	if err != nil {
		t.Fatal(err)
	}
	// Возвращаем код, заголовки и тело.
	return Response{Status: resp.StatusCode, Header: resp.Header, Body: data}
}

// get — короткая запись для GET.
func get(t *testing.T, path string) Response { t.Helper(); return do(t, http.MethodGet, path, nil) }

// post — короткая запись для POST с телом.
func post(t *testing.T, path string, body any) Response {
	t.Helper()
	return do(t, http.MethodPost, path, body)
}

// put — короткая запись для PUT с телом.
func put(t *testing.T, path string, body any) Response {
	t.Helper()
	return do(t, http.MethodPut, path, body)
}

// waitJob опрашивает задачу, пока её статус «running», и возвращает итоговое состояние.
func waitJob(t *testing.T, id string) map[string]any {
	// Вспомогательная функция.
	t.Helper()
	// Крайний срок — 3 минуты.
	deadline := time.Now().Add(3 * time.Minute)
	// Опрашиваем до крайнего срока.
	for time.Now().Before(deadline) {
		// GET /api/jobs/{id}, поле job.
		job := get(t, "/api/jobs/"+id).JSON(t)["job"].(map[string]any)
		// Задача закончилась — возвращаем её.
		if job["status"] != "running" {
			return job
		}
		// Ждём полсекунды перед следующим опросом.
		time.Sleep(500 * time.Millisecond)
	}
	// Не дождались — тест падает.
	t.Fatalf("задача %s не завершилась за 3 минуты", id)
	// Недостижимо: Fatalf останавливает тест; return нужен компилятору.
	return nil
}

// analysisOnce и analysisResult — анализ 4x20 выполняется один раз на весь прогон.
var (
	// analysisOnce гарантирует однократный запуск.
	analysisOnce sync.Once
	// analysisResult — сохранённый отчёт анализа.
	analysisResult map[string]any
)

// analysis запускает анализ 4x20 (один раз) и возвращает его отчёт.
func analysis(t *testing.T) map[string]any {
	// Вспомогательная функция.
	t.Helper()
	// Тело Do выполнится только при первом вызове.
	analysisOnce.Do(func() {
		// Запускаем фоновую задачу анализа.
		job := post(t, "/api/jobs", map[string]any{"kind": "analyze", "game": "4x20"}).JSON(t)["job"].(map[string]any)
		// Ждём завершения.
		done := waitJob(t, job["id"].(string))
		// Задача должна закончиться успешно.
		if done["status"] != "done" {
			t.Fatalf("анализ завершился со статусом %v: %v", done["status"], done["error"])
		}
		// Читаем отчёт.
		analysisResult = get(t, "/api/games/4x20/results?kind=analysis").JSON(t)["result"].(map[string]any)
	})
	// Если первый запуск упал, отчёта нет — останавливаем и этот тест.
	if analysisResult == nil {
		t.Fatal("анализ не выполнен")
	}
	// Отдаём отчёт.
	return analysisResult
}

// num достаёт число из разобранного JSON (encoding/json кладёт числа в float64).
func num(v any) float64 { return v.(float64) }

// field проходит по вложенным ключам: field(obj, "a", "b") == obj["a"]["b"].
func field(obj map[string]any, keys ...string) any {
	// Текущий уровень вложенности.
	var cur any = obj
	// Идём по ключам.
	for _, k := range keys {
		// На каждом шаге текущее значение должно быть объектом.
		cur = cur.(map[string]any)[k]
	}
	// Значение последнего ключа.
	return cur
}
