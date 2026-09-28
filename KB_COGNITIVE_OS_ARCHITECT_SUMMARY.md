> Датированный отчёт. Текущий статус: [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md); карта исходников: [PROJECT_MAP.md](PROJECT_MAP.md).

# KB Cognitive OS: архитектурное summary

Дата среза: 30 августа 2026 года  
Статус: исследовательский MVP с работающим безопасным ролевым контуром  
Аудитория: solution/software architect, technical lead, reviewer архитектуры

> Актуализация от 10 сентября 2026: ниже сохранён исторический архитектурный срез.
> Оценки 10.0 по contract gates не подтверждают семантическую зрелость ролей или
> перенос на неизвестные дефекты. После пересмотра v1-сертификатов актуальные
> unseen scores составляют 8.0 / 5.0 / 6.0 / 4.0 / 0.0 / 2.0; последний historical
> qualification v2 receipt содержит 2 квалифицированных CLI-дефекта (Granny, Rosbags)
> и 0 library-дефектов; это ещё не ролевой holdout.
> Результаты текущего ревью и дальнейший порядок работ — в
> [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md); текущий operational overview — в README.

## 1. Резюме

KB Cognitive OS представляет собой contract-first систему анализа, декомпозиции и контролируемого изменения программных проектов. Ее задача не сводится к генерации кода: система извлекает знания из существующего корпуса, классифицирует проект, строит архитектурное решение и техническую спецификацию, выбирает ограниченный first slice, готовит патч в sandbox, проверяет поведение и передает результат на review.

Основной архитектурный принцип: исходный код является важным, но не единственным носителем истины. Контракты, политики, role artifacts, evidence trails, capability manifests и результаты проверок также являются authority-артефактами.

Текущий MVP уже демонстрирует жизнеспособность подхода:

- свежая агрегированная readiness-оценка: **10.0/10 по contract gates**;
- полностью MVP-ready: **8 ролей из 8**;
- полный benchmark role pipeline: 8 проектов, artifact/implementation/QA/safety score = 1.0;
- 7 из 8 проектов проходят с первого раза, один проходит bounded recovery;
- handoff loss = 0, неконтролируемых изменений исходников = 0;
- recovery-аудит охватывает 397 Python-файлов;
- реализованы четыре безопасных AST-рецепта декомпозиции mixed-effect функций;
- неизвестные типы проектов и отсутствие безопасного candidate приводят к controlled stop, а не к выдуманному патчу.

Проект уже можно оценивать как сильный инженерный прототип controlled cognitive software engineering pipeline. Термин Cognitive Software Factory пока преждевременен: отсутствуют доказанные production SLO, зрелая permission/security model и повторяемый production pilot. Role-contract gaps закрыты; слабые места переместились во внешний blind transfer, production confidence и семантические границы network/subprocess/stream processing.

Вертикальный контур развития существующего Python-проекта теперь проходит полный безопасный цикл `diagnosis -> option -> decision -> outcome contract -> role chain -> sandbox experiment -> reassessment -> validated project memory`. Неизвестные и поврежденные проекты уходят в research, reselection не может заменить выбранную проблему посторонним удобным target, а исполнение допускается только для allowlisted deterministic reducer и готового implementation delta. FORD остаётся отрицательным контролем: согласованный handoff без поддержанного patch pattern не продвигает memory. Durable run `artifacts/project_development/project_development_20260827T194009645243Z.json` подтвердил `weak_contracts -> insert_required_input_guard`. В `mixed_responsibility` подтверждены четыре bounded subtype: `extract_json_dumps_helper` (`project_development_20260828T021205600886Z.json`), `extract_json_loads_helper` (`project_development_20260828T024351616482Z.json`), `extract_splitlines_helper` (`project_development_20260828T040000419241Z.json`) и `extract_append_mapping_helper` (`project_development_20260828T062025813058Z.json`); соответствующие two-site contrasts, включая mapping report `project_development_20260828T062101648866Z.json`, завершились без patch и memory. У mapping reducer дополнительно подтверждены loop-local conditional variant (`project_development_20260828T070645103118Z.json`), adjacent assignment variant (`project_development_20260828T072338364901Z.json`) и включительная 12-field policy boundary (`project_development_20260828T080840365016Z.json`); external fallback (`project_development_20260828T070723270674Z.json`), temporary reuse (`project_development_20260828T072433082449Z.json`) и 13-field over-limit (`project_development_20260828T080915669163Z.json`) остаются без patch и memory. Simple-loop authority подтверждена report `project_development_20260828T083944554908Z.json`, а nested-loop contrast `project_development_20260828T084003587919Z.json` блокируется. Reducer matcher требует ровно один prepared sandbox candidate и сохраняет попытки в PatchPackage. Контур уже не только planning/decision layer, но это зрелость четырёх узких boundary patterns с четырьмя проверенными mapping variants, а не общей архитектурной декомпозиции. Source apply и перенос результата в общую KB запрещены.

Failed development experiment теперь имеет явный ролевой выход через `ProjectDevelopmentExecutionFeedback`: matcher uncertainty возвращается по цепочке `Researcher -> Architect`, verification failure — к Architect для `needs_replanning`, неизвестная причина — в `controlled_stop`. Автоматический retry и расширение scope запрещены. Durable report `project_development_20260828T090705601690Z.json` подтверждает research feedback с reducer attempts и memory `not_promoted`; validated contrast `project_development_20260828T090747254502Z.json` закрывается как `completed` без лишнего handoff.

Research feedback теперь потребляется read-only цепочкой `Researcher -> Architect`: первый выпускает `ProjectDevelopmentResearchHypothesis`, второй — типизированное решение `ProjectDevelopmentArchitectFeedbackDecision` со значением `replan | research_more | controlled_stop`, агрегированное в `ProjectDevelopmentFeedbackContinuation`. Nested-loop report `project_development_20260828T093240287559Z.json` подтверждает source-backed hypothesis `nested_loop_mapping_boundary` (`0.93`) и `replan` при неизменном target; executor не перезапускается, Developer не вызывается, memory остаётся `not_promoted`. Validated contrast `project_development_20260828T093325940127Z.json` не создаёт лишних ролевых артефактов.

Architect materializes `replan` в отдельный `ProjectDevelopmentReplanRevision`: это revision `+1` исходных `ProjectDevelopmentDecision` и `ProjectDevelopmentOutcomeContract`, а не новый запуск реализации. Selected option, target и required checks сохраняются; меняются только planning adjustment и ожидаемый исследовательский outcome. Policy жёстко запрещает Developer handoff, Executor rerun, source changes и execution authorization. Report `project_development_20260828T100823826409Z.json` подтверждает planning-only revision `2` и неизменный source; validated contrast `project_development_20260828T100905579561Z.json` оставляет revision отсутствующей.

