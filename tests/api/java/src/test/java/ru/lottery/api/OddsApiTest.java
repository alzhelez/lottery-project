// Пакет API-тестов.
package ru.lottery.api;

// Allure: разделы и шаги.
import io.qameta.allure.Allure;
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// TestNG: тест и действие после теста.
import org.testng.annotations.AfterMethod;
import org.testng.annotations.Test;

// Коллекции.
import java.util.HashMap;
import java.util.List;
import java.util.Map;

// Утверждения AssertJ и допуски.
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

/** API-08, API-11: калькулятор шансов. */
@Epic("API (Java)")
@Feature("Шансы")
public class OddsApiTest extends BaseApiTest {

    /** Тело PUT, которое сбрасывает свои цену и призы (HashMap, потому что Map.of не принимает null). */
    private static Map<String, Object> resetBody() {
        // Изменяемый словарь.
        Map<String, Object> body = new HashMap<>();
        // Цена не задана.
        body.put("price", null);
        // Своих призов нет.
        body.put("prizes", Map.of());
        // Готовое тело.
        return body;
    }

    /** Ищет исход по ключу («2+2») в таблице шансов. */
    private static Map<String, Object> pattern(Map<String, Object> odds, String key) {
        // Список исходов.
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> patterns = (List<Map<String, Object>>) odds.get("patterns");
        // Первый исход с нужным ключом или ошибка.
        return patterns.stream().filter(p -> key.equals(p.get("key"))).findFirst()
                // Ключа нет — тест падает.
                .orElseThrow(() -> new AssertionError("исхода " + key + " нет"));
    }

    // alwaysRun — сброс выполнится, даже если тест упал.
    @AfterMethod(alwaysRun = true)
    public void resetPrizes() {
        // Возвращаем исходное состояние, чтобы не влиять на другие наборы тестов.
        put("/api/games/4x20/odds", resetBody());
    }

    @Test(description = "API-08. Шансы: точная вероятность, выплаты из архива, свои призы")
    public void odds() {
        // Сбрасываем свои призы на случай, если их оставил другой набор тестов.
        put("/api/games/4x20/odds", resetBody());
        // GET шансов.
        Map<String, Object> odds = get("/api/games/4x20/odds").jsonPath().getMap("odds");
        // Шаг: точная вероятность главного приза.
        Allure.step("1 из C(20,4)² = 23 474 025 за 4+4", () ->
                // Сравниваем с допуском: дробная часть — погрешность деления.
                assertThat(num(obj(odds, "jackpot").get("one_in"))).isCloseTo(23_474_025.0, within(2.0)));
        // Шаг: без своих данных берутся выплаты из архива.
        Allure.step("Выплата за 2+2 — медиана архива (300 ₽)", () -> {
            // Исход 2+2.
            Map<String, Object> row = pattern(odds, "2+2");
            // Сумма из мока.
            assertThat(num(row.get("prize"))).isEqualTo(300.0);
            // Источник — архив.
            assertThat(row.get("prize_source")).isEqualTo("archive");
        });
        // Шаг: свои цена и приз важнее архива, лишний ключ отбрасывается.
        Allure.step("Свои цена и приз", () -> {
            // Тело: цена 200, приз за 2+2 = 500, мусорный ключ.
            Map<String, Object> body = Map.of("price", 200, "prizes", Map.of("2+2", 500, "bad key", 1));
            // PUT и новая таблица шансов в ответе.
            Map<String, Object> updated = put("/api/games/4x20/odds", body).jsonPath().getMap("odds");
            // Своя сумма заменила архивную.
            assertThat(num(pattern(updated, "2+2").get("prize"))).isEqualTo(500.0);
            // Источник — пользователь.
            assertThat(pattern(updated, "2+2").get("prize_source")).isEqualTo("user");
            // Возврат с рубля = ожидаемый выигрыш / цена.
            assertThat(num(updated.get("return_per_ruble")))
                    // Допуск относительный: 1e-6 от значения.
                    .isCloseTo(num(updated.get("expected_value")) / 200, within(1e-6));
        });
    }

    @Test(description = "API-11. Шансы всех игр: у бинго калькулятора нет")
    public void oddsAllGames() {
        // GET /api/odds — словарь «игра → шансы» (ключи вида 4x20 читаем через Map, а не путём).
        Map<String, Object> odds = get("/api/odds").jsonPath().getMap("odds");
        // 4 из 20 поддерживается.
        assertThat(obj(odds, "4x20").get("supported")).isEqualTo(true);
        // Русское лото — нет…
        assertThat(obj(odds, "ruslotto").get("supported")).isEqualTo(false);
        // …и указана причина.
        assertThat((String) obj(odds, "ruslotto").get("reason")).isNotBlank();
    }
}
