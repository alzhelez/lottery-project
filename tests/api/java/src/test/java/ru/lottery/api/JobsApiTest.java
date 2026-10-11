// Пакет API-тестов.
package ru.lottery.api;

// Аннотации Allure и шаги отчёта.
import io.qameta.allure.Allure;
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
// Ответ сервера.
import io.restassured.response.Response;
// TestNG: параметризация и тесты.
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

// Коллекции для тел запросов и разбора ответов.
import java.util.List;
import java.util.Map;

// Утверждения AssertJ и допуск для дробных чисел.
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

/** API-04…API-06: фоновые задачи. */
@Epic("API (Java)")
@Feature("Фоновые задачи")
public class JobsApiTest extends BaseApiTest {

    /** Некорректные тела запроса и ожидаемый фрагмент ошибки. */
    @DataProvider(name = "badJobs")
    public Object[][] badJobs() {
        // Строка: имя случая, тело запроса, фрагмент текста ошибки.
        return new Object[][]{
                // Неизвестный тип задачи.
                {"неизвестный тип", Map.of("kind", "rm", "game", "4x20"), "Неизвестный тип задачи"},
                // Анализ без игры.
                {"без игры", Map.of("kind", "analyze"), "Не указана игра"},
                // Попытка выйти из папки.
                {"недопустимое имя", Map.of("kind", "analyze", "game", "../x"), "Недопустимое имя игры"},
                // Бюджет режима Бога 0 минут.
                {"бюджет 0", Map.of("kind", "godmode", "game", "4x20", "budget", 0), "Бюджет"},
                // Бюджет больше 480 минут.
                {"бюджет 481", Map.of("kind", "godmode", "game", "4x20", "budget", 481), "Бюджет"},
                // Строка вместо JSON.
                {"не JSON", "not json", "Ожидается JSON"},
        };
    }

    @Test(description = "API-04. Запуск задачи: некорректные запросы отклоняются с 400", dataProvider = "badJobs")
    public void jobValidation(String caseName, Object body, String error) {
        // POST /api/jobs с некорректным телом (строка уходит как есть, Map — как JSON).
        Response response = post("/api/jobs", body);
        // 400 Bad Request.
        assertThat(response.statusCode()).as(caseName).isEqualTo(400);
        // Текст ошибки объясняет причину.
        assertThat(response.jsonPath().getString("error")).as(caseName).contains(error);
    }

    // throws Exception — waitJob может прервать поток ожидания (InterruptedException).
    @Test(description = "API-05. Анализ: задача не дублируется, завершается, результат корректен")
    public void analysisJob() throws Exception {
        // Отчёт первого анализа (выполняется один раз на прогон).
        Map<String, Object> result = analysis();
        // Шаг отчёта Allure: проверка защиты от дублей.
        Allure.step("Повторный запуск во время работы возвращает ту же задачу", () -> {
            // Тело запроса анализа.
            Map<String, Object> body = Map.of("kind", "analyze", "game", "4x20");
            // Запускаем анализ.
            String first = post("/api/jobs", body).jsonPath().getString("job.id");
            // И сразу ещё раз.
            String second = post("/api/jobs", body).jsonPath().getString("job.id");
            // Сервер вернул ту же задачу.
            assertThat(second).isEqualTo(first);
            // Дожидаемся конца, чтобы не мешать следующим тестам.
            assertThat(waitJob(first).get("status")).isEqualTo("done");
        });
        // Шаг: содержимое отчёта анализа.
        Allure.step("Отчёт анализа", () -> {
            // Отчёт построен по последнему тиражу архива.
            assertThat(num(result.get("last_draw_no"))).isEqualTo(13896.0);
            // Раздел сравнения методов.
            Map<String, Object> evaluation = obj(result, "evaluation");
            // Проверка прошла.
            assertThat(evaluation.get("status")).isEqualTo("ok");
            // Ожидание случайного выбора в 4 из 20 — 1,6 (4·4/20 на каждое поле).
            assertThat(num(obj(evaluation, "baseline").get("mean"))).isCloseTo(1.6, within(1e-6));
            // Прогноз на следующий тираж: список полей.
            @SuppressWarnings("unchecked")
            List<List<Number>> numbers = (List<List<Number>>) obj(evaluation, "next_prediction").get("numbers");
            // В каждом поле 4 разных числа от 1 до 20.
            for (List<Number> block : numbers) {
                // Ровно 4 числа без повторов.
                assertThat(block).hasSize(4).doesNotHaveDuplicates();
                // Все — в диапазоне 1…20.
                assertThat(block).allMatch(v -> v.intValue() >= 1 && v.intValue() <= 20);
            }
            // Мок отдаёт выплаты и цену 150 ₽ — оценка в рублях доступна.
            assertThat(obj(evaluation, "money").get("available")).isEqualTo(true);
            // Цена билета из ответа API мока.
            assertThat(num(obj(evaluation, "money").get("price"))).isEqualTo(150.0);
        });
    }

    @Test(description = "API-06. Несуществующая задача — 404")
    public void unknownJob() {
        // GET по выдуманному id.
        Response response = get("/api/jobs/00000000-0000-0000-0000-000000000000");
        // 404 Not Found.
        assertThat(response.statusCode()).isEqualTo(404);
        // Понятное сообщение.
        assertThat(response.jsonPath().getString("error")).isEqualTo("Задача не найдена");
    }
}