Из planning revision формируется `ProjectDevelopmentBoundedExperimentProposal`, после чего отдельный `ProjectDevelopmentBoundedExperimentAdmission` проверяет primary target, один immutable allowlisted contrast, evidence budget, action allowlist, stop conditions и нулевой execution budget. Admission разрешает только embedded read-only Researcher и не запускает внешнюю role chain, Developer или Executor. Contrast path, digest, AST facts и validated report identity входят в admission/evidence boundary.

Embedded Researcher исполняет только допущенную read-only часть proposal и возвращает `ProjectDevelopmentBoundedExperimentEvidence`; Architect отвечает `ProjectDevelopmentArchitectEvidenceDecision`. Nested-loop negative и validated simple-loop positive теперь оба имеют source AST authority и неизменные digest. Эта пара достаточна для human-reviewed bounded implementation candidate, но не для KB promotion и не для автоматического execution. Report `project_development_20260828T113702427711Z.json` подтверждает paired evidence и `evidence_accepted`; validated contrast `project_development_20260828T113733891395Z.json` не запускает continuation.

Materialization candidate теперь требует цепочку `ProjectDevelopmentImplementationApprovalRequest`, внешнего `ProjectDevelopmentHumanApprovalDecision` и `ProjectDevelopmentImplementationApprovalValidation`; только затем возникает `ProjectDevelopmentBoundedImplementationCandidate`. Binding включает proposal ID и canonical evidence digest. Candidate имеет `approved_not_executable`: approval не разрешает Developer, Executor, source changes или memory promotion. Report `project_development_20260828T115407964184Z.json` фиксирует pending request и отсутствие candidate; approved report не создавался без отдельного человеческого решения. Validated contrast `project_development_20260828T115440020888Z.json` оставляет approval layer `null`.

Design layer теперь полон: `ProjectDevelopmentImplementationDesignRequest -> ProjectDevelopmentImplementationDesignAdmission -> ProjectDevelopmentImplementationDesign -> ProjectDevelopmentImplementationDesignValidation`. Явно вызванный Architect обязан сохранить candidate/proposal/evidence/target/source identity и заполнить только interface boundary, transformation steps, acceptance mapping и rollback strategy. ImplementationPlan, patch и executor task отклоняются рекурсивно; automatic role invocation, execution и memory promotion запрещены. Исторические controls `project_development_20260828T120640182121Z.json` и `project_development_20260828T120712767813Z.json` сохраняют соответственно pending и absent continuation paths. Current report `project_development_20260831T080044961164Z.json` фиксирует design как `accepted_not_executable` с canonical digest и останавливается перед отдельной implementation authorization.

Следующая рольовая граница также материализована: `ProjectDevelopmentImplementationAuthorizationRequest -> ProjectDevelopmentImplementationAuthorizationDecision -> ProjectDevelopmentImplementationAuthorizationValidation -> ProjectDevelopmentAuthorizedImplementationResult`. Human approval связан одновременно с design/evidence и relevant execution-policy digest, поэтому изменение overlay или plugin allowlist инвалидирует старое решение. Первый run `authorized_implementation_20260831T081035446426Z.json` применяет strict exception reconstruction operator только в sandbox, проходит targeted replay и полный pytest-socket suite (`103 passed, 9 skipped`), stub/scope/source-invariant gates. Это первая supervised verified transformation (`1/3`), но autonomous transformations остаются `0/3`, а operator не продвинут в active KB/global reducer catalog.

Второй supervised transfer завершён на `urllib3.LocationParseError`. Он важнее простого повторения первого кейса: upstream type-only test был зелёным, но semantic evaluator обнаружил потерю state fidelity. Matcher научился учитывать локально унаследованные reconstruction hooks и перестал считать isort дефектом. Новый design-bound режим оператора переиспользует только доказанные direct state assignments и fail-closed останавливается при несохранённом constructor input. `authorized_implementation_20260831T110602578287Z.json` подтверждает semantic equality, targeted `17 passed`, bounded regression `19 passed`, single-file sandbox scope и unchanged source. Ledger равен `2/3`; это ещё не основание для autonomous activation или KB promotion.

Третий supervised transfer завершён на `python-redmine.UnknownError`. Direct semantic probe подтвердил дефект replay: `status_code` сохранялся, но message получал двойной prefix. Тот же design-bound `reuse_direct_assignments` recipe добавил только `__reduce__` в sandbox target. `authorized_implementation_20260831T115835185733Z.json` подтверждает semantic equality, targeted `1 passed`, bounded regression `405 passed`, no stubs, single-file sandbox scope и unchanged source. Cleanup runner-а теперь удаляет sandbox-only `build/lib`, созданный локальной wheel-сборкой, до scope gate. Ledger равен `3/3`; supervised threshold закрыт, но autonomous activation, source apply и KB promotion остаются отдельными будущими gates.

Добавлен явный promotion-readiness gate для этого семейства. `exception_pickle_promotion_readiness_20260831T124021424040Z.json` агрегирует три supervised verified reports, audit boundary, один autonomous shadow report и safety invariants: результат `eligible_for_promotion_review`, но direct promotion из readiness запрещён. Первый pytest-socket кейс помечается как `legacy_pickle_native_replay`, потому что его report предшествует отдельному semantic verifier; новые supervised кейсы требуют явный semantic check.

Independent holdout transaction, autonomous shadow run и evaluator review вынесены в отдельные gates. `exception_pickle_holdout_transaction_20260831T124242422603Z.json` подтверждает 586 применимых кандидатов в 229 независимых проектах, focused regression `13 passed` и Config Doctor `44/44`, без source apply, KB promotion или autonomous activation. `exception_pickle_autonomous_shadow_20260831T123815742912Z.json` автономно выбирает `anyio.BrokenWorkerInterpreter`, строит sandbox patch и проходит compile/scope/source/stub gates плюс project-native semantic replay через import и pickle roundtrip. `exception_pickle_independent_evaluator_20260831T125714581827Z.json` подтверждает independence и no-mutation invariants.

Manual promotion transaction `exception_pickle_promotion_transaction_20260831T132156422950Z.json` после explicit approval прошла `20` focused regression tests и Config Doctor `45/45`, активировав `knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json`. Boundary interpreter теперь потребляет этот catalog как active overlay: matching boundary получает `status=active` и `validated_active` operator authority. Active operator проходит через proposal, candidate и design request как suggested recipe; design validation блокирует подмену recipe. Это повышает статус узкого pattern-а до `validated_active`, но не расширяет execution authority: source apply, generated stubs, existing reconstruction hooks и automatic runtime mutation запрещены.

