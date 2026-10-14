# Постоянный файловый worker — 28.09.2026

Позднее пользователь установил этот пакет; [проверка установленной службы](remote_worker_live_20260928.md)
подтвердила ACL и offline-допуск ролей, выявила сетевой блокер живого прогона.
Ниже сохранено состояние подготовки **до установки**.

Подготовлена реализация Windows-службы `CognitiveOSWorker` под виртуальной
учётной записью `NT SERVICE\CognitiveOSWorker`. Установка и живой ролевой прогон
ещё не выполнены: доступный процесс Alex не имеет административного токена,
службы пока нет. Это завершённая подготовка развёртывания, не его сертификация.

## Контракт

- `runtime/remote_support_daemon.py`: строгая конфигурация, проверка SID,
  один экземпляр через OS lock, диагностический status, остановка через event.
- `tools/remote_support_service.py`: SCM host; остановка прерывает текущий
  subprocess и прекращает приём новых jobs. Windows Job Object уничтожает
  дочерние процессы при гибели host. Уже созданный claim запрещает повтор.
- `runtime/remote_support_exchange.py`: повреждённый запрос не останавливает
  последующие задания. Отказ runner/записи completion оставляет claim и требует
  разбора. Статус worker не заменяет сверку бюджета контроллером.
- `tools/prepare_remote_worker.py`: закрытый список исходников и зависимостей,
  отдельный Python со stdlib/pywin32, проверка импортов, manifest SHA-256.
  Пользовательский site-packages, настройки COS и секреты не копируются.
- `tools/remote_support_install.py` и `runtime/remote_support_deployment.py`:
  установка только с Windows admin, только в новый `ProgramData/CognitiveOSWorker`,
  без перезаписи существующего service/root. Файлы сверяются до и после копирования.

Корень и exchange доступны worker для чтения; state — для записи. Только
controller, Administrators и SYSTEM могут менять код/config и создавать tickets.
Контроллер отдельно выдаёт worker Modify на source/output каждого задания.
Проверяются reparse points и распространённые групповые разрешения на подмену
родительских каталогов. Это не полный AccessCheck всех возможных доменных групп:
при нестандартных ACL нужна отдельная проверка фактического service token.

Установка сначала запускает службу вручную. Лишь после heartbeat с ожидаемым SID
включаются delayed auto-start и один автоматический restart через30с; дальнейшая
ошибка требует оператора. Частично установленный каталог сохраняется для разбора,
повторная установка его не затирает. Служба работает в контексте отдельной учётной
записи по [модели Windows SCM](https://learn.microsoft.com/en-us/windows/win32/services/service-user-accounts).
Режимы запуска описаны в [документации Microsoft](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create).

## Проверка

Профильные тесты покрывают остановку до claim, прерывание реального subprocess,
сохранение claim, OS lock между процессами, отказ при неверном SID, повреждённые
tickets, manifest и отказ установщика без admin до любых изменений.
Отдельный Windows-тест принудительно завершает host и проверяет смерть его child.
Private-runtime pilot исполнил ticket и корректно остановился, используя только
собранный Python. Это console-проверка под текущим SID, не работа SCM.

Receipts: `artifacts/remote_worker_deployment_20260928/tests.xml`,
`private-runtime-result.json`, `bundle.json`, `verification-summary.json`.
Платных LLM-вызовов0. Исторический расход53225/900000 не менялся.

## Установка и следующий шаг

Подготовленный установочный скрипт лежит в
`artifacts/remote_worker_deployment_20260928/install-worker.ps1`.
Он проверяет закреплённый manifest и каждый файл до запуска bundled Python.
Запускать из PowerShell с правами администратора; повторное общее «да» не создаёт
Windows admin token. Установка не меняет службы шлюза5 или GeminiVM.

После установки: проверить фактический SID службы, ACL отказа доступа к
controller/key/policy, stop/restart и неизменность claim. Затем подготовить
ограниченный ролевой smoke, обеспечив worker отдельный проверенный runtime
с зависимостями COS. В bundle включены зависимости **службы**; зависимости
произвольных заданий и роли не обещаются. До платного smoke — gateway bootstrap,
проверка frozen input и нового общего бюджета строго меньше1000000; прошлые
53225 остаются в исторической серии. Без завершения этих проверок новых баллов
ролям и заявлений об изоляции всего хоста нет.

Остановка/снятие регистрации из административной консоли:
`Stop-Service CognitiveOSWorker`, затем `sc.exe delete CognitiveOSWorker`.
Каталог, claims и receipts сохранять до проверки завершения всех процессов и
сверки бюджета. Удаление службы само по себе не завершает inference accounting.
