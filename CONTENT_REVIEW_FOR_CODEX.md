# Portfolio Landing Content Review

**Объект аудита:** `docs/case-study.html` (локальная версия, не задеплоенная) и
зеркальный `CASE_STUDY.md`.
**Тип аудита:** portfolio conversion audit — контент, нарратив, позиционирование,
hiring signal. Не UI/визуальный аудит.
**Дата:** 2026-08-12.

**Измеренные параметры страницы** (viewport 1280×720, локальный превью-сервер):

| Параметр | Значение |
|---|---|
| Полная высота | 10 059 px ≈ **14 экранов** |
| Объём текста | ~2 030 слов |
| Problem | 0.6 экрана (старт: экран 1) |
| Solution | 1.3 экрана |
| What I Built | 2.2 экрана (из них карусель 0.9) |
| My Role | 0.8 экрана (старт: **экран 4.2**) |
| How AI Fits | 1.8 экрана (старт: экран 4.9) |
| Results | **4.6 экрана — 33 % всей страницы** (старт: экран 6.7) |
| What I Learned | 1.9 экрана (старт: экран 11.3) |

Эти цифры — основа большинства рекомендаций ниже: самый сильный сигнал проекта
физически находится там, куда рекрутер не доходит.

---

## 1. Executive Summary

**Насколько страница сильна сейчас.** По честности и дисциплине доказательств
это верхние 5–10 % портфельных кейсов. Здесь нет выдуманных метрик, нет
«AI-powered», каждое число имеет знаменатель, предзаявленные пороги отделены от
результатов, ограничения названы прямо. Такая страница не будет отброшена как
надувательство — а это отсеивает большинство конкурентов.

**Главная проблема.** Страница написана как **документация продукта**, а не как
**аргумент найма**. Она отвечает на вопрос «что представляет собой FlatFeed?»,
но не на вопрос «почему я хочу поговорить с этим человеком?». Три следствия:

1. **Нет кандидата.** На странице нет имени, роли, к которой человек
   претендует, и ни одного способа связи. Единственное действие — «View
   repository». Лендинг, чья цель — интервью, не даёт возможности позвать на
   интервью.
2. **Решения не видны, видны только артефакты.** Страница подробно описывает,
   *что* построено и *что* измерено, но продуктовые решения с их ценой
   (fail-closed matching, матчинг только по Kaltmiete, отказ от скрейпинга,
   удаление собственного демо-тура, минимизация данных) в тексте почти
   отсутствуют — хотя все они реально приняты и подтверждаются репозиторием.
3. **Сильнейший дифференциатор похоронен на 7-м экране.** История «модель
   молча пропускала ошибки → бинарный вывод не позволял понять почему →
   добавление инструкций ухудшило другие поля → я вынес сравнение из модели в
   детерминированный код» — это ровно тот материал, по которому отличают AI PM
   от человека, собравшего обёртку над LLM. Сейчас она сжата до трёх
   нейтральных шагов в блоке «How I selected the setup» на экране ~6.

**Главная возможность.** Не нужно ничего придумывать: всё недостающее уже есть
в репозитории (`eval/AI_QA_FAILURE_ANALYSIS.md`, `eval/AI_QA_EVAL_PLAN.md`,
`docs/PROJECT_CONTEXT.md`, `DESIGN_CONTENT_SYSTEM.md` §§28–29). Нужно
**переставить приоритеты**: поднять решения и диагностическую историю вверх,
сжать повторяющиеся оговорки и повторы продуктовой формулировки, добавить
идентичность кандидата.

**Приведёт ли текущий нарратив к интервью?** Частично. Он вызовет доверие у
того, кто дочитает, но за 45 секунд он не создаёт причины дочитывать. Сейчас
страница выигрывает на глубине и проигрывает на входе.

---

## 2. Current 45-Second Impression

За 45 секунд читатель проходит примерно 2–4 экрана из 14: hero, Solution,
начало What I Built, возможно карусель.

**О проекте он понимает:** Berlin WBS-объявления разбросаны по нескольким
сайтам; есть Telegram-бот, где сохраняешь четыре критерия и получаешь
уведомление о подходящей квартире. Это понятно и сформулировано хорошо.

**О кандидате он понимает:** почти ничего. Имени нет. Целевой роли нет.
Контакта нет. Слово «I» впервые появляется в заголовке навигации «My Role», сам
раздел — на экране 4.2.

**О PM-навыках:** видно аккуратное формулирование проблемы и чистое продуктовое
письмо. Не видно ни одного решения с ценой, ни одного отказа, ни одного
приоритета — то есть не видно продуктового суждения, только продуктовое
описание.

**Об AI-продуктовых навыках:** на первых экранах — ничего. Слово «AI»
встречается впервые в навигации («How AI Fits») и далее на экране 4.9. Читатель,
ушедший через 45 секунд, не узнает, что здесь вообще есть офлайн-оценка на 600
листингах с предзаявленными порогами — единственный самый сильный актив
страницы.

**Рабочая гипотеза о риске:** значительная часть рецензентов закроет страницу с
выводом «аккуратный Telegram-бот для аренды», а не «человек, который умеет
ставить границу AI и проверять её измерением».

---

## 3. Target 45-Second Impression

После изменений те же 45 секунд должны давать:

1. **Что это:** работающий Telegram-прототип, который заменяет ручной обход
   нескольких берлинских жилищных сайтов одним сохранённым фильтром и
   уведомлением.
2. **Кто это сделал и на что претендует:** имя, роль (Product Manager / AI
   Product Manager), ссылка для связи — в шапке, без прокрутки.
