# DentFlow Redis Audit Report

**Дата аудита:** 2026-04-19  
**Контекст:** аудит соответствия фактической реализации Redis-подхода в проекте DentFlow каноническим правилам `docs/16-5_card_runtime_state_and_redis_rules.md`.

---

## 1) Executive summary

В проекте Redis **формально подключен**, но **архитектурно не доведен до реального боевого контура**:

1. Есть реализованный runtime-слой для карточек (callback token + active panel + TTL + namespaced keys), что соответствует базовой идее каноники.
2. Но этот слой **не интегрирован в пользовательские роутеры** (patient/admin/doctor) и не используется в фактической обработке callback/card-flow.
3. Критичные runtime-состояния Telegram UI (панели, сессионные маркеры, режимы) продолжают жить в process-local памяти (`dict`), что ломается при рестартах и multi-worker.
4. Reminder subsystem в целом опирается на Postgres truth (это правильно), но не использует Redis для runtime-ускорителей/дедупликации/lock-координации.

Итог: на текущий момент Redis присутствует как **частичная инфраструктурная заготовка**, а не как обязательный operating backbone, описанный в канонике.

---

## 2) Что уже сделано хорошо (в контексте Redis)

### 2.1 Реализован Redis-adapter для card runtime

- Есть `AsyncRedisRuntimeAdapter` поверх `redis.asyncio`.
- Есть конфиг `REDIS_URL` и зависимость `redis` в проекте.
- Есть wiring в `RuntimeRegistry` (card runtime store + coordinator + callback codec).

Это хороший фундамент и правильное направление.

### 2.2 В runtime_state заложены ключевые концепции из каноники

Реализовано:
- callback token registry (`card:cb:<token>`),
- active panel registry (`card:panel:<actor_id>:<panel_family>`),
- TTL для callback/panel,
- supersede/invalidate механика,
- stale error semantics (`stale_callback`, `stale_panel`).

### 2.3 Есть покрытие тестами базового поведения

Юнит-тесты проверяют:
- shared runtime token-resolve,
- expiry callback,
- family-aware active panel supersede,
- stale callback validation.

---

## 3) Ключевые блокеры (must-fix)

## B1. Runtime Redis не участвует в реальном Telegram flow

Хотя `CardRuntimeCoordinator` и `CardCallbackCodec` создаются в bootstrap, в реальных bot-роутерах они фактически не задействованы.

**Почему это блокер:** каноника требует shared runtime state как production truth для callback/panel lifecycle. Пока flow работает мимо него, требования документа не выполняются.

---

## B2. Process-local state в patient router

В patient-роутере держатся in-memory структуры:
- `panel_by_user`,
- `session_by_user`,
- `mode_by_user`,
- `care_state_by_user`.

Это ломает restart-safety и multi-worker coherence для Telegram сценариев.

**Риск:** после деплоя/рестарта или при масштабировании в несколько воркеров пользовательские кнопки/состояния становятся несогласованными.

---

## B3. Fallback на InMemory вне prod

`build_card_runtime_redis()` возвращает `InMemoryRedis` при любом `APP_ENV`, кроме `prod/production`.

**Проблема:** staging/preprod/dev-like интеграционные среды не тренируют реальную shared-state модель и скрывают race/restart defects до production.

---

## B4. Каноника требует source-context/list-runtime state как отдельную категорию, а реализация пока ограничена callback+panel

В документе 16-5 явно выделены категории runtime state (source context / pagination / session correlation). В коде есть поля `source_ref` и `page_or_index`, но нет полноценного отдельного контракта/хранилища для list/navigation/session correlation.

**Риск:** back-navigation и nested flows остаются хрупкими при длинных сценариях.

---

## 4) Технический долг

### D1. Неиспользуемые зависимости в router signatures

`card_runtime` и `card_callback_codec` проброшены в `make_router(...)`, но по факту не используются в admin/doctor и не интегрированы в patient flow как обязательный runtime guard.

### D2. Voice mode state тоже process-local

`VoiceSearchModeStore` хранит TTL state в локальном dict + monotonic clock. Это нормально для MVP, но не для multi-instance bot runtime.

### D3. Нет Redis-ориентированной observability

Для runtime-state нет достаточной операционной телеметрии уровня:
- token created/resolved/missed,
- stale-panel reject counters,
- keyspace hit/miss,
- Redis availability degradation mode.