Post-promotion reuse теперь проверен отдельным active-application контуром. Текущий active application ledger: `applied=178`, `blocked=414`; последние additions включают `maxteabag__sqlit / CredentialsStoreError`, шесть `ctripcorp__flybirds` exceptions, `setuptools / LinkOutsideDestinationError`, `calf-ai__calfkit-sdk / ToolRetryError`, два `leptonai__leptonai` API errors, два `aiohttp` connector errors, `mercadopago__sdk-python / InvalidWebhookSignatureError`, `eddyzzl__marvis-risk-agent / IllegalTransition`, три CPython `tarfile` destination/link errors, `not-sekiun__consortium / AgentGeneratorBuildStepOverridesFinalMethodError`, `abhinavsingh__proxy-py / ProxyConnectionFailed`, `dj-bolt__django-bolt / ComponentNameCollisionError`, `pybotters__pybotters / OutOfBoundsError`, два `shy3130` tickflow `CapabilityDenied` targets, два `nats-io__nats-py` client errors, `nerevu__riko / PipelineStateError`, `withceleste__celeste-python / UnsupportedParameterError`, `reloadware__reloadium / RedefinedVarError`, два `benoitc__gunicorn` stash errors, `vonage__vonage-python-sdk / PartialFailureError`, `software-mansion__starknet-py / OutOfBoundsError`, `reloadware__reloadium / NoTypeError`, `supabase__supabase-py / StorageApiError`, `disnakedev__disnake / MaxConcurrencyReached`, `mosaik__mosaik / InvalidNextStepTypeError`, `nextcord__nextcord / MaxConcurrencyReached`, два `rapptz__discord-py` command errors и `treeverse__dvc / BaselineMismatchError`. Blocker taxonomy отделяет constructor replay mismatch, dependency/import replay unavailable, import failure, unsupported semantic sample, behavior mismatch, sandbox-copy failure и static patch shape. `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` классифицирует latest-blocker frontier в 146 cases; sample-supported readmission frontier равен 0, class-state contract research выделен в 6 cases, а priority lane остаётся import/dependency isolation на 25 cases. Import-isolation summary разделяет эти 25 cases на dependency unavailable 9, import failed 5, attribute-base/metaclass risk 10 и один dependency-heavy sample-supported case; direct-file replay preferred для 14 cases; missing-import kinds: external dependency 11, project-local dependency 2, stdlib symbol compat 2. Top missing imports: теперь только `librt` имеет count 2; `authlib`, один `yarl` target и один `voluptuous` target закрыты, а failed report-only probes пометили `aiohttp`, `async_timeout`, `sqlalchemy`, `app` и `common` как diagnosis-required вместо direct-write clusters. Source-aware sliced-string/rendered-body materializer исправил replay для `line[:100]` и REST `body`; `topics`, `domain`, `service`, `bucket`, string-membership, `.lower()`, source-backed attribute-object samples, `.value`, bounded nested data objects, recursive named-object replay, CPython `frozendict` compatibility, `types.GenericAlias` replay shim и suffix-based `*_filepath` string samples поддержаны. Replay subprocess теперь добавляет sandbox import paths только после stdlib bootstrap, поэтому локальный `src/types.py` не ломает compatibility shims. Active application CLI сохраняет bounded saturation controls: replay blocker budgets, `--only-readmission-frontier`, `--only-import-isolation-frontier`, `--import-isolation-missing-kind`, `--import-isolation-batch-profile dependency_heavy_direct_file`, `--import-isolation-cluster`, `--maximum-accepted-applications`, `--readmission-subtype`, precheck-aware ordering, patchability ordering, dependency-light ordering, per-project static-patch/replay blocker budgets и настоящий no-ledger-update dry-run без `--write`, плюс `--write-report` для сохранения probe evidence без ledger mutation. Latest project-local exact-target writes accepted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError` и `astronomer__agents / NotFoundError` after a report-only project-local batch probe. Report-only probes теперь сохраняются через `--write-report` без ledger mutation; сохранённые probes пометили `aiohttp`, `async_timeout`, `sqlalchemy`, `app` и `common` как failed direct-file probes, а planner report `exception_pickle_import_cluster_planner_20260903T065218069738Z.json` помечает следующий `unknown:attribute_base_metaclass_risk` cluster как `not_batch_ready` с `class_state_contract_research_before_replay`. Failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` классифицирует 2 latest failed probes и теперь рекомендует `constructor_state_contract_research`; behavior-contrast, reprobe и replay-capture repair lanes закрыты текущим циклом. Object-contract audit/admission `exception_pickle_object_contract_audit_20260902T095949529132Z.json` / `exception_pickle_object_contract_admission_20260902T100010126192Z.json` закрыли source-backed object-materializer хвост до нуля в текущем BI. Derived-message и derived-import audits теперь пустые. LLM допускается только как advisory через `--use-l45-llm`, без source apply, KB promotion или замены deterministic evidence. Это уже не единичный smoke, а повторное использование active KB на независимых holdout-проектах; source-apply authority всё ещё отсутствует.

Накопленная boundary-семантика кристаллизована в staged KB, а не продвинута автоматически. `project_development_boundary_profiles.json` задаёт declarative predicates, hypothesis и evidence rules; `project_development_source_contrasts.json` отделяет source provenance от policy; `project_development_boundary_interpreter.py` исполняет закрытый fail-closed язык сопоставления. Frozen corpus содержит шесть source-backed cases, два blind cases и шесть lineages, но `kb_promotion_evidence=false` сохраняется до независимых reports и no-regression transaction. В матрице ролей current lane ограничен `cli_local_tool` и `library_pure_transform` с target `9.7`; все широкие типы помечены как обязательный deferred lane с тем же будущим target.

Historical foundation-ячейка ниже цели, `SpecWriter x cli_local_tool = 9.6`, закрыта общим evidence rule, а не project-specific profile; исходное воспроизведение и исправление сохранены в `role_foundation_min_field_trial_20260828T130714421779Z.json`. Свежие multi-project и независимые `black`/`cattrs` прогоны подтверждают foundation chain на `9.7/9.7/9.7+`. Downstream `10.0` рекалиброван: это bounded derived-contract score, а не универсальная зрелость Implementer/Tester/Reviewer. Матрица `role_project_type_evaluation_20260828T134957310326Z.json` оставляет эти ячейки usable до трёх project-native transformations.

Diagnostic authority также рекалиброван. Новый AST/token-aware `SourceIncompletenessEvidence` различает interface/marker stubs, deliberate exception suppression, declared future work и ambiguous stubs; синтаксис, TODO и security-shaped filenames остаются observations до target-bound executable/user failure. High/medium risks требуют scanner/runtime/test authority. Comfy CLI report `project_development_20260828T173504992818Z.json` подтверждает fail-closed результат: `CustomNode` TODO, auth/oauth и broad-function сигналы сохранены, но issue не создан, role chain не запущен, source и KB не изменены. Recognition artifact теперь отдельно публикует effective product identity и scope внутреннего archetype.

Для output Programmer действует отдельное более строгое правило: `GeneratedFunctionStubAdmission` сравнивает AST оригинала и patch sandbox и запрещает новые функции-заглушки либо замену реализации на `pass`, `...`, `raise NotImplementedError` или `return NotImplemented`. Старые interface stubs остаются наблюдениями, но созданная патчем заглушка является отрицательным результатом независимо от зелёных тестов: native replay, validated memory, KB promotion и maturity credit блокируются.

