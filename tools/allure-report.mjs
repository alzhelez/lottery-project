// Собирает единый Allure-отчёт из всех папок allure-results/* , которые есть.
// Папки появляются после соответствующих тестов:
//   python      — npm run test:py:allure        (движок, pytest)
//   e2e         — npm run test:e2e              (интерфейс, Playwright)
//   api-python  — npm run test:api:py           (API, pytest)
//   api-go      — npm run test:api:go           (API, go test → JUnit XML)
//   api-java    — npm run test:api:java         (API, TestNG + REST Assured)
// Запуск: npm run allure:report, затем npm run allure:open.
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = "allure-results";
const dirs = existsSync(root)
  ? readdirSync(root)
      .map((name) => join(root, name))
      .filter((p) => statSync(p).isDirectory() && readdirSync(p).length > 0)
  : [];

if (dirs.length === 0) {
  console.error("Нет результатов в allure-results/: сначала запустите тесты (см. README, раздел «Тесты»).");
  process.exit(1);
}

console.log("Результаты:", dirs.join(", "));
const r = spawnSync("npx", ["allure", "generate", ...dirs], { stdio: "inherit", shell: process.platform === "win32" });
process.exit(r.status ?? 1);