3. **Где здесь AI и почему именно там:** матчинг детерминированный; AI
   проверяет качество данных парсера и не принимает пользовательских решений.
4. **Что доказано, а что нет:** продукт реализован; AI-проверка измерена на 600
   синтетических листингах по порогам, зафиксированным до запуска; влияние на
   пользователей не измерено — сказано прямо.
5. **Что человек реально решал:** минимум одно решение с ценой видно уже на
   первом-втором экране (например: неизвестные значения никогда не матчатся —
   лучше пропустить квартиру, чем прислать ложное совпадение).

Разрыв между §2 и §3 — это и есть техническое задание ниже.

---

## 4. What Already Works

Это сохранить. Не переписывать «ради улучшения».

1. **Проблема сформулирована конкретно и без драматизации.** H1 «Berlin WBS
   listings are spread across housing portals and provider websites» — предметный,
   не абстрактный, без «revolutionizing housing search».
2. **Дисциплина доказательств.** Синтетический квалификатор стоит рядом с
   числом, а не в сноске; пороги названы «prototype target»; «User impact is not
   measured yet» — в подзаголовке Results, а не спрятано. Это редкость и
   основной источник доверия.
3. **Тезис «AI flags possible data errors. Fixed rules decide which apartments
   match.»** — лучшая строка на странице. Она за одно предложение показывает
   продуктовое мышление про AI. Её нужно поднимать, а не убирать.
4. **Разбивка по семи полям с объяснением «An overall score can hide a weak
   spot».** Это подлинный сигнал evaluation-мышления: агрегат может скрывать
   слабое место.
5. **Раздел «What did not work» про один непригодный ответ модели.** Один
   честно описанный отказ из 600 стоит дороже, чем четыре 100 %.
6. **Стоимостной сценарий с явным разделением измеренного и оценочного** и с
   честной оговоркой, что 12 398 повторных сдач — это прокси масштаба, а не
   число объявлений. Экономическое мышление + интеллектуальная честность.
7. **Оговорка про коллаборацию с кодовыми агентами** («Claude Code and Codex as
   coding collaborators»). Не убирать и не смягчать (закреплено
   `DESIGN_CONTENT_SYSTEM.md` §24).
8. **Сравнение Without FlatFeed / FlatFeed.** Самый быстрый способ понять
   ценность; работает при беглом просмотре.
9. **Карусель из семи реальных экранов Telegram.** Доказывает, что продукт
   существует, без имитации дашбордов и выдуманных данных.

---

## 5. P0 — Critical Changes

### P0-1. На странице нет кандидата: добавить идентичность, целевую роль и контакт

**Problem.** Ни имени, ни роли, ни LinkedIn/почты. Единственная кнопка — «View
repository». Идентичность выводится только из GitHub-URL (`mich-mayer`).

**Hiring impact.** Прямая потеря конверсии. Рекрутер, которому кейс понравился,
должен иметь возможность действовать немедленно; на странице действия нет. Плюс
отсутствие целевой роли заставляет читателя самому решать, кем считать автора —
и он часто решает «разработчик, который сделал бота».

**Recommended change.** Добавить в шапку имя + целевую роль + одну ссылку для
связи; в финальный блок — повтор контакта как единственного CTA страницы.

**Implementation for Codex.**
- `docs/case-study.html`, `<header class="case-top">` (стр. 27–45): в
  `.top-actions` добавить текстовую подпись автора перед кнопкой репозитория.
  Кнопка «View repository» остаётся (канонический CTA по §19), контакт делается
  вторичной текстовой ссылкой, чтобы не создавать конкуренцию двух кнопок.
- `docs/case-study.html`, `<section class="case-cta">` (стр. 727–732): под
  итоговым заголовком добавить строку контакта.
- Имя, целевую роль и URL **не выдумывать**. Вставить плейсхолдеры
  `{{AUTHOR_NAME}}`, `{{AUTHOR_ROLE}}`, `{{CONTACT_URL}}` и вынести их в
  чек-лист как обязательное заполнение автором.
- `DESIGN_CONTENT_SYSTEM.md` §19 (Action Language) сейчас разрешает в шапке
  только `View repository`. Добавить в §19 строку для контактной ссылки и
  запись в журнал изменений §34 — иначе правка нарушает собственный стандарт
  репозитория.
- То же контактное указание добавить в `CASE_STUDY.md` (в конец), чтобы
  surfaces остались meaning-aligned (§27).

**Suggested copy.**

```
<!-- header, before the repository button -->
<p class="byline">{{AUTHOR_NAME}} · {{AUTHOR_ROLE}} · <a href="{{CONTACT_URL}}">Contact</a></p>
```

```
<!-- case-cta, under the closing statement -->
<p>Built by {{AUTHOR_NAME}}. I am looking for product roles where the AI boundary
has to be defined and defended. <a href="{{CONTACT_URL}}">Get in touch</a> ·
<a href="https://github.com/mich-mayer/flatfeed">View the repository</a></p>
```

---

### P0-2. Первый экран не делает hiring-аргумент: добавить статусную строку фактов

**Problem.** Hero состоит из кикера, H1 и абзаца в 4 предложения (~70 слов). Он
описывает проблему, но не сообщает: что это за артефакт (работающий прототип),
в каком он состоянии (синтетический каталог), что измерено (600 листингов), и
что делал автор. Метаданные `Audience` / `Product` спрятаны в Solution — во
втором экране.

**Hiring impact.** Читатель за 45 секунд не получает ни одного сигнала о
масштабе работы. Проблема Берлина ему не интересна сама по себе — интересен
человек. Сейчас первый экран тратит всё внимание на рынок жилья.