Flake8 historical CLI case доведён через multi-interpreter intake под Python `3.12.9` без silent fallback. Ordered project/tool overlays, installed entry-point fallback, sibling basetemp и закрытая pytest plugin autoload boundary устранили environment noise. Processor-level witness, адаптированный из upstream regression, получил unique assertion-causal target через generic tuple-unpack/static-method matcher. `adjust_fstring_middle_brace_offsets` прошёл targeted `1 passed`, полный suite `465 passed`, generated-stub gate и source invariant. Третий независимый CLI lineage получен на isort: `guard_trailing_backslash_index` закрыл upstream regression (`1 passed`) и полный локальный suite (`548 passed, 5 skipped`). Target-scoped admission снял только агрегатный риск `stateful` для единственной повторяемой AST-проверенной функции; network/subprocess/concurrent риски остаются неотменяемыми. Матрица `artifacts/field_trials/role_project_type_evaluation_20260830T104433802113Z.json` подтверждает CLI `3/3`, а transaction `artifacts/role_promotion/project_native_repair_promotion_20260830T104614251822Z.json` активировала три CLI-паттерна после `167` regression tests и Config Doctor `44/44`.

Project-native contour теперь подтверждён первым реальным развитием внешнего проекта. Intake дважды воспроизвёл `platformdirs` failure `tests/test_api.py::test_no_ctypes[user_data_dir]`, связал его с единственным target `src/platformdirs/windows.py:get_win_folder_from_registry` и выдал failure-specific reducer `fallback_missing_registry_to_env`. Отдельный `failure_repair_contract` провёл target через Architect -> SpecWriter -> Implementer -> Tester -> Reviewer без подмены extraction-кандидатом. Sandbox patch закрыл исходный test (`1 passed`) и полный suite (`895 passed, 79 skipped`), исходный digest не изменился; report `project_development_20260829T025515649054Z.json` имеет `experiment_validated`, а memory authority получена только после native verification.

Матрица `role_project_type_evaluation_20260829T035206805890Z.json` учитывает два независимых project-native outcome. Второй контур на `marshmallow` связал assertion-only failure с `src/marshmallow/utils.py:from_timestamp`, синтезировал `normalize_timestamp_range_error` и прошёл исходный test (`1 passed`) и полный suite (`1184 passed`) без изменения source corpus. Для `library_pure_transform` downstream scores равны `Implementer 9.8`, `Tester 10.0`, `Reviewer 9.8`, но maturity остаётся `usable`: native count `2/3`. Новый assertion-causal matcher идёт от `assert` через локальные присваивания и допускает только единственный production call; test observers, external dependencies и unresolved instance calls остаются диагностикой без patch authority. На Typer он дважды воспроизвёл formatting failure, но исключил `normalize_rich_output` и `runner.invoke`, поэтому CLI остаётся `0/3`. Явные install hints и `ModuleNotFoundError` теперь всегда dependency blockers; ложные candidates `validators` и `markdown-it-py` закрыты. Clean baselines не засчитываются как transformation evidence. Оба подтверждённых repair-паттерна сохранены в staged KB `project_native_failure_repair_patterns.json`, promotion запрещён до третьей независимой native-трансформации.

Промежуточная эволюция boundary сохранена в evidence trail: planning admission `project_development_20260828T104947964126Z.json` / `project_development_20260828T105018631041Z.json` и policy-backed read-only evidence `project_development_20260828T111911887620Z.json` / `project_development_20260828T111943104093Z.json`. Эти reports исторические и не заменяют текущую paired-source authority.

## 2. Целевая архитектура

Система состоит из семи логических слоев.

1. **Project intake и scope control.** Определение active root, отделение active core от tests, generated, packaged copies, legacy noise и dirty portfolio. Для неизвестного архетипа запускается отдельный lifecycle накопления доказательств.
2. **Knowledge и policy layer.** Декларативные project archetypes, contract families, semantic target profiles, ranking policies, side-effect policies и promotion thresholds.
3. **Contract Registry и Capability Registry.** Разделение между доступными capabilities и разрешенными runtime-контрактами. Lifecycle capability учитывает active/degraded/quarantined/rebuilding/retired.
4. **Role pipeline.** Project Analyzer → Architect → Spec Writer → Implementer Planner → Tester (`TestPlan`) → Programmer Executor (`PatchPackage`/`TestResult`) → Reviewer. Researcher подключается условно при unknown archetype, knowledge gap или недоказанной semantic boundary.
5. **Sandbox execution.** Патчи сначала создаются в изолированной копии проекта. Применение к source tree требует явного флага, human approval, совпадения digest и source precondition.
6. **Verification и recovery.** Контрактные, структурные и differential-проверки; rollback snapshot; normal Architect re-entry после bounded recovery.
7. **Evaluation и self-improvement.** Curriculum, blind/external corpora, role×project-type heatmap, red-team gates, evidence-backed promotion и запрет автоматического обучения на собственном неподтвержденном выводе.

## 3. Зрелость ролей

Свежий `Role MVP Readiness v0.1` дает следующую картину. Баллы ниже являются readiness по проверяемым gate, а не субъективной оценкой интеллекта роли. `Maturity` означает изученность role×type области, `readiness` - прохождение независимых сквозных gate, `confidence` - надежность конкретного вывода. Эти оси не взаимозаменяемы.

| Роль | Балл | Статус | Основной вывод |
|---|---:|---|---|
| Project Analyzer | 10.0/10 | MVP-ready | Уверенно строит source-backed карту и сохраняет read-only режим |
| Architect | 10.0/10 | MVP-ready | Проходит local, external и GitHub curriculum; сохраняет архитектурные ограничения |
| Spec Writer | 10.0/10 | MVP-ready | Формирует связанный с ADR и source evidence исполнимый контракт |
| Implementer Planner | 10.0/10 | MVP-ready | External evidence handoff закрыт, writable scope остаётся ограниченным selected target |
| Programmer Executor | 10.0/10 | MVP-ready | Переоценен на зрелом Planner input; sandbox, verification и rollback gates зелёные |
| Tester | 10.0/10 | MVP-ready | Полный local/external/GitHub и pipeline QA контур |
| Reviewer | 10.0/10 | MVP-ready | Проходит local/external/GitHub и шесть adversarial artifact mutations |
| Researcher | 10.0/10 | MVP-ready, bounded | Измеряет unknown lifecycle и semantic hypotheses; production confidence остаётся низкой до внешнего blind-корпуса |

Следующий приоритет: **blind executable transfer → bounded pilot → semantic boundary evidence**. Все роли следует удерживать regression-наборами, а не улучшать без конкретного evidence gap.

## 4. Зрелость по типам проектов

Последняя полная role×project-type матрица содержит 666 наблюдений из 111 отчетов:

- 79 измеренных известных role×type ячеек;
- 44 ячейки классифицированы как mature, 34 как usable и одна как weak;
- 24 ячейки корректно помечены not applicable;
- foundation-часть narrow lane mature на `9.7+`, downstream-часть ожидает project-native evidence;
- не измерены только `Project Analyzer × unknown_new_archetype` и `Researcher × unknown_new_archetype`.

