// Пакет API-тестов.
package ru.lottery.api;

// Allure.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Ответ сервера.
import io.restassured.response.Response;
// TestNG.
import org.testng.annotations.Test;

// Кодировка UTF-8 для разбора CSV.
import java.nio.charset.StandardCharsets;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-10: экспорт в Excel и CSV. */
@Epic("API (Java)")
@Feature("Экспорт")
public class ExportApiTest extends BaseApiTest {

    @Test(description = "API-10. Экспорт в Excel и CSV")
    public void export() {
        // Excel со всеми таблицами: format=xlsx.
        Response xlsx = api().queryParam("format", "xlsx").when().get("/api/games/4x20/export");
        // Тип содержимого — таблица Excel.
        assertThat(xlsx.header("Content-Type")).contains("spreadsheetml");
        // xlsx — это zip-архив: первые байты «PK».
        assertThat(xlsx.asByteArray()).startsWith((byte) 'P', (byte) 'K');
        // CSV тиражей.
        Response csv = api().queryParam("format", "csv").queryParam("what", "draws").when().get("/api/games/4x20/export");
        // Тело как байты.
        byte[] bytes = csv.asByteArray();
        // В начале BOM (EF BB BF) — Excel поймёт, что это UTF-8.
        assertThat(bytes).startsWith((byte) 0xEF, (byte) 0xBB, (byte) 0xBF);
        // Текст без BOM: пропускаем первые 3 байта.
        String text = new String(bytes, 3, bytes.length - 3, StandardCharsets.UTF_8);
        // Первая строка — заголовки через «;».
        assertThat(text.lines().findFirst().orElse("")).isEqualTo("Тираж;Дата;Поле 1;Поле 2");
        // Неизвестный формат — 400.
        assertThat(api().queryParam("format", "pdf").when().get("/api/games/4x20/export").statusCode()).isEqualTo(400);
        // Журнала устаревшей игры нет — 404.
        assertThat(api().queryParam("format", "csv").queryParam("what", "journal").when()
                // Игра duel в моке закрыта, прогнозов по ней нет.
                .get("/api/games/duel/export").statusCode()).isEqualTo(404);
    }
}
