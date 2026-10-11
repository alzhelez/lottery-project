// Пакет API-тестов.
package ru.lottery.api;

// Аннотации Allure.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Тест TestNG.
import org.testng.annotations.Test;

// Коллекции.
import java.util.List;
import java.util.Map;
// Collectors — сбор потока в множество.
import java.util.stream.Collectors;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-07: журнал прогнозов. */
@Epic("API (Java)")
@Feature("Журнал прогнозов")
public class JournalApiTest extends BaseApiTest {

    @Test(description = "API-07. После анализа прогноз записан в журнал до тиража")
    public void journalAfterAnalysis() throws Exception {
        // Номер следующего тиража = последний в отчёте анализа + 1.
        double next = num(analysis().get("last_draw_no")) + 1;
        // GET журнала: массив записей.
        List<Map<String, Object>> entries = get("/api/games/4x20/journal").jsonPath().getList("entries");
        // Оставляем записи на следующий тираж.
        List<Map<String, Object>> upcoming = entries.stream()
                // Фильтр по номеру тиража.
                .filter(e -> num(e.get("draw_no")) == next)
                // В список.
                .collect(Collectors.toList());
        // Источники этих прогнозов.
        assertThat(upcoming.stream().map(e -> e.get("source")).collect(Collectors.toSet()))
                // Анализ пишет прогноз лучшего метода и консенсус.
                .contains("analysis_best", "analysis_consensus");
        // Тираж ещё не сыгран — все записи ждут сверки.
        assertThat(upcoming).allMatch(e -> "pending".equals(e.get("status")));
    }
}