Известный зрелый контур охватывает:

- CLI и локальные инструменты;
- библиотеки и чистые transforms;
- Web/API endpoint transforms;
- fixture-backed provider adapters;
- plugin/package/codegen/build primitives;
- tabular/data pipelines;
- scientific compute;
- ML inference;
- ML training/checkpoint projects;
- async workers и schedulers;
- stateful/SQLite transitions;
- filesystem/subprocess/archive I/O;
- LLM и multi-agent orchestration;
- workspace/dirty portfolio intake в пределах применимых ролей.

Оба narrow repair lane теперь прошли отдельные promotion transaction и удерживаются регрессией; это активирует только три pure-transform и три CLI failure patterns, а не общую автономию изменения Python-проектов. Следующая последовательность переходит к deferred lane: `SpecWriter -> Architect -> Project Analyzer` для `framework_plugin_build`, затем `workspace_portfolio` и оставшиеся широкие SpecWriter-ячейки. Параллельно target-scoped admission требует blind contrasts: stateful project допускается лишь для повторяемого единственного target без прямых внешних эффектов; network, subprocess, concurrent и provider risks не снимаются.

## 5. Работающий recovery-контур

Если Architect не находит безопасного source-backed candidate, система сохраняет controlled stop и запускает:

`Reviewer → Researcher → Architect → Developer → Tester → Architect`

Developer не получает право на изменение source автоматически. Сначала создается sandbox patch package, затем Tester выполняет differential verification, после чего обычный Architect gate должен выбрать новый source-backed candidate. Применение возможно только при human approval, связанном с точным patch digest; при неуспешной post-apply проверке выполняется rollback.

Реализованы четыре узких рецепта:

- извлечение `normalize_record` из append-mapping loop;
- извлечение `serialize_json` из filesystem write boundary;
- извлечение `parse_json` из filesystem read boundary;
- извлечение `split_lines` из `splitlines()` boundary.

Все рецепты fail-closed: неоднозначные или множественные границы не патчатся. Корпус проекта при field trials остается неизменным.

## 6. Неавтоматизируемые границы

AST-аудит отделяет syntactic extraction от semantic/security boundary research. Сейчас автоматическая recipe-полоса закрыта: все подтвержденные безопасные синтаксические кластеры имеют реализацию.

Researcher-полоса содержит четыре bounded hypotheses:

1. `request_mapping_inside_network_boundary`: отделить pure request builder от transport policy, сохранив authentication, timeout, retry и encoding.
2. `network_response_parse_inside_effect_boundary`: отделить decoding/schema validation от status/error/encoding semantics транспорта.
3. `dynamic_command_inside_subprocess_boundary`: отделить command builder без ослабления shell, path, environment и exit-code controls.
4. `parse_structured_stream_inside_io_boundary`: проверить возможность materialization без изменения CSV dialect, newline mode и timing ошибок итератора.

Architect gate для этих гипотез намеренно запрещает handoff в Developer до source review, независимого holdout и differential success/failure fixtures.

## 7. Сильные стороны

- Последовательная contract-first архитектура и typed role artifacts.
- Хорошее разделение планирования, исполнения и проверки.
- Read-only анализ внешних проектов и sandbox-first patching.
- Явные controlled stops вместо оптимистичного продолжения.
- Source-backed traceability от ProjectMapReport до ReviewFindings.
- Декларативные policy/KB каталоги и Config Doctor против configuration drift.
- Разделение known archetype и unknown lifecycle.
- Evidence-backed promotion вместо обучения на собственных ответах.
- Differential verification и digest-bound human approval для recovery patches.

## 8. Ограничения и риски

### Критичные для следующего этапа

- **Pilot admission заблокирован.** Не хватает двух новых blind executable-transfer проектов из двух независимых lineages; остальные pilot checks зелёные.
- **Researcher production confidence низкая.** Текущий score доказывает bounded planning/quarantine, но не точность внешнего исследования на новых доменах.
- **Role readiness насыщена.** 8/8 означает прохождение текущих gates и требует дальнейшего adversarial усложнения, а не трактовки как абсолютных 10/10.
- **Network/subprocess/stream boundaries остаются исследовательскими.** Автоматический патч здесь был бы преждевременным и потенциально опасным.

### Архитектурные

- Возможна насыщенность метрик и fixture overfitting: историческая матрица показывает 79/79 mature, но свежий role report выявляет три незрелые роли.
- Система преимущественно Python-centric; unsupported primary language корректно блокируется, но полноценной полиязыковой архитектуры пока нет.
- Semantic recognition все еще сочетает declarative profiles и AST heuristics; alias/data-direction matcher улучшен, но полноценного interprocedural dataflow нет.
- Production security model требует отдельной threat model для secrets, network allowlists, process execution и supply-chain dependencies.
- Нет доказанного long-running operational SLO: latency, resource ceilings, flaky dependency handling, artifact retention и concurrent sessions.
- Один parse failure из 397 файлов в последнем recovery-аудите требует отдельной классификации parser compatibility, а не молчаливого игнорирования.

## 9. План развития

### Этап 1. Handoff integrity: завершен

Горизонт: ближайшие 2-4 недели.

- добавить Reviewer artifact-mutation corpus: ADR/Spec drift, потеря acceptance requirement, target substitution, false-green TestResult и скрытый side-effect breach;
- устранить три Reviewer curriculum gaps и подтвердить исправление на blind-cases;
- закрыть единственный external backlog Implementer Planner;
- повторно оценить Programmer Executor после готовности planner input;
- включить Researcher в агрегированный readiness-report;
- добавить blind unknown-archetype corpus минимум из трех подтвержденных проектов;
- зафиксировать разницу между readiness score, maturity score и production confidence.

Результат: Planner/Executor handoff закрыт, Reviewer mutation corpus проходит 6/6, Researcher включен в агрегат, handoff loss остаётся нулевым. Внешняя blind-проверка перенесена в отдельный transfer gate и не подменяется внутренним score.

### Этап 2. Семантические boundary experiments: gate реализован, evidence pending

Горизонт: 1-2 месяца.

- провести holdout-эксперименты для request builder и response decoder;
- определить typed transport-neutral DTO;
- проверить success/error/retry/auth invariants;
- разработать process command contract с shell/path security policy;
- определить materialized stream contract с сохранением dialect/newline/error timing;
- допускать Developer recipe только после Architect evidence gate.

Текущий verdict: все четыре family имеют `evidence_required`, Developer handoff запрещён. Критерий выхода: минимум два независимых проекта/lineage, holdout и failure-path differential для каждой допускаемой boundary family.

### Этап 3. Blind transfer и bounded pilot: активный

Горизонт: 2-4 месяца.

