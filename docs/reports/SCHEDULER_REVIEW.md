# Scheduler & Telegram Background Jobs - Code Review Report

## 1. Timezone Bugs (daily_scheduler.py)

**Location:** `src/scheduler/daily_scheduler.py:13-15, 349, 359`

**Issue 1.1:** Overlap-aware timezone and midnight boundary handling
- Lines 349 and 359 do naive string-time comparisons (`schedules[time] <= now_time <= end_window`) on aware datetime objects.
- WIB = UTC+7. Midnight from UTC perspective is ~17:00 UTC relative to the previous day.
- If scheduler loop runs near 23:59 UTC (06:59 WIB the next day), datetime gets next day but string "08:30" still compares using current day's clock. Can cause missed jobs or re-occurrence.
- Sleep interval is 20s (line 366). If job delays > 20s, tz-aware windows overlap with next pass of the loop.

**Issue 1.2:** `datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))` is brittle despite Indonesia no DST
- Wired to UTC+offset; if entity moves to UTC+8, code breaks.
- Better to use named system timezone: `datetime.now(timezone(timedelta(hours=7)))` or `datetime.now(timezone("Asia/Jakarta"))`.

## 2. Overlapping Jobs

**Location:** `src/scheduler/daily_scheduler.py:366`

**Issue 2.1:** Fixed 20s idle between loop iterations
- All 4 jobs share the same loop and idle window (15–50s remaining). If API call takes > 20s, next window window collision.
- No per-job variance. No link between job duration and next scheduling decision.

## 3. Missing Error Recovery & No Health Check

**Location:** `src/scheduler/daily_scheduler.py:362-364`, `src/scheduler/daily_scheduler.py:338-369`, `src/notifications/telegram_bot.py:395-482`

**Issue 3.1:** No start/idempotency prevention for threads
- `start_background_scheduler()` and `start_telegram_bot_listener()` may be called multiple times and spawn duplicate threads.
- `daemon=True` is set on threads, but no thread identifier (e.g., UUID) or global flag.
- A killed/unclean thread leaves stale thread object but is allowed to continue.

**Issue 3.2:** No crash detection or recovery
- Scheduler prints error then loops (line 364), but cannot detect if thread previously crashed.
- Tele роботов listener loop catches and logs (line 481) then resumes; no waiting period or watchdog.

**Issue 3.3:** No general health endpoint
- `/api/telegram/status` exists (dashboard/backend/routes/telegram.py:22) but doesn’t indicate scheduler tick or thread status.
- Loop is tracked locally (`last_run` dict) but not exposed externally. No integration with FastAPI’s lifespan for monitoring.

## 4. Thread Safety

**Location:** `src/scheduler/daily_scheduler.py:98-101`, `src/scheduler/daily_scheduler.py:250-251`, `src/database/market_db.py:30-37`

**Issue 4.1:** Concurrent DB access without coordination
- `get_all_histories_from_db(limit_days=100)` runs in loop for each ticker (line 98–141).
- `save_signals_to_db(results)` writes alongside running jobs (line 251).
- SQLite is configured with WAL mode + `check_same_thread=False` + 60s timeout + "fast path", but within the same job, DB is read after possible writes from parallel logic, creating window for partial/broken results.
- The `LAST_RUN` dictionary is accessed without lock (line 345–360), enabling race conditions if loops run concurrently (multi-process scenario).

**Issue 4.2:** Telegram Bot poller shared with scheduled broadcasts
- `start_telegram_bot_listener()` and scheduler threads share global state.
- No coordination between listener (polls `/getUpdates`) and scheduled broadcasts (send messages).
- Threads may attempt send at same time, increasing contention in Telegram outbound traffic.

## 5. Duplicate Broadcasts

**Location:** `src/notifications/telegram_bot.py:86-96`, `src/notifications/telegram_bot.py:89, 91`

**Issue 5.1:** Double logging
- `send_telegram_message()` logs success twice (line 89 and 91): `[TELEGRAM] Pesan berhasil terkirim` and (implicitly via client) a confirmation, then again prints after error path.

**Issue 5.2:** User actions causing duplicate requests
- `/bsjp` command in listener (lines 433–446) spins a `handle_bsjp` daemon thread that runs full preprocessing + broadcast.
- No deduplication: if user clicks twice concurrently or API returns `ok`, you send two messages without de-dup or mutex.

## 6. Graceful Shutdown

**Location:** `dashboard/backend/main.py:84-105`

**Issue 6.1:** No signal handling or shutdown hooks
- Lifespan yields at line 105, background daemon threads continue (FastAPI doesn’t wait for completion).
- No SIGTERM/SIGINT handlers or state awareness in scheduler; SIGKILL forces immediate kill.
- Caller (main entry) can call `shutdown_events` but this isn’t integrated into scheduler loop.

**Issue 6.2:** Telegram listener unclosed on shutdown
- Listener spins `while True:` per loop (line 404). FastAPI closing FastAPI stops serving requests but polling loop remains running; redundant HTTP traffic continues.

**Issue 6.3:** Missing reset of `last_run` on restart
- `last_run` dict persists across process restarts if not persisted or cleaned.
- On restart, schedule may re-run same times on first hour.

## Proposed Fixes

### Timezone
- Replace naive string comparisons with offset-aware datetime comparison. Or normalize to UTC before comparison.
- For Indonesia, use `datetime.now(timezone("Asia/Jakarta"))` instead of `timedelta(hours=7)`.

### Overlapping jobs
- Include actual elapsed time per job in scheduling decisions to adjust sleep or skip.
- Window-based but with a cutover gap: closer to the end_window, shift last_run and schedule with controlled lag.

### Health check & idempotency
- Assign a thread identifier (UUID) to scheduler/bot listeners.
- Add a global flag (`_scheduler_running`) and check before start.
- Add `/health` endpoint returning scheduler ticker status or last run timestamp.

### Thread safety
- Wrap DB access time windows with timeout-or-wait logic per job, or add integrity checks before starting.
- Use a dedicated scheduler lock for `last_run` and for job execution state.

### Duplicate broadcasts
- Add a token (job ID) to `send_telegram_message` calls and optionally store in a redis-like DB for temp de-dup.
- In user actions, retry as fire-and-forget with locking, or show "Working..." to user.

### Graceful shutdown
- Implement shutdown event hook in lifespan: register signal handlers to stop loops and join daemon threads.
- Set `timeout` or `quit_flag` on listener and scheduler loops so they exit early.
- On restart, clear or persist `last_run` so first-run windows don’t re-trigger immediately.