# 06: Aktifkan rate limit login, register, dan reset password

**Trello:** #160 — https://trello.com/c/AFm6miVI/160-mantra-aktifkan-rate-limit-login-register-dan-reset-password
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 3 — Core Application, Mantra
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Pasang `SlowAPIMiddleware` di `backend/app.py` dengan `app.state.limiter` dan `default_limits=[]`, lalu batasi eksplisit 5/minute pada login serta 3/minute pada register dan reset.

**Blocked by:** Tiket 04.

- [ ] Request login ke-6 dalam 60 detik → 429 dengan `error.code = "rate_limited"`.
- [ ] Request register dan reset ke-4 dalam 60 detik → 429 dengan envelope yang sama.
- [ ] Endpoint di luar auth tidak terkena limit global 300/minute.
- [ ] `backend/tests/test_auth.py` mencakup ketiga batas dan tetap lulus bersama seluruh suite.