- усилить async/distributed, stateful/database, ML checkpoint и LLM-agent holdouts;
- расширить dirty portfolio и damaged source-tree scenarios;
- добавить parser compatibility taxonomy для новых версий Python;
- внедрить property-based и metamorphic verification для deterministic transforms;
- сохранять mutation testing Reviewer и расширить его на Tester;
- провести два новых blind executable-transfer проекта из независимых lineages для открытия pilot admission;
- провести cross-corpus regression без повторного использования training fixtures.

Текущий operational срез уточнил порядок работ. Два rework-case первого batch закрыты общими matcher-правилами и стали executable callable, но независимый пяти-owner corpus дал 0/5 first-pass: четыре nominal/protocol fixture gap и один корректный profile stop. Human review подтвердил `rework=4`, `stop=1`; `pilot_telemetry_20260827T112019244368Z.json` фиксирует пять валидных решений, pending `0`, source changes `0`, handoff loss `0`. Поэтому ближайшая последовательность идет по цепочке ролей: Architect/SpecWriter добавляют executability evidence в выбор кандидата, Programmer Executor развивает общие protocol materializers, после чего проводится новый unseen confirmation.

Критерий выхода: pilot admission `eligible`, отсутствие regression в зрелых ячейках и подтвержденная переносимость новых контрактов на независимый корпус. Первый профиль ограничен pure/filesystem-read/sandbox сценариями; source apply запрещён.

### Этап 4. Production operating model

Горизонт: 4-6 месяцев.

- threat model и permission model для filesystem/network/subprocess/secrets;
- durable execution sessions, resume/replay и artifact retention policy;
- operational telemetry: latency, failure rate, rollback rate, human rejection rate;
- capability lifecycle automation с quarantine и controlled promotion;
- multi-user approval/audit trail;
- pilot на ограниченном классе реальных проектов с обязательным human review.

Критерий выхода: определенные SLO/SLA, воспроизводимый rollback, auditability и ограниченный production pilot без unrestricted autonomous writes.

## 10. Перспективы

Наиболее реалистичные направления продукта:

- архитектурный аудит и построение карты legacy/dirty проектов;
- безопасное выделение reusable capabilities из существующего кода;
- генерация ADR/TechnicalSpec с source traceability;
- controlled modernization с sandbox patching и differential verification;
- проектный knowledge base, который накапливает подтвержденные contract families;
- human-supervised software factory для повторяемых типов изменений;
- foundation для дальнейшего multi-language и organization-specific Cognitive OS.

Стратегически сильная сторона проекта не в обещании полной автономности, а в способности постепенно расширять область автоматизации, не теряя controlled stop, evidence trail и право Architect/человека остановить изменение.

## 11. Вопросы для архитектурной оценки

1. Достаточно ли четко разделены Knowledge, Contract Registry и Capability Registry, или часть policy authority дублируется?
2. Следует ли оставлять Implementer Planner и Programmer Executor отдельными ролями на долгом горизонте?
3. Достаточен ли текущий digest-bound human approval как trust boundary для pilot deployment?
4. Где должна проходить граница между AST matcher, interprocedural analysis и LLM semantic interpretation?
5. Какие network/process contracts допустимо автоматизировать, а какие должны навсегда остаться human-gated?
6. Как нормировать maturity metrics, чтобы избежать насыщения и fixture overfitting?
7. Нужен ли event-sourced artifact store для полноценного replay и concurrent role sessions?
8. Какой первый production use case имеет лучший баланс ценности и ограниченного blast radius?

## 12. Evidence

- `COGNITIVE_OS_TECHNICAL_BASELINE.md`: нормативная инженерная спецификация.
- `config/role_project_type_evaluation.json`: роли, типы проектов, risk profiles и promotion thresholds.
- `artifacts/field_trials/role_mvp_readiness_20260827T062723091738Z.json`: свежая readiness-оценка ролей.
- `artifacts/field_trials/role_project_type_evaluation_20260828T134957310326Z.json`: текущая полная role×project-type матрица с разделением derived и project-native evidence.
- `artifacts/field_trials/recovery_pattern_audit_20260827T061321560930Z.json`: AST-аудит recovery patterns.
- `artifacts/field_trials/recovery_boundary_research_20260827T061321562931Z.json`: Researcher hypotheses и Architect gate.
- `config/artifact_contracts.json`: API-контракты role artifacts.
- `config/patch_synthesis_policy.json`: разрешенные deterministic patch recipes.

## 13. Итоговая оценка

KB Cognitive OS имеет убедительную архитектурную основу и хорошо развитый безопасный контур анализа, спецификации и тестирования. Система уже сильнее обычного code-generation pipeline за счет контрактов, role separation, evidence trails, recovery и controlled application.

Ближайшая архитектурная цель: не расширять количество эвристик, а довести Reviewer, Implementer/Executor handoff и Researcher evidence model до того же уровня, который уже достигнут Analyzer/Architect/SpecWriter/Tester. После этого проект готов к ограниченному human-supervised pilot на deterministic и filesystem-read project types.

## 14. Historical pre-fix outcome, 2026-08-29

Третий независимый project-native outcome получен на Deepmerge без искусственной порчи production source: полный parent tree `f4822dec` дополнен только исходным regression-тестом из read-only fix commit `d180db58`. Intake сохранил параметризованный nodeid `[zero int]`, связал assertion с единственным class-method target и классифицировал `falsy_primitive_empty_contract`. Цепочка `Architect -> SpecWriter -> Implementer -> Tester -> Reviewer` выбрала один bounded reducer; sandbox прошел targeted `1 passed` и полный suite `34 passed`, исходный digest не изменился.

Узкий `library_pure_transform` evidence ledger теперь равен `3/3`, что подтверждает зрелость `9.7+`, но не универсальные `10/10`. CLI остается `0/3`, широкие типы проектов остаются deferred lane. KB repair catalog достиг численного порога, однако automatic promotion выключен до явной no-regression транзакции.

## 15. Promotion and first CLI outcome, 2026-08-30

Каталог трёх pure-transform repair patterns прошёл явную атомарную promotion-транзакцию: `126` regression tests, Config Doctor `43/43`, все шесть role cells mature, три независимых lineage и ноль изменений исходных проектов. Evidence: `artifacts/role_promotion/project_native_repair_promotion_20260830T000805901553Z.json`. Это активирует только узкую подтверждённую область, а не общий режим автономного редактирования Python-проектов.

Следующий тип начат с исторического Autoflake holdout. Parent commit `e2109ba9` с оригинальным regression-тестом из read-only fix commit `aefc058d` дал повторяемый `IndexError` в `extract_package_name`. Cognitive OS самостоятельно провела intake, diagnosis, role handoff, выбрала reducer `guard_incomplete_import_tokens`, проверила targeted `1 passed` и full suite `172 passed`, затем подтвердила отсутствие изменений source tree. CLI ledger теперь `1/3`; pattern хранится в отдельном staged-каталоге и не может быть активирован до ещё двух независимых CLI lineages. Пересчитанная role-by-project matrix: `artifacts/field_trials/role_project_type_evaluation_20260830T002347353942Z.json`.