**Recommended change.** Сократить lede с 4 предложений до 3 и **перенести**
`dl.case-meta` из Solution в hero, расширив с двух пунктов до четырёх: Product,
Audience, AI role, My role. Это перенос, а не добавление объёма.

**Implementation for Codex.**
- Удалить `<dl class="case-meta">` из `#solution` (стр. 68–71) и вставить в
  `.hero-copy` после `.case-lede`.
- Из lede убрать третье предложение («In a market where listings may stay online
  only briefly…») — его смысл дублируется в Solution и в панели «Without
  FlatFeed». Оставить: фрагментация → почему это стоит времени → что делает
  FlatFeed.
- В `CASE_STUDY.md` соответствующая правка: вводный абзац + короткий
  список фактов перед «## 1. Problem».
- Governance: `DESIGN_CONTENT_SYSTEM.md` §22 (Element rules → Problem hero и
  Solution) прямо предписывает держать метаданные в Solution и оставлять hero
  text-only. Список фактов остаётся текстовым, но правило про расположение
  метаданных нужно обновить + добавить запись в §34.

**Suggested copy.**

```
<dl class="case-meta">
  <div><dt>Product</dt><dd>Working Telegram apartment-alert prototype, synthetic catalog</dd></div>
  <div><dt>Audience</dt><dd>Berlin WBS renters</dd></div>
  <div><dt>AI role</dt><dd>Offline parser quality check, evaluated on 600 synthetic listings</dd></div>
  <div><dt>My role</dt><dd>Problem definition, product scope, AI boundary, evaluation design; built with coding agents</dd></div>
</dl>
```

Сокращённый lede:

```
A major housing portal can notify users when a new offer appears on its platform,
but housing providers also maintain their own listing pages, and users cannot
assume every offer appears in both places at the same time. FlatFeed lets users
save four criteria once and receive a Telegram notification when a matching
Berlin apartment appears.
```

---

### P0-3. Не видно продуктовых решений: превратить «My Role» в раздел решений с ценой

**Problem.** Сейчас My Role — это один абзац-заявление: «I defined… I chose… I
shaped… I set… I designed…». Это перечисление зон ответственности, а не
доказательство суждения. При этом в проекте есть минимум шесть настоящих
решений с явной ценой, и на лендинге нет ни одного из них.

**Hiring impact.** Это главный различитель между «сделал прототип» и «принимал
продуктовые решения». Интервьюер читает кейс, чтобы найти материал для
вопросов; сейчас зацепиться не за что, кроме AI-оценки. Раздел занимает 0.8
экрана и не окупает своё место.

**Recommended change.** Оставить абзац владения (сжатый), добавить блок из 4–5
карточек «решение → почему → чем пришлось заплатить». Все пункты проверяемы по
репозиторию; ничего изобретать не нужно.

**Implementation for Codex.**
- Секция `#role` (стр. 300–321): сохранить `section-heading` и `role-note`,
  сократив `role-note` до 2 предложений (ownership + coding collaborators).
- Добавить после него `<div class="decision-list decision-list--roles">` с
  карточками (паттерн уже существует в `#ai`, новых стилей не требуется).
- Обязательные к включению решения: **fail-closed**, **отказ от скрейпинга**,
  **удаление собственного демо-тура**. Далее на выбор автора: **Kaltmiete-only**
  или **минимизация данных / `/delete`**. Больше пяти не ставить.
- Источники для проверки формулировок: `docs/PROJECT_CONTEXT.md` (Parsing
  Semantics → Prices; Main Flows → Rules that keep the product flow safe and
  honest), `flatfeed/matching.py:280`, `DESIGN_CONTENT_SYSTEM.md` §28 (Approved
  Patterns, строка «Fail-closed matching on unknown values … Wrong sends are the
  costliest error») и §29 (Deprecated → retired guided demo).
- Governance: `DESIGN_CONTENT_SYSTEM.md` §25 сейчас требует держать
  fail-closed-поведение в технической документации, «unless they explain a
  specific reader-facing risk». Здесь исключение выполняется — решение объясняет
  риск для пользователя (ложное совпадение тратит его окно на отклик).
  Зафиксировать это в §25 и в §22 (Element rules → My Role) + запись в §34.
- Зеркальная правка в `CASE_STUDY.md` §4.
- Рационал каждого решения автор должен подтвердить; Codex не должен
  дописывать мотивы, которых нет в репозитории.

**Suggested copy.**

```
A — Unknown values never match
A listing with an unknown Kaltmiete or room count is not sent, even if
everything else fits. A wrong alert costs the user part of a short response
window; a missed listing costs less.

B — Match on Kaltmiete only
Warmmiete depends on how each provider counts utilities, so it is not comparable
across sources. The card shows both, but only base rent decides a match.

C — No scraping without permission
The demo runs on a synthetic catalog behind the same source-adapter contract
that a real provider adapter would use. The ingestion path is real; the data is
not. The cost of this decision is that source coverage remains unproven.

D — I removed my own demo tour
The first version led visitors through a scripted tour. It demonstrated the
portfolio rather than the product a user would operate, so I replaced it with
the saved-filter flow the bot actually runs.

E — Users can delete everything
FlatFeed stores a Telegram ID and four filter fields. `/delete` removes the
record and the notification history after a confirmation that names the
consequence.
```

---

### P0-4. Самый сильный AI-сигнал рассказан слишком слабо: заменить «How I selected the setup» диагностической историей

