// Пакет API-тестов.
package ru.lottery.api;

// Allure.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Ответ сервера.
import io.restassured.response.Response;
// TestNG.
import org.testng.annotations.Test;

// Коллекции.
import java.util.List;
import java.util.Map;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-17: выгрузка прогнозов в цифровом виде и автоанализ покрытия тиражей. */
@Epic("API (Java)")
@Feature("Журнал прогнозов")
public class DigitalExportApiTest extends BaseApiTest {

    @Test(description = "API-17. Выгрузка прогнозов в цифровом виде и автоанализ покрытия тиражей")
    public void digitalExportAndCoverage() {
        // GET /api/games/6x45/digital?days=0 — все тиражи, по которым есть сверенные прогнозы.
        Response response = get("/api/games/6x45/digital?days=0");
        // Сервер должен ответить 200 OK и отдать текстовый файл.
        assertThat(response.statusCode()).as(response.asString()).isEqualTo(200);
        assertThat(response.contentType()).startsWith("text/plain");
        // Тиражи — от самого дальнего к ближайшему.
        String text = response.asString();
        assertThat(text).contains("Тиражи: 100; 101; 102; 103; 104");
        // Лучший метод анализа: 3 из 6 в тираже 100 и 1 из 6 в тираже 101.
        assertThat(text).contains("ЛМА: 111000; 100000; -; -; -");
        // Порядок из хаоса: 0 и 2 из 6.
        assertThat(text).contains("ПиХ: -; -; 000000; 110000; -");
        // Наименее вероятные: выпали 4 их числа.
        assertThat(text).contains("НВ: -; -; -; -; 111100");
        // Недопустимый период — 400.
        assertThat(get("/api/games/6x45/digital?days=5").statusCode()).isEqualTo(400);
        // GET /api/games/4x20/coverage — автоанализ: семь методов, счётчики сходятся.
        Response cov = get("/api/games/4x20/coverage");
        List<Map<String, Object>> methods = cov.jsonPath().getList("methods");
        assertThat(methods).hasSize(7);
        // У каждого метода «есть» + «пропуски» + «быть не может» = число тиражей архива.
        double draws = num(cov.jsonPath().get("draws"));
        for (Map<String, Object> m : methods) {
            assertThat(num(m.get("have")) + num(m.get("missing")) + num(m.get("na"))).isEqualTo(draws);
        }
    }
}
