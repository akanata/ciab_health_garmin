# Cloud in a Bottle Health Producer for Garmin

This application implements a producer for the Cloud in a Bottle health data
spec from Garmin devices. The Garmin API itself is locked behind a developer
application portal, so data is extracted using GarminDB.

The service has two halves: an **ingest** side that drives GarminDB headlessly
on a schedule to keep a local SQLite corpus fresh, and a **serve** side that
maps those rows into `health_data_service` types over the spec's HTTP contract.

## Project Status

**Scaffolding only — no Python source exists yet.** `plan.md` at the repo root
is the design of record; read it before writing code. The current iteration
covers heart rate (`specific_types.py`) and sleep (`sleep_types.py`); workouts
are out of scope.

The tooling described under *Development Commands* has **not landed yet** —
there is no `pyproject.toml`, `justfile`, or `src/` tree. Today the live
dependency list is `requirements.txt` and the environment is the existing
uv-created `.venv/`. Do not assume a command works because it is listed here;
check that the file backing it exists.

## Important References

- Cloud in a Bottle Health Data service spec: https://github.com/cloud-in-a-bottle/health-data-service-spec
- Cloud in a Bottle - Creating an App: https://cloudinabottle.org/docs/creating_an_app/overview.html
- Cloud in a Bottle - App Manifest Spec: https://cloudinabottle.org/docs/creating_an_app/manifest_spec.html
- Cloud in a Bottle - Cross-App Services: https://cloudinabottle.org/docs/creating_an_app/cross_app_services.html
- GarminDB: https://github.com/tcgoetz/GarminDB

https://github.com/akanata/openhost_spec_mcp is a sibling Cloud in a Bottle app
that *consumes* this same spec. It is the reference for stack, layout,
Dockerfile, and test harness.

## Development Commands

- **Environment:** `uv sync` — manages the standard `.venv/`;
  `source .venv/bin/activate` still works. (The venv is `.venv/`, not `venv/`.)
- **Run local dev server:** `just run`
  → `uv run hypercorn garmin_health.app:app --bind 0.0.0.0:8080 --reload`
- **Lint, format, typecheck:** `just check`
  → `ruff check --fix . && ruff format . && uv run mypy`
- **Execute test suite:** `just test` → `uv run pytest -x`
- **Build container image:** `just build` → `docker build -t garmin-health .`

## Code Style & Architecture

- **Language:** Python 3.12 (`requires-python = "==3.12.*"`). GarminDB requires
  `>=3.12`; the sibling app and the Dockerfile pin 3.12.
- **Framework:** Litestar served by Hypercorn. This is a JSON API — there is no
  React, no Tailwind, and no frontend build. The only HTML is the owner-facing
  `/setup` page, which should be plain server-rendered markup.
- **Formatting:** 4-space indentation, double quotes, ruff `line-length = 100`.
  Lint rules `E,F,B,UP,I,PLC0415`; isort `force-single-line`.
- **Typing:** mypy `strict = true`, plus `follow_untyped_imports = true` — the
  spec package ships full annotations but no `py.typed` marker, so without it
  every import from it degrades to `Any`.
- **Wire types are attrs + cattrs, not pydantic.** All emitted timestamps are
  timezone-aware UTC, serialized as ISO 8601.
- **Isolation rule:** only the `garmin/` package may import `garmindb`,
  `idbutils`, `fitfile`, or `sqlalchemy`. Everything crossing that boundary is
  a `health_data_service` type or a stdlib type. GarminDB may be swapped later
  for the real Garmin API or a different unofficial API later; this must not
  impact the HTTP layer.

## Project Structure