**Problem.** Текущие три шага — «начал с дешёвого», «взял модель сильнее»,
«сузил задачу AI» — читаются как процедура закупки. Настоящая история
(`eval/AI_QA_FAILURE_ANALYSIS.md`) гораздо сильнее: проверяющий молча
пропускал подсаженные ошибки; поскольку модель возвращала только бинарный ответ,
причину нельзя было установить; попытка №1 (больше инструкций в промпте)
ухудшила другие поля; попытка №2 (модель возвращает доказательства, но
по-прежнему сама решает о совпадении) не прошла предзаявленные пороги; итоговое
решение — модель только цитирует источник, сравнение делает детерминированный
код, а цитата, отсутствующая в исходном тексте дословно, отклоняется.

**Hiring impact.** Это редчайший на портфельных лендингах материал: цикл
гипотеза → эксперимент → отклонение → перепроектирование контракта вывода. Он
показывает, что человек умеет отлаживать AI-фичу, а не подбирать модели. Именно
эту историю интервьюер будет разбирать на собеседовании.

**Recommended change.** Переписать три шага, сохранив структуру `qa-selection`
и заголовок-вывод. Никаких чисел из ранних прогонов.

**Implementation for Codex.**
- Секция `#ai` → `<section class="qa-selection">` (стр. 369–397): заменить текст
  трёх `<li>`; заменить `h4` на формулировку-вывод.
- **Жёсткое ограничение:** `DESIGN_CONTENT_SYSTEM.md` §23 и §27 запрещают
  публиковать любые числа калибровочных, development- и ранних
  frozen-validation-прогонов на лендинге и в `CASE_STUDY.md`. Историю излагать
  **качественно** (например «missed planted errors silently», без «291/300»,
  без «9», без «19/20»). Никакие цифры в этом блоке появляться не должны —
  иначе упадёт `scripts/check_eval_numbers.py`.
- Названия моделей `gpt-5.6-Luna` / `gpt-5.6-Terra` можно сохранить (они уже на
  странице) либо заменить на «the lower-cost model» / «the stronger model» —
  вторая формулировка читается лучше для нетехнического рекрутера и ничего не
  теряет. Рекомендуется второй вариант, названия оставить только в финальной
  конфигурации в Results.
- Зеркальная правка в `CASE_STUDY.md` §5 «How I selected the AI QA setup».
- Следствие: после этой правки карточка B в What I Learned («Model power was
  only part of the answer») станет дословным повтором — см. P1-4.

**Suggested copy.**

```
Heading: The fix was a smaller AI job, not a bigger model.
Intro: I set acceptance criteria before each run and only increased capability
when a configuration missed them.

01 — Start cheap, with the gates written first
I began with the lower-cost model at its lowest reasoning setting, measured
against criteria fixed before the run.

02 — A stronger model did not fix it
The stronger configuration still missed planted errors silently. Because the
checker returned only a yes/no answer, I could not tell whether it had misread
the listing or compared the values incorrectly. Adding more instructions to the
prompt improved one field and made others worse, so I stopped that direction.

03 — Move the decision out of the model
I changed what the model is allowed to return: exact quotes from the listing for
each field, and nothing else. Deterministic code compares those quotes with the
parsed values and rejects any quote that is not present verbatim in the source.
That configuration passed every predeclared gate.
```

---

### P0-5. Results занимает треть страницы и повторяет сам себя: сжать примерно вдвое

**Problem.** Секция Results — 3 308 px, 4.6 экрана, 33 % высоты страницы. Внутри
одна и та же мысль утверждается многократно:
- «все пороги пройдены» — 13 раз (4 карточки метрик, 7 строк таблицы, карточка
  «Measured · AI QA», блок «Decision»);
- «это синтетика, не продакшн» — 8 раз (подзаголовок Results, карточка
  Measured, `qa-threshold-note`, `qa-findings`, `qa-stop`, сноска стоимости,
  Learned C, «Current limits» — оба столбца);
- «AI не может изменить листинг / решить о совпадении / отредактировать
  карточку» — 4 раза, дважды почти дословно (стр. 348, 583–584), плюс блок
  «Product boundary» и «Current limits».

**Hiring impact.** Двойной: (а) читатель, дошедший до Results, тратит внимание
на повторы вместо новых сигналов; (б) многократное самооправдание начинает
читаться как неуверенность — эффект, обратный задуманному. Одно точное
ограничение убедительнее шести.

**Recommended change.** Оставить в Results: сплит Implemented/Measured, четыре
агрегатные метрики, таблицу по семи полям, «What did not work», стоимостной блок
и одну (одну!) финальную оговорку. Убрать дубли.

**Implementation for Codex.**
- Удалить `<aside class="qa-outcome">` (стр. 445–453): её содержание дословно
  повторяют карточка «Measured · AI QA» и четыре метрики.
- Из `<article>` «How the final check worked» (стр. 574–590) удалить предложение
  «It is separate from runtime AI QA and cannot change a listing, decide a match
  or edit a Telegram card» — это третье повторение границы; она уже установлена
  в `#ai` (карточка C и `reliability-boundary`).
- Объединить `qa-threshold-note` (стр. 490–493) и `blockquote.qa-stop`
  (стр. 602–607) в один короткий блок остановки: пороги были предзаявлены →
  все пройдены → синтетическое тюнингование остановлено → живые данные требуют
  отдельной проверки.
- В `#learned` → `Current limits`: убрать четвёртый буллет «Demo configuration»
  про фотографию — атрибуция уже стоит в подписи к слайду 07, где она
  обязательна (§22). Оставить одну фразу о синтетичности данных листинга.
