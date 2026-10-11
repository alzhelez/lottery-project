// Пакет тестов: все классы API-тестов лежат в ru.lottery.api.
package ru.lottery.api;

// Фильтр Allure: прикладывает каждый HTTP-запрос и ответ к отчёту.
import io.qameta.allure.restassured.AllureRestAssured;
// Точка входа REST Assured: given() начинает описание запроса.
import io.restassured.RestAssured;
// Настройки разбора JSON (каким типом возвращать числа).
import io.restassured.config.JsonConfig;
// Общая конфигурация REST Assured.
import io.restassured.config.RestAssuredConfig;
// Тип содержимого запроса (application/json).
import io.restassured.http.ContentType;
// Варианты типа чисел при разборе JSON.
import io.restassured.path.json.config.JsonPathConfig;
// Ответ сервера: код, заголовки, тело.
import io.restassured.response.Response;
// Описание запроса до отправки.
import io.restassured.specification.RequestSpecification;

// Map — объект JSON после разбора.
import java.util.Map;

// Утверждения AssertJ: assertThat(...) с читаемыми сообщениями об ошибках.
import static org.assertj.core.api.Assertions.assertThat;

/**
 * Базовый класс API-тестов: адрес приложения, общие настройки запросов и помощники.
 * Все классы тестов наследуются от него.
 */
public abstract class BaseApiTest {

    // Адрес приложения: системное свойство api.baseUrl (задаётся в pom.xml) или переменная API_BASE_URL.
    protected static final String BASE_URL = System.getProperty("api.baseUrl",
            // Если свойство не задано — берём переменную окружения, иначе адрес тестового окружения.
            System.getenv().getOrDefault("API_BASE_URL", "http://127.0.0.1:3100"));

    // Сколько миллисекунд ждём завершения фоновой задачи (анализ идёт несколько секунд).
    private static final long JOB_TIMEOUT_MS = 180_000;

    // Конфигурация: числа из JSON читаем как double, чтобы не терять точность (по умолчанию — float).
    private static final RestAssuredConfig CONFIG = RestAssuredConfig.config()
            // Настраиваем разбор JSON…
            .jsonConfig(JsonConfig.jsonConfig()
                    // …все дробные числа — double.
                    .numberReturnType(JsonPathConfig.NumberReturnType.DOUBLE));

    /** Начало любого запроса: адрес, JSON, конфигурация и запись в отчёт Allure. */
    protected static RequestSpecification api() {
        // given() — начинаем описывать запрос.
        return RestAssured.given()
                // Все пути считаются от адреса приложения.
                .baseUri(BASE_URL)
                // Тело запроса — JSON.
                .contentType(ContentType.JSON)
                // Числа — double (см. CONFIG).
                .config(CONFIG)
                // Запрос и ответ попадут во вложения отчёта Allure.
                .filter(new AllureRestAssured());
    }

    /** GET по пути, возвращает ответ без проверок. */
    protected static Response get(String path) {
        // when() — переходим к отправке, get(path) — отправляем GET.
        return api().when().get(path);
    }

    /** POST с телом (объект превращается в JSON). */
    protected static Response post(String path, Object body) {
        // body(...) — тело запроса, post(path) — отправка.
        return api().body(body).when().post(path);
    }

    /** PUT с телом. */
    protected static Response put(String path, Object body) {
        // Аналогично POST, но методом PUT.
        return api().body(body).when().put(path);
    }

    /** Ждёт, пока фоновая задача перестанет быть «running», и возвращает её состояние. */
    protected static Map<String, Object> waitJob(String jobId) throws InterruptedException {
        // Крайний срок ожидания.
        long deadline = System.currentTimeMillis() + JOB_TIMEOUT_MS;
        // Опрашиваем, пока не вышло время.
        while (System.currentTimeMillis() < deadline) {
            // GET /api/jobs/{id}; jsonPath().getMap("job") — объект задачи.
            Map<String, Object> job = get("/api/jobs/" + jobId).jsonPath().getMap("job");
            // Задача закончилась — возвращаем её.
            if (!"running".equals(job.get("status"))) {
                return job;
            }
            // Ждём полсекунды и спрашиваем снова.
            Thread.sleep(500);
        }
        // Не дождались — тест падает с понятным сообщением.
        throw new AssertionError("Задача " + jobId + " не завершилась за " + JOB_TIMEOUT_MS / 1000 + " с");
    }

    // Отчёт анализа 4x20: запускается один раз и нужен нескольким классам тестов.
    private static Map<String, Object> analysis;

    /** Запускает анализ 4x20 (один раз на весь прогон) и возвращает его отчёт. */
    protected static synchronized Map<String, Object> analysis() throws InterruptedException {
        // Уже выполнен — отдаём сохранённый отчёт.
        if (analysis != null) {
            return analysis;
        }
        // Запускаем фоновую задачу анализа.
        String jobId = post("/api/jobs", Map.of("kind", "analyze", "game", "4x20"))
                // Из ответа берём id задачи.
                .jsonPath().getString("job.id");
        // Дожидаемся завершения.
        Map<String, Object> job = waitJob(jobId);
        // Анализ должен закончиться успешно.
        assertThat(job.get("status")).as("статус анализа").isEqualTo("done");
        // Читаем сохранённый отчёт: GET /api/games/4x20/results?kind=analysis.
        analysis = api().queryParam("kind", "analysis").when().get("/api/games/4x20/results")
                // Поле result — сам отчёт.
                .jsonPath().getMap("result");
        // Отдаём отчёт.
        return analysis;
    }

    /** Достаёт вложенный объект JSON по цепочке ключей: obj["a"]["b"]. */
    @SuppressWarnings("unchecked")
    protected static Map<String, Object> obj(Map<String, Object> source, String... keys) {
        // Начинаем с исходного объекта.
        Map<String, Object> current = source;
        // Спускаемся по каждому ключу.
        for (String key : keys) {
            // Очередной уровень — тоже объект.
            current = (Map<String, Object>) current.get(key);
        }
        // Возвращаем объект на нужной глубине.
        return current;
    }

    /** Число из JSON как double (REST Assured может вернуть Integer или Double). */
    protected static double num(Object value) {
        // Любое число в JSON — наследник Number.
        return ((Number) value).doubleValue();
    }
}
