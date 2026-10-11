// Пакет API-тестов.
package ru.lottery.api;

// Allure.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// TestNG.
import org.testng.annotations.Test;

// Коллекции.
import java.util.List;
import java.util.Map;
// Collectors — сбор кодов признаков в множество.
import java.util.stream.Collectors;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-09: генератор билетов и проверка комбинации. */
@Epic("API (Java)")
@Feature("Билеты")
public class TicketsApiTest extends BaseApiTest {

    @Test(description = "API-09. Генератор билетов и проверка своей комбинации")
    @SuppressWarnings("unchecked")
    public void tickets() {
        // POST: сгенерировать 3 билета; путь tickets.tickets — массив билетов.
        List<Map<String, Object>> tickets = post("/api/games/4x20/tickets", Map.of("count", 3))
                // Разбираем ответ.
                .jsonPath().getList("tickets.tickets");
        // Ровно три билета.
        assertThat(tickets).hasSize(3);
        // Перебираем билеты.
        for (Map<String, Object> ticket : tickets) {
            // Поля билета — списки чисел.
            for (List<Number> block : (List<List<Number>>) ticket.get("blocks")) {
                // В каждом поле 4 разных числа.
                assertThat(block).hasSize(4).doesNotHaveDuplicates();
            }
        }
        // Проверяем популярную комбинацию: ряд 1-2-3-4 и 5-6-7-8.
        Map<String, Object> check = post("/api/games/4x20/tickets", Map.of("check", "1,2,3,4|5,6,7,8"))
                // Поле check — результат разбора.
                .jsonPath().getMap("check");
        // Комбинация корректна.
        assertThat(check.get("valid")).isEqualTo(true);
        // Собираем коды признаков популярности из всех полей.
        List<Map<String, Object>> blocks = (List<Map<String, Object>>) check.get("blocks");
        // flatMap — объединяем списки признаков полей в один поток.
        assertThat(blocks.stream().flatMap(b -> ((List<Map<String, Object>>) b.get("flags")).stream())
                // Берём код признака.
                .map(f -> f.get("code"))
                // В множество.
                .collect(Collectors.toSet()))
                // Должен найтись «ряд подряд».
                .contains("runs");
        // Некорректные запросы: 0 билетов, 51 билет, буквы вместо чисел.
        for (Map<String, Object> body : List.<Map<String, Object>>of(Map.of("count", 0), Map.of("count", 51), Map.of("check", "a,b,c"))) {
            // Каждый — 400.
            assertThat(post("/api/games/4x20/tickets", body).statusCode()).as(body.toString()).isEqualTo(400);
        }
    }
}
