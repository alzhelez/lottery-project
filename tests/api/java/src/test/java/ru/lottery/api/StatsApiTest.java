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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

/** API-16: статистика по журналу прогнозов. */
@Epic("API (Java)")
@Feature("Статистика")
public class StatsApiTest extends BaseApiTest {

    @Test(description = "API-16. Статистика: сколько раз метод угадал половину чисел, лучший и худший метод")
    @SuppressWarnings("unchecked")
    public void stats() {
        // GET /api/stats — статистика по журналу всех игр.
        Response response = get("/api/stats");
        // Сервер должен ответить 200 OK.
        assertThat(response.statusCode()).as(response.asString()).isEqualTo(200);
        // Игра 6 из 45: её журнал подготовило окружение (tests/api/env.py, seed_stats_journal).
        List<Map<String, Object>> games = response.jsonPath().getList("games");
        Map<String, Object> game = games.stream().filter(g -> "6x45".equals(g.get("slug"))).findFirst().orElseThrow();
        // Порог «половина и больше» для 6 чисел — от 3.
        assertThat(game.get("threshold")).isEqualTo("от 3 из 6");
        // Строки по методам — в порядке журнала; собираем их в словарь по источнику.
        Map<String, Map<String, Object>> rows = new LinkedHashMap<>();
        for (Map<String, Object> row : (List<Map<String, Object>>) game.get("rows")) {
            rows.put((String) row.get("source"), row);
        }
        // Лучший метод анализа, порядок из хаоса, наименее вероятные.
        assertThat(rows.keySet()).containsExactly("analysis_best", "chaos", "least");
        // Лучший метод угадал 3 из 6 и 1 из 6: половину и больше — 1 раз из 2.
        assertThat(num(rows.get("analysis_best").get("checked"))).isEqualTo(2.0);
        assertThat(num(rows.get("analysis_best").get("half"))).isEqualTo(1.0);
        // Порядок из хаоса — 0 и 2 из 6: ни разу.
        assertThat(num(rows.get("chaos").get("half"))).isEqualTo(0.0);
        // Случайные 6 чисел угадывают 3 и больше с шансом ≈ 0,0238 — за 2 прогноза в среднем 0,048 раза.
        assertThat(num(rows.get("analysis_best").get("expected"))).isCloseTo(2 * 0.023834, within(1e-4));
        // Двух прогнозов мало для p-value.
        assertThat(rows.get("analysis_best").get("p_better")).isNull();
        // У «наименее вероятных» цель обратная.
        assertThat(rows.get("least").get("goal")).isEqualTo("fewer");
        // Поэтому лучший — «лучший метод анализа» (50%), худший — «порядок из хаоса» (0%), ничьей нет.
        assertThat(obj(game, "best").get("source")).isEqualTo("analysis_best");
        assertThat(obj(game, "worst").get("source")).isEqualTo("chaos");
        assertThat(game.get("tie")).isEqualTo(false);
    }
}
