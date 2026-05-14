# Security Audit — Week 2 Code

## CRITICAL

### 1. Prompt Injection via `str.format()` (base_agent.py:22)
**File:** `backend/agents/base_agent.py`
**Line:** 22 — `return template.format(**context)`
**Risk:** If any context variable contains curly braces (e.g., a token symbol like `{self.api_key}`), Python's `str.format()` will attempt attribute access. An attacker controlling token metadata from external APIs (DexScreener, PumpDev) could exfiltrate the Kimi API key, environment variables, or any object attribute.
**Fix:** Replace with manual variable substitution or sanitize all context values before formatting.

### 2. Silent Safety Check Failures (rugcheck.py:58, 84)
**File:** `backend/services/rugcheck.py`
**Lines:** 58, 84 — `except Exception: pass`
**Risk:** If RugCheck.xyz or Solscan APIs fail (network error, rate limit, downtime), the service silently returns `safe=True`. A token with mint authority enabled could be marked as safe simply because the API was unreachable. This bypasses the entire safety layer.
**Fix:** Fail closed — if safety APIs fail, assume token is unsafe. Log failures explicitly.

## HIGH

### 3. Unbounded Memory Growth (whale_scorer.py:35)
**File:** `backend/scoring/whale_scorer.py`
**Line:** 35 — `self.positions: Dict[str, List[Position]] = {}`
**Risk:** All positions are stored in-memory forever. With 20 wallets each making dozens of trades daily, this grows indefinitely. No archiving, pruning, or persistence strategy exists.
**Fix:** Limit in-memory history (e.g., last 100 positions per wallet), persist to database, or implement TTL eviction.

### 4. Race Conditions on Shared State (whale_scorer.py)
**File:** `backend/scoring/whale_scorer.py`
**Risk:** `WhaleScorer` uses regular Python dicts/lists. With multiple async background tasks (whale poll + position updater), concurrent access will corrupt position tracking and produce incorrect P&L/score calculations.
**Fix:** Use `asyncio.Lock` around state mutations, or switch to database-backed state.

### 5. No Input Validation on Addresses
**Files:** `whale_scorer.py`, `launch_scorer.py`, `rugcheck.py`
**Risk:** Wallet addresses and token mints are accepted as arbitrary strings. Invalid/malicious data can corrupt SQLite indexes, cause downstream failures, or be injected into prompts.
**Fix:** Validate base58 format and 32-44 byte length for Solana addresses before processing.

## MEDIUM

### 6. No HTTP Timeouts (rugcheck.py)
**File:** `backend/services/rugcheck.py`
**Lines:** 38, 63
**Risk:** `aiohttp` requests have no timeout. A slow/unresponsive API will hang the entire asyncio event loop, freezing all background tasks.
**Fix:** Add `timeout=aiohttp.ClientTimeout(total=10)` to all requests.

### 7. No Financial Guardrails (agents)
**Files:** `backend/agents/whale_agent.py`, `backend/agents/sniper_agent.py`
**Risk:** Mock responses and future LLM outputs are not validated. `suggested_size_usd` could exceed `$50` max, `stop_loss_pct` could be negative, or extreme values could be returned.
**Fix:** Add post-processing validation clamping all financial fields to safe ranges.

### 8. JSON Parsing of Untrusted LLM Output
**File:** `backend/agents/base_agent.py:28-29`
**Risk:** `json.loads(response_text)` on arbitrary-length LLM output could cause memory exhaustion if a compromised/malicious model returns megabytes of data.
**Fix:** Truncate response to max length (e.g., 4KB) before parsing.

## LOW

### 9. API Key Exposure via Instance Attributes
**File:** `backend/agents/base_agent.py:10`
**Risk:** `self.api_key` stored as plain string. Accidental logging or serialization of the agent object leaks the key.
**Fix:** Use environment variable lookup at request time instead of storing in instance.

### 10. `any` Typo in Type Hint
**File:** `backend/services/rugcheck.py:14`
**Line:** `-> Dict[str, any]`
**Risk:** None (runtime safe), but `any` shadows built-in.
**Fix:** Change to `Any`.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 2 | Prompt injection, silent safety bypass |
| HIGH | 3 | Memory growth, race conditions, input validation |
| MEDIUM | 3 | Timeouts, financial guards, JSON limits |
| LOW | 2 | Key exposure, type hint |