- Сокращение считать выполненным, если высота `#results` опускается ниже ~2 500 px
  (≈3.5 экрана) без потери ни одного числа из финального прогона.
- Проверять `scripts/check_eval_numbers.py` после правок: все четыре агрегатные
  метрики, семь строк по полям, стоимость прогона и сценарий на 15 000 проверок
  должны остаться.
- Зеркальные правки в `CASE_STUDY.md` §6 и §7.

**Suggested copy** (объединённый блок остановки, заменяет `qa-threshold-note`
и `qa-stop`):

```
These acceptance criteria were fixed before the final run; they are prototype
targets, not industry benchmarks. The run met all of them, so I stopped
synthetic tuning: the prototype is complete at its intended scope. Performance
on live provider data is a separate question and remains unmeasured.
```

---

## 6. P1 — Important Changes

### P1-1. Идеальные 100 % выглядят подозрительно: объяснить сложность бенчмарка

**Problem.** Три метрики из четырёх равны 100.0 %, и все семь полей — «Target
met». Опытный рецензент немедленно задаёт вопрос: «сам сгенерировал ошибки — сам
их и нашёл, насколько трудным был тест?» Страница отвечает на это только
общими словами («controlled feasibility»), но не описывает *конструкцию*
сложности.

**Hiring impact.** Это единственное место, где страница рискует потерять
доверие — при том, что доверие её главный актив. Прямое объяснение превращает
слабость в сигнал evaluation-мышления.

**Recommended change.** Добавить один абзац сразу после четырёх метрик, до
таблицы по полям: как устроены ошибки и почему высокий результат ожидаем.
Материал есть в `eval/AI_QA_EVAL_PLAN.md` §6 (Controlled Error Contract) и §8
(Ground-truth Isolation).

**Implementation for Codex.** Вставить `<p class="qa-threshold-note">` (или
аналогичный существующий блок) после `<dl class="qa-scorecard__metrics">`
(после стр. 488). Зеркально — в `CASE_STUDY.md` §6 после таблицы агрегатных
метрик.

**Suggested copy.**

```
Why these numbers are high: each corrupted listing contains exactly one planted
error, and every error is a direct contradiction that is visible in the listing
text. Ambiguous cases were kept out of the corrupted set by design. The model
never sees which cases are corrupted, the expected values or any case metadata.
This benchmark answers whether the check works at all, not how accurate it would
be on real provider listings, which are messier: several errors at once,
ambiguous phrasing and missing values.
```

---

### P1-2. Синтетические данные поданы как ограничение, а не как решение

**Problem.** Отсутствие живых источников появляется на странице только в
негативной рамке: «the demo does not scrape housing-provider websites», «Current
limits». Между тем это осознанное решение (юридические условия и права на
данные), а не техническая недоделка.

**Hiring impact.** Ограничение читается как «не смог». Решение читается как
«взвесил риск и заплатил за это доказательной полнотой». Для корпоративной AI
PM-роли второе — сильный сигнал (data rights, defensibility).

**Recommended change.** Перенести смысл в раздел решений (карточка C из P0-3),
а в «Current limits» оставить только следствия. Ничего не добавлять к объёму —
это переклассификация одного и того же факта.

**Implementation for Codex.** Первый буллет «Demo configuration» в
`#prototype-setup` (стр. 706) сократить до следствия: «Only the FlatFeed
Synthetic adapter is enabled, so live source coverage is unproven». Причина
переезжает в карточку решений в `#role`. Синхронно — в `CASE_STUDY.md` §7.

---

### P1-3. Раздел Problem не показывает, откуда взята проблема

**Problem.** Проблема утверждается («listings may stay online only briefly»), но
не подкреплена ничем и не помечена как допущение. При этом на странице уже есть
официальный берлинский источник — он используется только в стоимостном блоке в
самом низу.

**Hiring impact.** Два сигнала сразу: (а) человек умеет опираться на публичные
данные; (б) человек умеет отличать факт от собственного допущения и говорит об
этом прямо. Второе особенно ценно и полностью соответствует тону страницы.

**Recommended change.** Добавить в Problem одно предложение с уже
процитированным источником и одно предложение о статусе допущения.

**Implementation for Codex.** Вставить в `.hero-copy` после lede (или как первый
абзац Solution — на усмотрение автора, но не оба сразу). Ссылка та же, что в
стоимостном блоке (стр. 619); во втором месте её можно оставить без повторного
пояснения, чтобы не дублировать.

**Suggested copy.**

```
Six state-owned Berlin housing companies reported 12,398 re-lettings in 2024 —
a figure for re-lettings, not for online ads, but it shows how limited the
supply behind these filters is. I did not run user research for this project:
the framing comes from how providers publish listings and from public market
data, and the first thing I would test with real users is whether an alert
arrives early enough to act on.
```

---

### P1-4. What I Learned после правок частично дублирует How AI Fits

**Problem.** После P0-4 карточка B («Model power was only part of the answer»)
и заголовок раздела («A stronger model helped. A narrower AI task made the
result reliable») повторяют историю выбора конфигурации почти дословно.

**Hiring impact.** Повтор на 12-м экране расходует последнее внимание читателя,
которое лучше потратить на то, чего на странице ещё нет.

**Recommended change.** Заменить карточку B на урок об устройстве самой оценки —
он подлинный (см. `eval/AI_QA_EVAL_PLAN.md` §§6, 8, 10, 12) и на странице пока
не сформулирован.

**Suggested copy.**

```
B — What you can measure decides what you can fix
The first checker returned a yes/no answer, so a miss told me nothing about its
cause. Designing the output so that every claim carries a verifiable quote made
the failures diagnosable — and made the deterministic comparison possible.
```