### D4. Нет тестов E2E на restart/multi-worker для Redis runtime

Есть unit слой, но нет интеграционных сценариев: «callback выпущен воркером A, обработан воркером B», «после restart state сохраняется по TTL», «при flush корректная stale деградация в UI».

---

## 5) Хвосты (backlog, не блокирующие запуск, но важные)

1. Единая key naming policy + versioning (`card:v1:*`, `voice:v1:*`, `idempotency:v1:*`).
2. Явный degraded-mode контракт при недоступности Redis (что разрешено, что блокируется fail-safe).
3. Redis policy для reminder runtime-ускорителей (ниже в предложениях).
4. SLO/SLI для reminder latency и callback stale-rate.
5. Runbook: flush, failover, TTL tuning, memory pressure handling.

---

## 6) Reminder subsystem в контексте Redis: текущий статус

Важно: reminder canonical truth в проекте хранится в БД (Communication), и это правильно по архитектуре.

Что уже хорошо:
- есть worker delivery/recovery,
- есть статусы scheduled/queued/sent/failed/canceled/acknowledged,
- есть retry и recovery политика.

Где Redis может дать практическую пользу без нарушения каноники truth-in-DB:

1. **Dispatch lock / duplicate suppression** на короткое окно:  
   ключи вида `rem:dispatch_lock:<reminder_id>` (SET NX EX).
2. **Action idempotency cache** для callback-кнопок напоминаний:  
   `rem:action_seen:<reminder_id>:<provider_message_id>:<action>`.
3. **Rate limiting per patient/chat** для burst-защиты.
4. **Short-lived routing cache** (patient->telegram target) c безопасной инвалидацией.
5. **Circuit-breaker state** для provider outage (временные маркеры в Redis, чтобы не DDOS-ить провайдера).

---

## 7) Рекомендуемый план исправления (по волнам)

## Wave 1 (критично, 1-2 PR)

1. Сделать Redis-runtime обязательным для card/callback production-path в patient flows.
2. Убрать process-local panel/session режим для карточных сценариев; заменить на runtime-store c TTL.
3. Внедрить `ensure_panel_is_active` + stale-safe ответы в callback handlers.
4. Добавить env-flag вида `REDIS_REQUIRED=true` для staging/prod-like окружений (fail-fast при недоступности Redis).

## Wave 2 (стабильность и операционка)

1. Интеграционные тесты multi-worker/restart/flush.
2. Метрики + structured logs для runtime-state.
3. Документ degraded mode (fail-safe semantics).

## Wave 3 (reminder performance + resilience)

1. Redis idempotency/lock keys для reminder delivery/actions.
2. Rate limit policy per patient/chat/clinic.
3. Provider outage circuit breaker + telemetry.

---

## 8) Предложение по Redis keyspace (draft)

- `card:v1:cb:<token>` — callback payload (TTL 15-60m)
- `card:v1:panel:<actor_id>:<family>` — active panel (TTL 1-3h)
- `card:v1:ctx:<actor_id>:<context_id>` — source/list context (TTL 30-60m)
- `voice:v1:mode:<actor_id>` — voice search mode (TTL = mode ttl)
- `rem:v1:dispatch_lock:<reminder_id>` — anti-duplicate lock (TTL 1-3m)
- `rem:v1:action_seen:<rid>:<msg>:<action>` — idempotency (TTL 24-72h)
- `rem:v1:rl:<patient_id>` — short window rate limiting

---

## 9) Риски, если оставить как есть

1. Случайные stale/ghost callback после деплоя.
2. Неконсистентные панели при горизонтальном масштабировании.
3. Непредсказуемое поведение UI при рестартах.
4. Операционные инциденты в reminder delivery при всплесках/дублях.
5. Рост скрытого техдолга: код «как будто Redis есть», но операционно «как будто его нет».

---

## 10) Финальный вывод

DentFlow прошел важный путь: Redis-заготовка и runtime-модель уже есть.  
Но на дату **2026-04-19** проект еще не соответствует собственной канонике Redis-first runtime в части реальной эксплуатации Telegram UI flow.

Главная задача ближайшего цикла: превратить Redis из "подключенной опции" в "обязательный operational слой" для card/callback/session runtime, а затем расширить его роль на idempotency/locks для reminder execution.