Последовательность развития остаётся evidence-driven: (1) получить второй и третий historical CLI outcome разных failure families; (2) провести отдельную CLI promotion transaction с no-regression; (3) только затем выбирать следующую узкую project stratum. Широкие stateful, distributed, framework и network-bound типы остаются в deferred backlog и не наследуют оценку pure-transform.

Коррекция оптимистичной оценки: Rich-CLI выявил, что experiment admission не исполнял `pilot_route=analysis_only_stop`. После fail-closed исправления Rich и Click останавливаются до Programmer Executor из-за project-wide prohibited risks; старый Rich validated-memory claim исключён из memory context. Поэтому CLI остаётся `1/3`, несмотря на наличие двух новых типизированных failure families и unit-tested reducers. Следующий evidence case должен не только иметь воспроизводимый defect, но и пройти recognition/pilot admission без исключений.

## 16. CLI activation and target-scope contrasts, 2026-08-30

CLI ledger завершён тремя независимыми project-native transformations: Autoflake, Flake8 и isort. Отдельная no-regression transaction `artifacts/role_promotion/project_native_repair_promotion_20260830T104614251822Z.json` прошла `167` тестов и Config Doctor `44/44`, после чего только три exact repair pattern стали `validated_active`. Это не общий допуск к произвольным CLI-проектам.

Узкий target-scoped waiver дополнительно прошёл frozen contrast: `3/3` решений совпали на isort и Click, direct `open` и project-level `subprocess` остались блокирующими, исходники не менялись. Evidence: `artifacts/field_trials/project_target_scope_contrast_20260830T145348614957Z.json`. Положительный transfer пока равен `1/2` независимых lineage, поэтому scope не расширяется.

`framework_plugin_build` foundation lane закрыт на свежем восьмипроектном owner holdout: семь targets прошли executable acceptance, AutoDoc корректно завершился Architect-owned exhaustion по 21 кандидатам, source changes равны нулю. После исправления evaluator-а, который раньше требовал выдумать candidate даже при доказанном отсутствии безопасного target, матрица `role_project_type_evaluation_20260830T150846767817Z.json` показывает Analyzer/Architect/SpecWriter `9.7/9.7/9.7` по 12 blind projects, 46 mature cells и zero weak cells.

Следующая очередь разделена: для того же `framework_plugin_build` нужны три независимые project-native transformations, чтобы доказать Implementer/Tester/Reviewer; их raw `10.0` остаются лишь structural score. Среди foundation-only gaps первым идёт `workspace_portfolio / Project Analyzer 9.2`. Широкие effect-heavy типы сохраняются в backlog.

## 17. Framework/plugin native promotion and workspace closure, 2026-08-30

Предыдущая очередь закрыта тремя независимыми historical transformations: Pluggy исправляет порядок `call_extra`, PyPA Build извлекает `.dist-info` из содержимого wheel, MkDocs нормализует пустой YAML theme config. Все failures воспроизведены дважды на parent source, получили unique target, прошли цепочку `Analyzer -> Architect -> SpecWriter -> Implementer -> Tester -> Reviewer`, generated-stub gate, targeted/project regression и source invariant. Promotion `artifacts/role_promotion/project_native_repair_promotion_20260830T160749995978Z.json` прошла `174` regression tests и Config Doctor `44/44`; активирован отдельный KB-каталог `framework_plugin_failure_repair_patterns.json`.

Текущая матрица `artifacts/field_trials/role_project_type_evaluation_20260830T161442270918Z.json` показывает для framework/plugin `9.7/9.7/9.7/9.8/10.0/9.8` и три native transformations без gaps. Workspace Analyzer поднят до `9.7` на пяти blind portfolios: система не выбирает root при доказанной неоднозначности и не запускает downstream-роли, которые для этого типа отмечены `not_applicable`.

Target-scoped transfer достиг минимального подтверждения: `project_target_scope_contrast_20260830T161826182156Z.json` совпал `4/4`, positive lineages `isort + mkdocs = 2/2`; literal read-only file access допускается, direct write и nonwaivable subprocess остаются блокирующими. Это расширяет доказательную базу узкого sandbox admission, но не даёт source apply и не переносит зрелость на широкие effect-heavy типы.

## 18. Bounded self-development protocol, 2026-08-30

Первый structural self-development layer реализован как `SelfDevelopmentChangeProposal` и `SelfDevelopmentChangeAdmission`. Декларативный `config/self_development_change_policy.json` задаёт классы `L0-L4`, authority для propose/sandbox/promote/apply и обязательные regression, holdout, independent-evaluator, stub и rollback gates. Unknown target kind fail-closed классифицируется как L4; `L1-sensitive` не может менять admission/promotion measure и самостоятельно подтверждать успех. Существующие `CapabilityDevelopmentRequest` материализуются в L3 `SelfDevelopmentShadowDossier`, но этот этап не применяет patch, не выполняет source apply и не продвигает capability.

Первый mature-corpus backfill управляется `config/self_development_shadow_trial.json`. Report `artifacts/self_development/self_development_shadow_trial_20260830T175415849133Z.json` реконструировал L0 proposals для трёх реально проведённых promotion transactions: pure-transform, CLI и framework/plugin. Все cases получили score `1.0`, все семь aggregate checks зелёные, каталоги и evidence reports сохранили digest. Ограничение принципиально: backfill доказывает корректное представление известных good changes, но не обнаружение новой systematic error; до prospective holdout L0 authority не расширяется.

Prospective path отделён от backfill файлом `config/self_development_prospective_detection.json`. Detector группирует только новые post-cutoff системные issues, не смешивает project types и требует три distinct projects. Текущий live report `artifacts/self_development/self_development_prospective_detection_20260831T031558750274Z.json` корректно завершился `waiting_for_evidence`: 75 старых reports исключены, 34 новых вошли в зрелый scope, 32 не дали системного сигнала, а общий `framework_plugin_build` recognition gap двух независимых проектов остался в watchlist с дефицитом одного проекта. Candidate не создан, `5/5` safety checks зелёные.

Повторное использование локального корпуса отделено в `config/self_development_corpus_eligibility.json`. `SelfDevelopmentCorpusEligibilityIndex` в `artifacts/self_development/self_development_corpus_eligibility_20260831T052410743974Z.json` учитывает 4903 копии и 4321 canonical project, оставляя 644 untouched packaging-marker candidates. Acquisition и frozen holdout сохраняют `3/3`, `7/7` checks зелёные; три сетевых pytest-plugin revisions добавлены только после доказанного локального дефицита и теперь помечены exposed.

В matcher добавлен общий KB-оператор `required_source_contains_all` и правило `owned_packaging_build_backend`. Оно требует совместного source evidence трёх PEP 517 hooks и backend-маркера, поэтому provider отличается от проекта, который только объявляет внешний backend. Реальные прогоны исправили `setuptools` до `framework_plugin_build/packaging_build_backend` с confidence `0.79`, подтвердили перенос на `flit` и `poetry-core` и сохранили consumer-only contrast вне правила.