---

### P1-5. «What I would test next» — сильный блок в слабом формате

**Problem.** Это абзац сплошного текста на 12-м экране. Внутри перечислены
именно те метрики, которые интервьюер ищет: покрытие источников, время от
появления листинга до доставки алерта, доля алертов, по которым пользователь
действовал, доля нерелевантных совпадений. При беглом чтении они не видны.

**Hiring impact.** Metrics thinking — один из главных сигналов PM. Сейчас он
подан так, что его пропустят.

**Recommended change.** Превратить в список из четырёх пунктов с
заголовком-выводом. Формулировки условные («I would…») сохранить — §23 требует
статуса HYPOTHESIS.

**Implementation for Codex.** `#learned` → `aside.role-note` (стр. 685–695):
заменить абзац на `<ul>`; заголовок `preview-label` оставить.

**Suggested copy.**

```
Heading: The next evidence I would collect is about alerts, not about the model.

- Source coverage: how many permitted listings a live adapter actually sees.
- Time to alert: from a listing appearing at the source to a notification
  arriving.
- Acted-on alerts: the share of notifications a user opens or follows up on.
- Wasted alerts: the share of matches that are irrelevant or already gone — the
  counter-metric that keeps the first three honest.
```

---

### P1-6. Соседний кейс подан как сноска, а не как позиционирование

**Problem.** Блок `case-sibling` — одно предложение мелким шрифтом в самом
низу. Между тем два кейса с *разными* границами AI — это готовый и подлинный
дифференциатор.

**Hiring impact.** «Человек, который последовательно думает про роль модели в
продукте» запоминается лучше, чем «человек, который сделал ещё один прототип».

**Recommended change.** Переформулировать в утверждение о подходе.

**Suggested copy.**

```
Two case studies, two different AI boundaries. In FlatFeed the model checks data
quality and deterministic code decides what the user sees. In Opsqora the model
clusters support feedback and a human makes the product decision.
Read the Opsqora case study →
```

---

## 7. P2 — Polish

1. **`<title>` страницы — просто «FlatFeed».** Во вкладке, в закладках и в
   пересылке ссылки это ничего не сообщает. Заменить на
   `FlatFeed — Berlin WBS apartment alerts · Product case study`
   (`docs/case-study.html:10`).
2. **«Prepare every source» как название шага** непонятно вне контекста.
   Заменить на `Normalize every source` — термин уже используется в
   `PROJECT_CONTEXT` («one normalized listing schema»). Синхронно в
   `CASE_STUDY.md` §3.
3. **Подписи в карусели чисто процедурные** («Step one captures the eligibility
   tier»). Две-три подписи могут нести по одному решению без роста объёма,
   например слайд 02: `WBS tiers are preset buttons, not free text: the values
   are fixed by the certificate, and a typo would silently break matching.`
   Только если автор подтверждает рационал.
4. **Двойная атрибуция фотографии** (подпись слайда 07 + буллет в Current
   limits). Оставить в подписи; см. P0-5.

---

## 8. Recommended Page Narrative

Семичастная структура сохраняется (она закреплена в `DESIGN_CONTENT_SYSTEM.md`
§27 и работает); меняется наполнение и вес разделов.

1. **Problem (+ идентичность и статусные факты)** — за 10 секунд сообщает, кто
   автор, что это за артефакт, для кого он и какую повторяющуюся работу
   заменяет.
2. **Solution** — показывает изменение пользовательского маршрута: было
   несколько сайтов вручную → стал один фильтр и одно уведомление.
3. **What I Built** — доказывает, что продукт существует: четыре шага потока,
   семь реальных экранов Telegram, две карточки возможностей.
4. **My Role & decisions** — показывает суждение: 4–5 решений с ценой, каждое
   проверяемо по репозиторию; здесь же владение и коллаборация с кодовыми
   агентами.
5. **How AI Fits** — объясняет, почему AI стоит именно там, где стоит, и как
   автор пришёл к этой границе через отклонённые конфигурации.
6. **Results** — предъявляет измеренное: реализованный продукт отдельно,
   синтетическая оценка отдельно, сложность бенчмарка объяснена, стоимость
   оценена, неудача названа.
7. **What I Learned + Current limits** — показывает, что человек знает границы
   собственных доказательств и умеет назвать следующую проверку в метриках.
8. **Closing + Opsqora + контакт** — оставляет одно запоминающееся утверждение о
   подходе к AI-границе и даёт способ связаться.

---

## 9. Content to Remove or Compress

| Что | Где | Что сделать |
|---|---|---|
| `aside.qa-outcome` («Decision: passed the synthetic benchmark…») | `docs/case-study.html:445–453` | Удалить: дословно дублирует карточку «Measured · AI QA» и четыре метрики |
| «cannot change a listing, decide a match or edit a Telegram card» | стр. 583–584 (третье повторение) | Удалить предложение; граница уже задана в `#ai` |
| `qa-threshold-note` + `blockquote.qa-stop` | стр. 490–493 и 602–607 | Объединить в один блок остановки (копия в P0-5) |
| Буллет об атрибуции фото в Current limits | стр. 709 | Сократить до факта о синтетичности данных; кредит остаётся в подписи слайда 07 |
| Третье предложение lede («In a market where listings may stay online only briefly…») | стр. 55–56 | Удалить: смысл повторяется в Solution и в панели «Without FlatFeed» |
| Причина синтетического каталога в Current limits | стр. 706 | Перенести как решение в `#role`; в лимитах оставить следствие |
| Карточка Learned B | стр. 674–677 | Заменить (см. P1-4) — после P0-4 становится повтором |
| Формулировка продуктовой сути | hero, Solution H2, Built H2, closing | Оставить полную формулировку в Solution H2 и в closing; в Built H2 оставить только то, что добавляет новое (что именно реализовано), без повторного перечисления механизма |

