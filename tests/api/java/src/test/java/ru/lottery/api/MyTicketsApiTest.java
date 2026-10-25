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

/** API-15: мои билеты. */
@Epic("API (Java)")
@Feature("Мои билеты")
public class MyTicketsApiTest extends BaseApiTest {

    @Test(description = "API-15. Мои билеты: сверка с тиражом, итог, неверные запросы, удаление")
    @SuppressWarnings("unchecked")
    public void myTickets() {
        // Номер последнего тиража 4 из 20 — из списка игр.
        List<Map<String, Object>> games = get("/api/games").jsonPath().getList("games");
        // Находим 4x20 и берём last.no.
        double last = num(obj(games.stream().filter(g -> "4x20".equals(g.get("slug"))).findFirst().orElseThrow(), "last").get("no"));
        // Билет на последний тираж: он уже сыгран — сверяется сразу.
        Response added = post("/api/my-tickets", Map.of("game", "4x20", "numbers", "1,2,3,4|5,6,7,8", "draw_no", (int) last, "price", 150));
        // Билет принят.
        assertThat(added.statusCode()).as(added.asString()).isEqualTo(200);
        // Первая (единственная) строка.
        Map<String, Object> ticket = (Map<String, Object>) added.jsonPath().getList("added").get(0);
        // Статус «сверен», угадано по каждому из двух полей.
        assertThat(ticket.get("status")).isEqualTo("checked");
        assertThat((List<Object>) ticket.get("hits_by_block")).hasSize(2);
        // Итог по игре.
        Map<String, Object> body = get("/api/my-tickets?game=4x20").jsonPath().getMap("$");
        // Потрачено не меньше цены билета.
        assertThat(num(obj(body, "summary").get("spent"))).isGreaterThanOrEqualTo(150.0);
        // Ближайший тираж — после последнего.
        assertThat(num(obj(body, "form").get("next_no"))).isGreaterThan(last);
        // Неверные запросы: три числа, буквы, чужая папка — 400.
        for (Map<String, Object> payload : List.<Map<String, Object>>of(
                Map.of("game", "4x20", "numbers", "1,2,3"), Map.of("game", "4x20", "numbers", "a,b"),
                Map.of("game", "../etc", "numbers", "1"))) {
            assertThat(post("/api/my-tickets", payload).statusCode()).as(payload.toString()).isEqualTo(400);
        }
        // Удаление: 200, повторно — 400 (билета уже нет).
        String path = "/api/my-tickets?game=4x20&id=" + ticket.get("id");
        assertThat(api().when().delete(path).statusCode()).isEqualTo(200);
        assertThat(api().when().delete(path).statusCode()).isEqualTo(400);
    }
}