`ProjectDevelopmentRun` теперь содержит `ClassificationConsistencyEvidence` от отдельного bounded AST evaluator. Если recognized-классификация расходится с owned contract, diagnosis создаёт `classification_contradiction` и допускает только research route. Unknown/ambiguous решения не дублируются, а проекты без независимого контракта остаются neutral. Prospective detector группирует contradiction отдельно и не создаёт candidate до трёх независимых проектов.

Второй narrow contract `owned_pytest_plugin` подтверждён training runs и отдельным unseen holdout. Authority требует `pytest11` плюс production fixture/lifecycle hook; entry point может вести на package module, поэтому буквальное имя `plugin.py` больше не является обязательным. SHA-frozen report `artifacts/pytest_plugin_holdout_20260831/holdout_report.json` дал recognition/consistency и executable acceptance `3/3`, minima Analyzer/Architect/SpecWriter `9.7/9.7/9.8`, source changes `0`. Conftest-only consumer остаётся neutral, downstream maturity не наследуется.

Для downstream добавлен первый настоящий defect trial: оригинальный regression test из upstream fix `49c8c1bb487d03ca1bda2ac7567e4205bf82aae6` перенесён на его parent `c9181c28607e990123ee480200ae2e684f58e7b6`. Intake `artifacts/field_trials/project_native_failure_intake_20260831T060005886998Z.json` дважды получил одинаковую сигнатуру и связал leaf `TypeError` с `faker_seed`. Development report `artifacts/project_development/project_development_20260831T060548304438Z.json` показывает реальную границу: subtype распознан, проверенного reducer нет, поэтому Implementer заблокирован, а Researcher/Architect оставили staged hypothesis `unsupported_reducer_shape` с confidence `0.68`. Source changes и executor rerun равны нулю; до promotion нужны независимые контрасты и три проверенные project-native трансформации.

Второй owner-independent trial взят из pytest-httpserver fix `96bbe1990c985df132f21f243d5bb4fe1f33a7ba`. Intake `artifacts/field_trials/project_native_failure_intake_20260831T062053744758Z.json` дважды воспроизводит readiness cleanup failure и через bounded state-transition slice связывает его с `HTTPServer.start`. Failure-backed target закреплён между ролями; network-risk сохраняет запрет execution, но допускает read-only Researcher. Report `artifacts/project_development/project_development_20260831T062528187092Z.json` завершён на `unsupported_reducer_shape` `0.68`, без patch/source changes/executor rerun. Текущий честный downstream итог: два qualified defects, ноль autonomous transformations.

Третий owner-independent trial использует pytest-socket fix `2bf8608adfc79f0e4ba1e44b42164cd658aa877a`. Intake `artifacts/field_trials/project_native_failure_intake_20260831T071448820513Z.json` связывает pickle reconstruction `TypeError` с `SocketConnectBlockedError.__init__` через unique named-constructor identity. Constructor interpreter сравнивает его с passing `SocketBlockedError`; этот same-project contrast допускает bounded design evidence, но не KB promotion. После раздельных human gates implementation report `artifacts/project_development/authorized_implementation_20260831T081035446426Z.json` прошёл targeted/full verification в sandbox при неизменном исходном проекте. Discovery breadth достиг `3`, supervised transformation threshold теперь `1/3`; autonomous threshold остаётся `0/3`.

Collector теперь автоматически вызывается после записи `ProjectDevelopmentRun`, хранит digest checkpoint и не пересчитывает duplicate. Derived signals декларативно покрывают role-handoff gap, human rejection и validated memory вне eligible route. Fresh batch без chain hints зафиксирован в `artifacts/self_development/self_development_fresh_blind_trial_20260830T183308224089Z.json`: десять новых reports, mature coverage `3+3+3`, девять type matches, один out-of-scope lark contrast, один eligible framework recognition gap и ноль clusters. Verdict `evidence_exhausted` означает отсутствие доказанной systematic error, а не провал. L0 lifecycle требует unseen holdout, regression, independent evaluator и reviewer decision; staging/quarantine находятся только в artifacts и поддерживают реальный rollback rehearsal, active KB write запрещён.

Exception-pickle active sync marker: `exception_pickle_active_application_20260903T065054426561Z.json` latest exact-target repair ledger accepted `astronomer__agents / astro-airflow-mcp/src/astro_airflow_mcp/adapters/base.py:NotFoundError.__init__` after exact promotions for Alembic range/head errors, JMComic base error, two Redis HTTP errors, Pact interaction verification, Discord command invoke and GraphQL WS response errors; latest intelligence `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` uses latest-blocker frontier accounting and reports `applied=178`, ledger `blocked=414`, latest-blocker frontier `146`, readmission frontier `0`, next lane `import_dependency_isolation_candidate:25`; latest planner `exception_pickle_import_cluster_planner_20260903T065218069738Z.json` marks `unknown:attribute_base_metaclass_risk` as `not_batch_ready`; latest failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` recommends `constructor_state_contract_research`. The current cycle also closed the `graphql`, `overrides`, `platformdirs` and `pydantic_settings` one-target clusters; Chroma exposed and verified narrow `dir`/`version` materializer coverage plus decorator-factory stub replay. The current cycle also closed `volcengine` and `vonage_jwt`; Volcengine verified `missing_services` list samples, and Vonage verified a bounded response-object sample with `status_code`, `url`, `content`, `text` and `json()`. The current project-local cycle added `project_local_direct_file`, filters out attribute-base and target self-attribute-gap cases, scopes failed-probe evidence by profile/cluster, and promoted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError`, and `astronomer__agents / NotFoundError`; stub path joins now use the platform temp directory and `endpoint` string samples are supported. Class-state audit `exception_pickle_class_state_contract_audit_20260903T070847705234Z.json` splits the 10 attribute-base/metaclass-risk cases into 7 `base_constructor_passthrough_contract`, 2 `attribute_base_state_contract`, and 1 `target_self_state_gap_research`; the next narrow lane is parent-constructor argument/state preservation research before replay. Source line-limit audit `source_line_limit_audit_20260903T230204065085Z.json` now passes across the scanned Python corpus: 1513 Python files checked, 0 files exceed the 400-line limit. Post-split audit `post_split_audit_20260903T230640450590Z.json` records 24 mechanical facades and 55 helper-backed tests as design-debt inventory. The final cleanup kept runtime clean, split the two remaining tool probes behind stable facades, split the project-map domain-profile plugin tests, and moved oversized runtime test suites into helper-backed context-bounded test modules. This records the 400-line rule as enforced for runtime, tools, plugins and tests, not as optional refactoring guidance.
Derived-message sync marker: `exception_pickle_derived_message_audit_20260902T045536203364Z.json` reports 0 derived-message cases; source apply and KB promotion remain false.
Derived-import sync marker: `exception_pickle_derived_import_audit_20260902T045554559495Z.json` reports 0 derived import-isolation cases; source apply and KB promotion remain false.