Отдельно: **ничего не удалять из числовых доказательств финального прогона.**
Все четыре агрегатные метрики, семь строк по полям, стоимость `$1.412906` и
сценарий на 15 000 проверок остаются — они защищены `scripts/check_eval_numbers.py`
и §27.

---

## 10. Missing Hiring Signals

Всё перечисленное **уже есть в проекте** и проверяемо; на лендинге отсутствует
или не читается.

| Сигнал | Где подтверждается | Куда поставить |
|---|---|---|
| Асимметрия ошибок / fail-closed matching | `flatfeed/matching.py:280`, `PROJECT_CONTEXT` (Prices, Rooms), `DESIGN_CONTENT_SYSTEM` §28 | My Role, карточка решений A (P0-3) |
| Отказ от скрейпинга как решение о правах на данные | `PROJECT_CONTEXT` (Purpose, Source collection), `DESIGN_CONTENT_SYSTEM` §30 | My Role, карточка C (P0-3), следствие — в Current limits |
| Удаление собственной фичи (guided demo tour) | `DESIGN_CONTENT_SYSTEM` §29, `CURRENT_STATUS` (retired tour callbacks) | My Role, карточка D (P0-3) |
| Минимизация данных и удаление по запросу (`/delete`, подтверждение с названным последствием) | `PROJECT_CONTEXT` (Main Flows → Explicit personal state, Data Model) | My Role, карточка E (P0-3) |
| Диагностика отказа модели и перепроектирование контракта вывода | `eval/AI_QA_FAILURE_ANALYSIS.md` | How AI Fits, шаги 02–03 (P0-4) |
| Целостность оценки: скрытая истина не попадает в промпт, финальный датасет сгенерирован заново и не пересекается с предыдущими входами | `eval/AI_QA_EVAL_PLAN.md` §8, `CURRENT_STATUS` («no overlap with 22 prior input artifacts») | Results, абзац о сложности бенчмарка (P1-1) |
| Операционные ограничители стоимости AI: одна проверка на листинг на версию промпта, дневные лимиты по количеству и деньгам, явный spending guard до платных запросов | `PROJECT_CONTEXT` (AI QA), `eval/AI_QA_EVAL_PLAN.md` §10 | Results, стоимостной блок — одно предложение |
| Matching только по Kaltmiete как доменное суждение | `PROJECT_CONTEXT` (Prices) | My Role, карточка B (P0-3) |

Чего в проекте **нет** и что запрещено добавлять: пользователи, adoption,
retention, бизнес-результат, живое покрытие источников, продакшн-точность,
управление ML-командой, любые числа ранних прогонов на публичных поверхностях.

---

## 11. Final Content Blueprint for Codex

Файлы, которые меняются вместе: `docs/case-study.html`, `CASE_STUDY.md`,
`DESIGN_CONTENT_SYSTEM.md` (§§19, 22, 25 + запись в §34). После изменений
обязательны прогоны из `docs/agent-workflow.md` и
`scripts/check_eval_numbers.py`.

### 1. Header

**Purpose:** читатель за 3 секунды знает, чей это кейс и как связаться.
**Keep:** бренд, подзаголовок «Product case study», навигацию из семи пунктов,
кнопку «View repository».
**Change:** добавить строку автора с контактной ссылкой (P0-1); обновить §19.
**Suggested copy:** `{{AUTHOR_NAME}} · {{AUTHOR_ROLE}} · Contact`

### 2. Problem (hero)

**Purpose:** назвать проблему и одновременно выдать статусные факты о проекте.
**Keep:** кикер `01 Problem`, H1, тултип WBS, первые два предложения lede.
**Change:** удалить третье предложение lede; перенести сюда `dl.case-meta` и
расширить до четырёх пунктов (P0-2); добавить предложение с берлинским
источником и явным статусом допущения (P1-3).
**Suggested copy:** см. блоки в P0-2 и P1-3.

### 3. Solution

**Purpose:** показать изменение маршрута пользователя.
**Keep:** H2-утверждение, панели Without FlatFeed / FlatFeed.
**Change:** удалить `dl.case-meta` (переехал в hero). Больше ничего не трогать —
раздел работает.

### 4. What I Built

**Purpose:** доказать, что продукт существует и что именно реализовано.
**Keep:** четыре шага потока, карусель из семи экранов, две карточки
(User product / System foundation).
**Change:** шаг 02 переименовать в `Normalize every source` (P2-2); H2 не должен
повторять механизм из Solution — оставить акцент на «реализовано», а не на «как
устроено».
**Suggested copy (H2):** `Filter setup, rule-based matching and Telegram
delivery run today as one product.`

### 5. My Role & decisions

**Purpose:** показать продуктовое суждение, а не список обязанностей.
**Keep:** заголовок «I owned the product decisions from problem definition to
evaluated prototype», факт самостоятельного проекта, упоминание кодовых агентов
(§24 — не смягчать и не удалять).
**Change:** сократить `role-note` до двух предложений; добавить блок из 4–5
карточек решений с ценой (P0-3); обновить §22 и §25.
**Suggested copy:** карточки A–E из P0-3 (обязательны A, C, D; из B и E автор
выбирает одну или обе, максимум пять карточек).

### 6. How AI Fits

