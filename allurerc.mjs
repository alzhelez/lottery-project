// Конфигурация Allure 3: npm run allure:report
import { defineConfig } from "allure";

export default defineConfig({
  name: "Лотерейный анализатор",
  output: "./allure-report",
  plugins: {
    awesome: {
      options: {
        reportName: "Лотерейный анализатор",
        reportLanguage: "ru",
        groupBy: ["epic", "feature"],
      },
    },
  },
});