```
src/garmin_health/
  config.py         Settings (frozen attrs) from env. No I/O.
  timezones.py      TimeZonePolicy - the ONLY place naive<->aware conversion happens.
  serialization.py  cattrs converter, hooks, the three response envelopes.
  registry.py       METRICS: dict[str, MetricEntry]. Declarative; one block per metric.
  service.py        HealthDataService facade - the only thing routes/ imports.
  garmin_config.py  Renders/validates GarminConnectConfig.json.
  auth.py           Garmin login + MFA state machine.
  sync.py           download -> import -> analyze; the background loop.
  garmin/           connection, sampling, vocabulary, heart_rate, sleep, daily.
  routes/           service.py (/v1/*), owner.py (/setup, /sync, /health).
tests/
  fixtures.py       build_fixture() - a real GarminDB SQLite in a tmpdir.
```

Dependency direction is strictly
`routes -> service -> registry -> garmin/* -> garmindb`, with `timezones.py`
imported only by `garmin/*`.

## Critical Guardrails & Gotchas

**Timezones — the highest-risk area of this project.**

- GarminDB stores **naive** datetimes on four different clocks. FIT-sourced
  rows (`monitoring_hr`, `monitoring_hrv_value`, `sleep_events`) are
  device-local; `sleep.start`/`sleep.end` are rendered in the *importing
  container's* `TZ`. At `TZ=UTC` these disagree by hours.
- Container `TZ` must be the Garmin account's home timezone; `GARMIN_HOME_TZ`
  overrides. Never fall back to the container's local zone — a silent wrong
  answer corrupts every timestamp and will not be noticed for months.
- `import_offset` applies to `sleep.start`/`sleep.end` **only**. Everything
  else converts via `home_tz` alone.
- Query bounds must be **naive**. SQLAlchemy's SQLite `DATETIME` bind processor
  discards `tzinfo`, so an aware bound silently mis-filters with no error.

**Spec conformance.**

- Construct spec types with **keyword arguments only**. attrs moves overridden
  base fields to the end, so `HeartRate.__init__` is `(source, metric_id=...,
  ..., samples=[])` — positional construction produces garbage.
- Never serve an interval-valued metric on `/v1/time-series`. The client's
  `Sample` structure hook resolves by MRO and silently drops `end_timestamp`.
  Sleep stages reach consumers only via `SleepSession.stages`.
- The manifest must declare the service as
  `github.com/imbue-openhost/health-data-service-spec` — the pre-rename string
  the spec's client still hardcodes. Declaring the `cloud-in-a-bottle` URL
  means no consumer will ever route to us. Verify against a live router.

**GarminDB.**

- `GarminConnectConfigManager` calls `sys.exit(-1)` on a missing or malformed
  config. Validate the JSON before constructing it.
- Its `homedir` and `temp_dir` are class attributes evaluated **at import**, so
  setting `HOME` after `import garmindb` has no effect. Use an absolute
  `directories.base_dir` with `relative_to_home: false`.
- Importers **swallow every per-file exception** — a totally failed sync looks
  successful. Verify by comparing row counts and `latest_time()`.
- `MonitoringFitFileProcessor` dereferences `plugin_manager` unconditionally;
  passing `None` raises `AttributeError`.
- Constructing a `DB` object **writes** (`create_all` + a version check), so
  `DBs/` cannot be mounted read-only. After any DB rebuild call
  `GarminConnection.reset()` — pooled handles otherwise point at the deleted
  inode and serve stale data silently.
- GarminDB and `garminconnect` are entirely synchronous. Never call them on the
  event loop; always `anyio.to_thread.run_sync`.
- Persist **both** the config dir (for `garmin_tokens.json`) and the HealthData
  tree. Retaining the raw JSON/FIT corpus means a schema rebuild needs no
  re-download.

**Auth.**

- There is no OAuth consent flow for this API — `garminconnect` replays the
  owner's **real Garmin password** against `sso.garmin.com`. Blank it from
  `GarminConnectConfig.json` once `garmin_tokens.json` exists.
- An unfinished MFA challenge lives on the `Garmin` client **instance**;
  `resume_login`'s `client_state` argument is ignored, so the object must be
  retained between the two requests.