**Purpose:** объяснить, почему AI поставлен именно в эту точку и как автор туда
пришёл.
**Keep:** H2 «AI flags possible data errors. Fixed rules decide which apartments
match.», три карточки ролей A/B/C, блок «Product boundary».
**Change:** полностью переписать `qa-selection` по P0-4; без чисел из ранних
прогонов; названия моделей убрать отсюда, оставив их только в финальной
конфигурации в Results.
**Suggested copy:** блок из P0-4.

### 7. Results

**Purpose:** предъявить измеренное и честно очертить его границы.
**Keep:** сплит Implemented / Measured, четыре агрегатные метрики, таблицу по
семи полям с объяснением «An overall score can hide a weak spot», «What did not
work», стоимостной блок, ссылки на evidence.
**Change:** удалить `qa-outcome`; убрать третье повторение AI-границы; объединить
`qa-threshold-note` и `qa-stop`; добавить абзац о сложности бенчмарка (P1-1);
добавить одно предложение об операционных ограничителях стоимости в стоимостной
блок.
**Suggested copy (ограничители стоимости, в конец `qa-cost`):**
`Each listing is checked once per prompt version, and the runner enforces daily
count and spend limits before any paid request.`

### 8. What I Learned + Current limits

**Purpose:** показать понимание границ собственных доказательств и следующий шаг
в метриках.
**Keep:** карточки A и C, блок Current limits как единственное место
консолидированных ограничений.
**Change:** заменить карточку B (P1-4); превратить «What I would test next» в
список из четырёх метрик с контр-метрикой (P1-5); из Current limits убрать
атрибуцию фото и причину синтетики (переехала в решения).
**Suggested copy:** блоки из P1-4 и P1-5.

### 9. Closing + Opsqora + contact

**Purpose:** оставить одно запоминающееся утверждение о подходе и дать действие.
**Keep:** «One filter. Timely apartment alerts. …» — формулировка закреплена
§22, не менять.
**Change:** переписать блок соседнего кейса как утверждение о двух разных
AI-границах (P1-6); добавить контактную строку (P0-1).
**Suggested copy:** блоки из P1-6 и P0-1.

### Governance (обязательно в том же изменении)

- `DESIGN_CONTENT_SYSTEM.md` §19: добавить каноническую контактную ссылку в
  шапке.
- §22 (Element rules): обновить правила Problem hero (метаданные + факт-строка),
  My Role (блок решений), How AI Fits (диагностическая версия истории выбора).
- §25: зафиксировать исключение для fail-closed на лендинге («explains a
  specific reader-facing risk»).
- §34: одна запись журнала с датой, причиной и перечнем затронутых поверхностей.
- `CASE_STUDY.md`: все правки зеркалируются по смыслу (§27), не дословно.

---

## 12. Final QA Checklist

После реализации проверить по пунктам:

- [ ] На первом экране без прокрутки видны: имя автора, целевая роль и рабочая
      контактная ссылка (плейсхолдеры `{{AUTHOR_NAME}}`, `{{AUTHOR_ROLE}}`,
      `{{CONTACT_URL}}` заменены реальными значениями).
- [ ] За 45 секунд чтения сверху понятно: что это, для кого, в каком состоянии
      (прототип, синтетический каталог), что измерено и что делал автор.
- [ ] Проблема понятна из H1 и первых двух предложений, без специальных знаний;
      WBS и Kaltmiete глоссированы при первом употреблении.
- [ ] В разделе My Role видно не менее четырёх решений, и у каждого названа
      цена или отвергнутая альтернатива.
- [ ] Каждое решение проверяемо по репозиторию; ни одного мотива, которого нет
      в коде или документации.
- [ ] Роль AI объяснена продуктовой причиной (качество данных парсера), а не
      наличием AI; нигде не утверждается, что модель влияет на матчинг или на
      то, что видит пользователь.
- [ ] История выбора конфигурации содержит отказ и перепроектирование, а не
      только апгрейд модели.
- [ ] На лендинге и в `CASE_STUDY.md` нет ни одного числа из калибровочных,
      development- и ранних frozen-validation-прогонов.
- [ ] `python scripts/check_eval_numbers.py` проходит: четыре агрегатные
      метрики, семь строк по полям, стоимость прогона и сценарий на 15 000
      проверок на месте и совпадают с артефактами.
- [ ] Синтетический статус результатов виден на той же глубине чтения, что и
      сами числа, но повторяется не более трёх раз на странице.
- [ ] Граница «AI не изменяет листинг / не решает о совпадении / не редактирует
      карточку» сформулирована один раз в `#ai` и не дублируется в Results и в
      Current limits.
- [ ] Объяснено, почему бенчмарк даёт высокие числа (одна подсаженная ошибка на
      листинг, прямое противоречие, изоляция скрытой истины).
- [ ] Высота секции Results — не более ~3.5 экранов; общая высота страницы
      сократилась относительно 10 059 px.
- [ ] Чтение только по заголовкам даёт связную историю: проблема → решение →
      что построено → какие решения приняты → где AI и почему → что измерено →
      что не доказано.
- [ ] Ни одного нового утверждения о пользователях, adoption, бизнес-эффекте,
      живом покрытии источников или продакшн-точности не появилось.
- [ ] `CASE_STUDY.md` и `docs/case-study.html` совпадают по смыслу (§27);
      `DESIGN_CONTENT_SYSTEM.md` §§19, 22, 25 обновлены, запись в §34 добавлена.
- [ ] Страница проверена на desktop и mobile, консоль без ошибок, ссылки
      (контакт, репозиторий, evidence, Opsqora) открываются.
