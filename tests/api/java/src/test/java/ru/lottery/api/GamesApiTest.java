// Пакет API-тестов.
package ru.lottery.api;

// Аннотации Allure: раздел и подраздел отчёта.
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Ответ сервера.
import io.restassured.response.Response;
// DataProvider — источник данных для параметризованного теста TestNG.
import org.testng.annotations.DataProvider;
// Test — помечает метод как тест TestNG.
import org.testng.annotations.Test;

// Список и объект JSON после разбора.
import java.util.List;
import java.util.Map;

// Утверждения AssertJ.
import static org.assertj.core.api.Assertions.assertThat;

/** API-01…API-03: список игр и карточка игры. */
@Epic("API (Java)")
@Feature("Игры")
public class GamesApiTest extends BaseApiTest {

    // description — название теста в отчётах TestNG и Allure.
    @Test(description = "API-01. Список игр: 4 из 20 с тиражами и номером следующего тиража")
    public void gamesList() {
        // GET /api/games.
        Response response = get("/api/games");
        // Ожидаем 200 OK.
        assertThat(response.statusCode()).isEqualTo(200);
        // Версия: три числа через точку, подчёркивание и дата (40.3.0_ДДММГГГГ).
        assertThat(response.jsonPath().getString("version")).matches("\\d+\\.\\d+\\.\\d+_\\d{8}");
        // Массив игр.
        List<Map<String, Object>> games = response.jsonPath().getList("games");
        // Находим 4x20 потоком Java: filter + findFirst.
        Map<String, Object> game = games.stream()
                // Оставляем только запись с нужным slug.
                .filter(g -> "4x20".equals(g.get("slug")))
                // Берём первую.
                .findFirst()
                // Нет — тест падает с сообщением.
                .orElseThrow(() -> new AssertionError("4x20 нет в списке игр"));
        // Мок отдаёт 1500 тиражей.
        assertThat(num(game.get("draws"))).isEqualTo(1500.0);
        // Следующий тираж — последний номер плюс один.
        assertThat(num(game.get("nextNo"))).isEqualTo(num(obj(game, "last").get("no")) + 1);
        // Игра активна: последний тираж был вчера.
        assertThat(obj(game, "activity").get("active")).isEqualTo(true);
    }

    @Test(description = "API-02. Карточка игры: ссылка на stoloto.ru, количество тиражей, период")
    public void gameCard() {
        // GET /api/games/4x20 и сразу весь объект ответа.
        Map<String, Object> game = get("/api/games/4x20").jsonPath().getMap("$");
        // Ссылка по шаблону https://www.stoloto.ru/<игра>/game/.
        assertThat(game.get("stolotoUrl")).isEqualTo("https://www.stoloto.ru/4x20/game/");
        // 1500 тиражей.
        assertThat(num(game.get("draws"))).isEqualTo(1500.0);
        // Пропусков нет.
        assertThat(num(game.get("missing"))).isEqualTo(0.0);
        // Номера подряд: последний − первый + 1 == 1500.
        assertThat(num(obj(game, "last").get("no")) - num(obj(game, "first").get("no")) + 1).isEqualTo(1500.0);
        // Дата в формате ДД.ММ.ГГГГ ЧЧ:ММ.
        assertThat((String) obj(game, "first").get("date")).matches("\\d{2}\\.\\d{2}\\.\\d{4} \\d{2}:\\d{2}");
    }

    /** Данные для API-03: имя случая и путь запроса. */
    @DataProvider(name = "unknownGames")
    public Object[][] unknownGames() {
        // Каждая строка — один запуск теста.
        return new Object[][]{
                // Игры с таким именем нет.
                {"нет такой игры", "/api/games/nope-game"},
                // Попытка выйти из папки данных.
                {"выход из папки", "/api/games/..%2Fetc"},
        };
    }

    // dataProvider — тест запустится для каждой строки unknownGames().
    @Test(description = "API-03. Несуществующая и недопустимая игра — 404", dataProvider = "unknownGames")
    public void unknownGame(String caseName, String path) {
        // Оба запроса должны вернуть 404; as(...) — подпись в сообщении об ошибке.
        assertThat(get(path).statusCode()).as(caseName).isEqualTo(404);
    }
}
