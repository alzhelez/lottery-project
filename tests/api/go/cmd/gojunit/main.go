// gojunit — переводит вывод «go test -json» в отчёт JUnit XML.
// JUnit XML читают Allure, GitHub Actions, Jenkins и почти любые CI.
// Названия тестов берутся из комментариев над функциями TestAPIxx
// («// TestAPI01GamesList — список игр: …» → «API-01. Список игр: …»).
//
// Запуск из папки tests/api/go:
//
//	go test -json ./... | go run ./cmd/gojunit -src . -out ../../../allure-results/api-go/junit.xml
package main

// Импорты стандартной библиотеки.
import (
	// bufio — построчное чтение потока событий.
	"bufio"
	// encoding/json — разбор событий go test.
	"encoding/json"
	// encoding/xml — запись отчёта JUnit.
	"encoding/xml"
	// flag — параметры командной строки.
	"flag"
	// fmt — форматирование чисел и сообщений.
	"fmt"
	// go/ast, go/parser, go/token — разбор исходников тестов ради комментариев.
	"go/ast"
	"go/parser"
	"go/token"
	// os — файлы, стандартные потоки, код выхода.
	"os"
	// path/filepath — создание папки для отчёта.
	"path/filepath"
	// regexp — номер сценария из имени функции.
	"regexp"
	// sort — стабильный порядок тестов в отчёте.
	"sort"
	// strings — работа с текстом комментариев.
	"strings"
	// unicode, unicode/utf8 — заглавная первая буква названия.
	"unicode"
	"unicode/utf8"
)

// event — одна строка вывода «go test -json».
type event struct {
	// Action — run, pass, fail, skip, output.
	Action string
	// Package — имя пакета.
	Package string
	// Test — имя теста (пусто для событий пакета).
	Test string
	// Elapsed — длительность в секундах (у pass/fail/skip).
	Elapsed float64
	// Output — строка вывода теста.
	Output string
}

// result — накопленные данные одного теста.
type result struct {
	// status — pass, fail или skip.
	status string
	// seconds — длительность.
	seconds float64
	// output — весь вывод теста (сообщения t.Errorf, t.Log).
	output strings.Builder
}

// XML-структуры отчёта JUnit.
type testSuites struct {
	// Корневой элемент <testsuites>.
	XMLName xml.Name `xml:"testsuites"`
	// Вложенные <testsuite>.
	Suites []testSuite `xml:"testsuite"`
}

// testSuite — один пакет Go.
type testSuite struct {
	// Имя набора.
	Name string `xml:"name,attr"`
	// Число тестов, падений и пропусков.
	Tests    int `xml:"tests,attr"`
	Failures int `xml:"failures,attr"`
	Skipped  int `xml:"skipped,attr"`
	// Общая длительность.
	Time string `xml:"time,attr"`
	// Тесты.
	Cases []testCase `xml:"testcase"`
}

// testCase — один тест или подтест.
type testCase struct {
	// Название, которое увидит человек.
	Name string `xml:"name,attr"`
	// Имя «класса» — для Go это пакет.
	Classname string `xml:"classname,attr"`
	// Длительность.
	Time string `xml:"time,attr"`
	// Причина падения (nil — тест прошёл).
	Failure *message `xml:"failure,omitempty"`
	// Признак пропуска.
	Skipped *message `xml:"skipped,omitempty"`
	// Вывод теста.
	SystemOut string `xml:"system-out,omitempty"`
}

// message — текст падения или пропуска.
type message struct {
	// Короткое сообщение в атрибуте.
	Message string `xml:"message,attr"`
	// Полный текст внутри элемента.
	Text string `xml:",chardata"`
}

// apiNumber находит номер сценария в имени функции: TestAPI07Journal → 07.
var apiNumber = regexp.MustCompile(`^TestAPI(\d+)`)

// titles читает *_test.go в папке src и возвращает «имя функции → название».
func titles(src string) map[string]string {
	// Пустая карта: без исходников останутся имена функций.
	out := map[string]string{}
	// Без -src ничего не читаем.
	if src == "" {
		return out
	}
	// Набор файлов для парсера.
	fset := token.NewFileSet()
	// Все тестовые файлы папки.
	files, _ := filepath.Glob(filepath.Join(src, "*_test.go"))
	// Перебираем файлы.
	for _, name := range files {
		// Разбираем файл вместе с комментариями.
		file, err := parser.ParseFile(fset, name, nil, parser.ParseComments)
		// Ошибка разбора — пропускаем файл.
		if err != nil {
			continue
		}
		// Перебираем объявления верхнего уровня.
		for _, decl := range file.Decls {
			// Нужны только функции с комментарием.
			fn, ok := decl.(*ast.FuncDecl)
			if !ok || fn.Doc == nil {
				continue
			}
			// Номер сценария из имени функции.
			m := apiNumber.FindStringSubmatch(fn.Name.Name)
			if m == nil {
				continue
			}
			// Текст комментария одной строкой.
			doc := strings.TrimSpace(strings.ReplaceAll(fn.Doc.Text(), "\n", " "))
			// Отрезаем «TestAPI01GamesList — ».
			if i := strings.Index(doc, "— "); i >= 0 {
				doc = doc[i+len("— "):]
			}
			// Точку в конце убираем — название, не предложение.
			doc = strings.TrimSuffix(doc, ".")
			// Название с заглавной буквы: «API-01. Список игр…».
			out[fn.Name.Name] = fmt.Sprintf("API-%s. %s", m[1], capitalize(doc))
		}
	}
	// Готово.
	return out
}

