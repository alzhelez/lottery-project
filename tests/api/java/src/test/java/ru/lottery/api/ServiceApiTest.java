// Пакет API-тестов.
package ru.lottery.api;

// Allure.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Ответ сервера.
import io.restassured.response.Response;
// TestNG.
import org.testng.annotations.Test;

// Объект JSON.
import java.util.Map;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-12…API-14: служебные эндпоинты. */
@Epic("API (Java)")
@Feature("Сервис")
public class ServiceApiTest extends BaseApiTest {

    @Test(description = "API-12. Статус автозапуска")
    public void autoStatus() {
        // GET /api/auto — весь объект ответа.
        Map<String, Object> body = get("/api/auto").jsonPath().getMap("$");
        // Ровно два поля: статус последнего цикла и признак «идёт сейчас».
        assertThat(body).containsOnlyKeys("status", "running");
        // running — логическое значение.
        assertThat(body.get("running")).isInstanceOf(Boolean.class);
    }

    @Test(description = "API-13. Telegram в тестовом окружении не настроен")
    public void telegramStatus() {
        // GET /api/telegram.
        Map<String, Object> body = get("/api/telegram").jsonPath().getMap("$");
        // Уведомления выключены.
        assertThat(body.get("configured")).isEqualTo(false);
        // Токена нет.
        assertThat(body.get("has_token")).isEqualTo(false);
    }

    @Test(description = "API-14. Результаты: неизвестный вид отчёта — 400")
    public void resultsBadKind() {
        // kind может быть только analysis или godmode.
        Response response = api().queryParam("kind", "secret").when().get("/api/games/4x20/results");
        // 400 Bad Request.
        assertThat(response.statusCode()).isEqualTo(400);
        // Сообщение об ошибке.
        assertThat(response.jsonPath().getString("error")).isEqualTo("Неверный запрос");
    }
}
