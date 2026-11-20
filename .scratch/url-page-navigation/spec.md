# Spec: Navigasi Menu yang Mengubah Halaman di URL

Status: implemented (PR #46 merged 2026-11-19, merge dd65f29)
Document ID: PLAN-URL-PAGE-NAVIGATION-20261119
GitHub Issues: #41, #42, #43, #44, #45 (all closed)
Mapping: 01 → #41, 02 → #42, 03 → #43, 04 → #44, 05 → #45

## Problem Statement

Sebagai mahasiswa, dosen, atau admin FTMM Compass, ketika saya berpindah menu di sidebar, isi halaman berubah tetapi URL tetap di halaman awal. Akibatnya, menekan refresh mengembalikan saya ke Dashboard/default, tombol Back/Forward browser tidak melakukan apa-apa, dan saya tidak bisa menandai atau membagikan tautan ke halaman tertentu. Saya ingin halaman yang saya buka tercermin di URL.

## Solution

Setiap perpindahan menu menulis path halaman ke URL browser. Refresh membaca path tersebut dan langsung menampilkan halaman yang diminta. Back/Forward browser mengikuti perpindahan halaman. Redirect paksa (role tidak sesuai, logout, 401, sesi habis, path tidak dikenal) membersihkan riwayat dengan mengganti entri, bukan menumpuknya. Tautan jadwal `#timetable=` tetap terbawa lintas halaman. Item menu sidebar dan blok identitas profil menjadi tautan asli, sehingga Ctrl/middle-click membuka tab baru di halaman yang benar, sementara klik kiri tetap berupa transisi tanpa reload.

## User Stories

1. As a student, I want clicking a sidebar menu to update the URL path, so that I can bookmark the page I am on.
2. As a student, I want refreshing the browser while on Compass AI to keep me on Compass AI, so that I do not lose my place.
3. As a lecturer, I want refreshing while on Rekap & Kelola MK to keep me there, so that my review session is not interrupted.
4. As an admin, I want refreshing while on Manajemen Akun to keep me there, so that I can continue reviewing accounts.
5. As a user, I want the browser Back button to return to the previously viewed page, so that navigation follows normal browser behavior.
6. As a user, I want the browser Forward button to re-open the page I left, so that Back/Forward are symmetric.
7. As a user, I want to paste `/degree-planner` into a new tab and land directly on Degree Planner, so that I can share a precise link.
8. As a user, I want to paste `/course-finder` into a new tab and land directly on Course Finder, so that colleagues can open the same module.
9. As a user, I want to paste `/chatbot` into a new tab and land directly on Compass AI, so that a shared link is useful.
10. As a user, I want to paste `/profile` into a new tab and land directly on Profil Pengguna, so that profile settings are linkable.
11. As a user, I want opening `/pj-courses` as a student to redirect me to Dashboard, so that I never see an empty Rekap & Kelola MK area.
12. As a lecturer, I want `/pj-courses` to open normally, so that my Rekap & Kelola MK link works.
13. As a PJ Prodi, I want Rekap & Kelola MK to remain a lecturer capability, so that no separate role is introduced for my jabatan.
14. As a student, I want `/degree-planner` and `/chatbot` to be available to me, so that my study-planning modules stay accessible.
15. As a lecturer or admin, I want student-only deep links to redirect to Dashboard, so that I do not see pages meant for students.
16. As an admin, I want `/admin-accounts` to open normally, so that my account-management work remains linkable.
17. As a non-admin, I want `/admin-accounts` to redirect to Dashboard, so that I cannot reach account management by typing a URL.
18. As a lecturer, I want `/course-finder` to remain openable even though it is not in my sidebar, so that the existing quick-access path keeps working.
19. As a user, I want `/` to keep showing Dashboard, so that the original entry URL still works.
20. As a user, I want an unrecognised path to be replaced with `/dashboard`, so that the address bar never lies about the page shown.
21. As a user, I want clicking Dashboard to write `/dashboard` rather than leave `/`, so that the canonical page URL is consistent.
22. As a user who logs out from any page, I want to land on Dashboard with history replaced, so that Back cannot return to a page I no longer have access to.
23. As a user whose session expires or receives 401, I want the same clean redirect, so that stale pages cannot be revisited from history.
24. As a user with no active session who opens a deep link, I want to see the Login form first, so that I am not shown protected content.
25. As a user who logs in after that, I want to start at Dashboard, so that behavior matches what happens today.
26. As a user, I want Ctrl+click or middle-click on a sidebar item to open a new tab at that item's URL, so that I can keep two pages side by side.
27. As a user, I want a plain left-click to stay inside the app without a full reload, so that session and transient state are preserved.
28. As a user, I want the profile identity block to behave like a link as well, so that Profil Pengguna can be opened in a new tab.
29. As a user, I want quick-action buttons inside pages to remain buttons, so that they keep their current in-page behavior where a course or tab context is involved.
30. As a student, I want a shared timetable hash to survive refresh and page switching, so that the shared jadwal is still applied when I navigate.
31. As a student, I want dismissing a shared timetable to remove only the hash, so that the current page path is not lost.
32. As a user, I want the header title and active sidebar highlight to follow the URL after refresh and Back/Forward, so that the UI never contradicts the address bar.
33. As a user, I want each page's error boundary to reset when the page changes, so that an error on one page does not leak into another.
34. As a user, I want refreshing a deep link under the current Vite-served deployment to return the app shell, so that I do not get a 404.
35. As a maintainer, I want access rules kept in the existing session/access module, so that authorization has one source of truth.
36. As a maintainer, I want the navigation flow documentation updated, so that it no longer states that routing is state-only.
37. As a maintainer, I want no new routing library, so that dependency surface stays unchanged.
38. As a maintainer, I want no test framework added for a single URL parser, so that verification stays at the browser seam already used by the team.
39. As a maintainer, I want the risk of future static hosting documented rather than configured now, so that no config is added for a host that does not exist yet.
40. As a user, I want chat history, selected course detail, planner tab, and scroll position to remain transient, so that only the page identity is encoded in the URL.

## Implementation Decisions

- The app shell gains a URL-to-page mapping and a page-to-URL builder. The page union stays the single vocabulary for all seven modules; slug names follow the existing page identifiers.
- The URL pathname is the identity of the active page. The root path remains an alias for Dashboard; unrecognised paths resolve to Dashboard and are replaced in history.
- The current page state is initialised from the location and updated through one navigation function that writes history and local state together. A `popstate` subscription is the only reader for Back/Forward, and is cleaned up on unmount so StrictMode's double mount is safe.
- Click-driven navigation uses push history; forced redirects use replace history. Forced redirects cover role denial, logout, 401/session expiry, successful login, and unrecognised paths.
- Session state is already read synchronously from local storage, so the first render can decide the page without an async gate. An unauthenticated deep link shows Login; successful login still starts at Dashboard.
- Access rules stay centralised. Existing restrictions remain: study-planning and Compass AI are student-only, account management is admin-only. Rekap & Kelola MK becomes lecturer-only so a typed URL cannot produce an empty page. Course Finder remains available to lecturers, matching the existing quick-access path. PJ Prodi remains a lecturer attribute rather than a new role, per the accepted architecture decision.
- Sidebar items and the profile identity block become real anchors. A plain left-click is intercepted for in-app navigation; clicks with modifier keys are left to the browser. Quick-action buttons inside feature pages remain buttons.
- Search parameters and the hash are preserved when building the destination URL, keeping the shared timetable token intact. Dismissing a shared timetable still clears only that token.
- No module interface is added for transient state: planner tab, selected course, chat messages, and scroll position stay in React state.
- No schema, API contract, or backend behavior changes.
- No new dependency, no router, no test framework, and no static-host rewrite configuration. The deployment risk is recorded in the plan document instead.
- The navigation-flow documentation is corrected to describe URL-backed routing.

## Testing Decisions

- A good test observes only external behavior: the address bar path, the rendered page, the active sidebar highlight, history navigation, role-based outcomes, and the timetable hash. No test asserts internal state variables or helper function calls.
- One seam: browser-level QA against the running application. The matrix covers each menu click, refresh on every page, Back/Forward, deep links per role, unknown path, logout history, middle-click, and timetable hash preservation. This matches the team's existing browser-QA evidence from the sprint scratch folder.
- The server fallback for deep links is checked with a single HTTP request during verification as an environment check, not as a code test seam.
- No unit tests, component tests, or new test framework. A pure URL parser alone does not justify infrastructure that the repo does not currently have.

## Out of Scope

- No router library and no change to the build/serve setup.
- No conversion of in-page quick-action buttons to anchors.
- No page state beyond identity in the URL: no planner tab, selected course, chat history, or scroll position.
- No return-to-requested-page after login.
- No dedicated "access denied" page; role denials go to Dashboard.
- No access-rule changes other than making Rekap & Kelola MK lecturer-only.
- No rewrite rules for a hypothetical static host, no new hosting configuration.
- No backend, schema, API, or Trello card changes.
- No push to any remote.

## Further Notes

- This spec synthesises the approved low-level plan `PLAN-URL-PAGE-NAVIGATION-20261119` and the decisions confirmed during grilling, including the change from buttons to anchors for sidebar navigation.
- Glossary vocabulary applies: the planning unit is a Kartu Trello; local execution files are Tiket kerja. PJ Prodi remains a lecturer flag per the accepted ADR.
- Verification still includes `curl` for deep-link fallback because no recorded result exists; the conclusion that Vite serves `index.html` for unknown paths rests on documented default behavior, not a repo test.
- Existing deployment is Vite-only with root base; no static host or subpath is configured, so the host risk is a note rather than a task.

## Delivery Notes

- Implemented on `backend-page` (head `d4314d9`) and merged upstream through PR #46. The merge is already an ancestor of `feat/prodi-scoped-accounts` via `upstream/main`.
- PR #46 records browser QA for menu clicks, refresh, Back/Forward, deep links per role, role redirects, logout history, hash preservation, and the Vite SPA fallback.
- Two acceptance items were not directly observed in automated Chromium: opening a new tab via Ctrl/middle-click (only `href` and the modifier guard were checked) and dismissing a shared timetable (the button was absent on the QA baseline). These remain manual-verification gaps, not completed evidence.