// capitalize делает первую букву строки заглавной (работает и с кириллицей).
func capitalize(s string) string {
	// Первая руна и её длина в байтах.
	r, size := utf8.DecodeRuneInString(s)
	// Пустая строка — как есть.
	if size == 0 {
		return s
	}
	// Заглавная + остаток.
	return string(unicode.ToUpper(r)) + s[size:]
}

// display — человекочитаемое имя теста или подтеста.
func display(test string, names map[string]string) string {
	// Подтест: «TestAPI03UnknownGame/выход_из_папки».
	parent, sub, isSub := strings.Cut(test, "/")
	// Название родителя из комментария или имя функции.
	title, ok := names[parent]
	if !ok {
		title = parent
	}
	// Для подтеста добавляем его имя (go test меняет пробелы на «_»).
	if isSub {
		return title + " › " + strings.ReplaceAll(sub, "_", " ")
	}
	// Обычный тест.
	return title
}

// main — точка входа.
func main() {
	// -src — папка с исходниками тестов (для названий).
	src := flag.String("src", "", "папка с *_test.go для названий тестов")
	// -out — куда записать XML (по умолчанию — в стандартный вывод).
	out := flag.String("out", "", "файл отчёта JUnit XML")
	// Разбираем параметры.
	flag.Parse()

	// Названия из комментариев.
	names := titles(*src)
	// Результаты по пакетам: пакет → тест → результат.
	results := map[string]map[string]*result{}
	// Признак: был ли хоть один провал (для кода выхода).
	failed := false

	// Читаем stdin построчно; буфер побольше — строки вывода бывают длинными.
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 1024*1024), 16*1024*1024)
	// Перебираем строки.
	for scanner.Scan() {
		// Разбираем событие.
		var e event
		// Строка не JSON (например, ошибка компиляции) — печатаем и идём дальше.
		if err := json.Unmarshal(scanner.Bytes(), &e); err != nil {
			fmt.Fprintln(os.Stderr, scanner.Text())
			continue
		}
		// Событие пакета без теста: отмечаем только провал пакета.
		if e.Test == "" {
			if e.Action == "fail" {
				failed = true
			}
			continue
		}
		// Карта тестов пакета (создаём при первом событии).
		pkg := results[e.Package]
		if pkg == nil {
			pkg = map[string]*result{}
			results[e.Package] = pkg
		}
		// Результат теста (создаём при первом событии).
		r := pkg[e.Test]
		if r == nil {
			r = &result{}
			pkg[e.Test] = r
		}
		// Обрабатываем событие.
		switch e.Action {
		// Строка вывода — копим.
		case "output":
			r.output.WriteString(e.Output)
		// Итог теста — запоминаем статус и время.
		case "pass", "fail", "skip":
			r.status = e.Action
			r.seconds = e.Elapsed
			// Провал любого теста — провал прогона.
			if e.Action == "fail" {
				failed = true
			}
		}
	}

	// Собираем XML.
	report := testSuites{}
	// Пакеты по алфавиту.
	pkgs := make([]string, 0, len(results))
	for p := range results {
		pkgs = append(pkgs, p)
	}
	sort.Strings(pkgs)
	// Перебираем пакеты.
	for _, p := range pkgs {
		// Набор тестов пакета.
		suite := testSuite{Name: "API (Go)"}
		// Суммарное время.
		total := 0.0
		// Имена тестов по алфавиту: TestAPI01 < TestAPI02 < …
		tests := make([]string, 0, len(results[p]))
		for t := range results[p] {
			tests = append(tests, t)
		}
		sort.Strings(tests)
		// Перебираем тесты.
		for _, t := range tests {
			// Результат теста.
			r := results[p][t]
			// Тест с подтестами пропускаем: в отчёт идут сами подтесты,
			// иначе каждая проверка посчитается дважды.
			if hasChildren(t, results[p]) {
				continue
			}
			// Запись теста.
			c := testCase{
				// Название из комментария.
				Name: display(t, names),
				// Пакет.
				Classname: p,
				// Время с тремя знаками.
				Time: fmt.Sprintf("%.3f", r.seconds),
				// Вывод теста.
				SystemOut: r.output.String(),
			}
			// Статус.
			switch r.status {
			// Упал — сообщение берём из вывода.
			case "fail":
				c.Failure = &message{Message: "тест упал", Text: r.output.String()}
				suite.Failures++
			// Пропущен.
			case "skip":
				c.Skipped = &message{Message: "тест пропущен"}
				suite.Skipped++
			}
			// Добавляем.
			suite.Cases = append(suite.Cases, c)
			// Считаем.
			suite.Tests++
			total += r.seconds
		}
		// Общее время набора.
		suite.Time = fmt.Sprintf("%.3f", total)
		// Добавляем набор в отчёт.
		report.Suites = append(report.Suites, suite)
	}

	// Сериализуем с отступами.
	data, err := xml.MarshalIndent(report, "", "  ")
	// Ошибка сериализации — аварийный выход.
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	// Заголовок XML + тело.
	data = append([]byte(xml.Header), data...)
	// Без -out — печатаем.
	if *out == "" {
		os.Stdout.Write(data)
	} else {
		// Создаём папку отчёта.
		if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		// Пишем файл.
		if err := os.WriteFile(*out, data, 0o644); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	// Код выхода 1, если тесты упали: CI увидит провал.
	if failed {
		os.Exit(1)
	}
}

// hasChildren — есть ли у теста подтесты («Test/...»).
func hasChildren(test string, tests map[string]*result) bool {
	// Префикс подтестов.
	prefix := test + "/"
	// Ищем любой тест с этим префиксом.
	for t := range tests {
		if strings.HasPrefix(t, prefix) {
			return true
		}
	}
	// Подтестов нет.
	return false
}
