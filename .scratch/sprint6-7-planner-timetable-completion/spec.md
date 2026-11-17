# Spec: Selesaikan Kartu Sprint 6–7 Hans/Mantra (Planner & Timetable)

Status: ready-for-agent
Feature slug: `sprint6-7-planner-timetable-completion`
Source: hasil sesi grilling 2026-11-17 (Q1–Q14), verifikasi kode backend/frontend, dan deskripsi kartu Trello board `FTMM COMPASS`.

## Problem Statement

Sepuluh kartu Trello Sprint 6 dan 7 atas nama Hans dan Mantra masih berstatus `dueComplete=false`. Pemeriksaan kode menunjukkan kondisinya tidak seragam: sebagian kartu benar-benar belum diimplementasikan, sebagian setengah ada, dan sebagian sudah selesai di kode tetapi belum disinkron ke Trello.

Akibatnya:

- Katalog matkul belum punya endpoint detail satu matkul; data `prerequisites` yang dikirim admin ke endpoint create/update dibuang, sehingga rantai prasyarat tidak bisa dipertahankan lewat API.
- Validasi prasyarat Degree Planner bergantung pada array yang dikirim klien. Klien yang tidak mengirim array tidak divalidasi sama sekali, dan frontend tidak pernah memanggil endpoint validasi gateway.
- Timetable Builder tidak punya API backend sama sekali. Frontend memakai daftar `sections` yang selalu kosong, sehingga deteksi bentrok tidak pernah terjadi, panel kelas alternatif kosong, dan ekspor `.ics` serta cetak PDF menghasilkan berkas kosong.
- Persistensi Degree Planner sudah pindah ke database, tetapi kartu lama masih meminta `localStorage`, dan deskripsi kartu cloud-sync masih menyebut kontrak endpoint yang sudah dibatalkan oleh keputusan desain sebelumnya.
- Hardening produksi baru mencakup container non-root dan sebagian error envelope. Tidak ada deteksi diskoneksi klien pada SSE, catch-all 500, atau test regresi produksi, tetapi knowledge base menyatakan kartu tersebut tuntas.
- Tidak ada sinkronisasi antara bukti aktual di repo dan status kartu Trello; knowledge base memuat klaim yang cocok dengan repo chatbot, bukan repo UI.

## Solution

Selesaikan sembilan kartu backend dan frontend dalam satu feature branch, lalu sinkronkan status Trello berdasarkan bukti terverifikasi. Bekerja berurutan: backend lebih dulu karena frontend bergantung pada data kelas dari database, kemudian frontend, lalu sinkron Trello lewat MCP.

Kartu benchmark konkurensi/SSE (chatbot) ditunda dan tidak disentuh dalam spec ini.

## User Stories

1. As an admin, I want to create a course with its prerequisite chain through the catalog API, so that the curriculum stored in the database is complete and reusable by the planner.
2. As an admin, I want to update a course together with its prerequisites, so that curriculum revisions are not silently discarded on save.
3. As an admin, I want a duplicate course code to be rejected with a conflict response, so that the catalog cannot contain ambiguous entries.
4. As an admin, I want invalid catalog parameters to be rejected with a validation response, so that bad input never reaches the database.
5. As an admin, I want a created course to be immediately visible in the catalog list, so that I can confirm the write succeeded without a separate rebuild step.
6. As an admin, I want a deleted course to disappear from the active catalog, so that retired courses are not offered to students.
7. As a student, I want to retrieve the detail of one course by its code, so that I can inspect its metadata and prerequisites before planning.
8. As a student, I want an unknown course code to return a clear not-found response, so that the UI can show an honest empty state instead of a generic failure.
9. As a student, I want the planner to resolve prerequisites from the database, so that my plan is validated even when the client does not send a prerequisite array.
10. As a student, I want fast local prerequisite feedback while arranging courses, so that I see obvious problems immediately.
11. As a student, I want the gateway to be the final authority on prerequisite validation, so that bypassing the UI cannot produce an invalid plan.
12. As a student, I want my saved degree plan to remain free of duplicated academic rules, so that storage and validation stay independent.
13. As a student, I want to see the real class sections available for a course in the active academic period, so that I am choosing from actual offerings rather than placeholder data.
14. As a student, I want each class section to show its meeting days, times, and room, so that I can compare schedules without leaving the planner.
15. As a student, I want the system to detect overlapping classes among my selected sections, so that I know my timetable is not workable before the semester starts.
16. As a student, I want to see concrete alternative class sections that are free of conflicts, so that I can resolve a clash without searching the course catalog again.
17. As a student, I want to apply an alternative section directly from the resolution panel, so that the timetable grid updates immediately.
18. As a student, I want a conflicting time slot to be visibly marked with both color and text, so that the warning is perceivable without relying on color alone.
19. As a student, I want an informative message when no class sections exist yet for a course, so that an empty response is not mistaken for a broken feature.
20. As a student, I want to export my real weekly schedule to an `.ics` file, so that I can import it into Google Calendar or Apple Calendar on my phone.
21. As a student, I want the exported calendar to contain recurring weekly events with correct course names and times, so that the schedule stays accurate throughout the semester.
22. As a student, I want to print or save my timetable as PDF, so that I have an offline copy free of navigation elements.
23. As a student, I want export and print actions to explain when there is no schedule to export, so that a silent no-op is replaced with an actionable message.
24. As a student, I want my degree plan to persist on the server across browsers and devices, so that clearing local storage does not destroy my work.
25. As a student, I want a visible save status that reflects the actual network request, so that I know whether my latest draft is on the server.
26. As a student, I want a retry action after a failed save, so that a transient network error does not require re-entering my plan.
27. As a student, I want a confirmation dialog when my local draft differs from the server copy, so that I do not silently overwrite newer work.
28. As a student on a phone, I want the eight-semester roadmap to become a semester-by-semester selection, so that I do not have to scroll sideways through eight columns.
29. As a student on a phone, I want the weekly timetable to become a per-day accordion, so that five days are readable on a narrow screen.
30. As a student using touch, I want every action target to be at least 44 by 44 pixels, so that buttons are reliably tappable.
31. As a student on a phone, I want no horizontal page overflow, so that the page does not appear broken at 375–414 pixels.
32. As an operator, I want unexpected server failures to return the standard error envelope without internal details, so that clients can handle errors uniformly.
33. As an operator, I want rate-limit responses to include a retry hint, so that clients know when to try again.
34. As an operator, I want the streaming chat response to stop when the client disconnects, so that inference capacity is not wasted on abandoned requests.
35. As an operator, I want the containers to drop all Linux capabilities and run read-only where possible, so that a compromised process has limited write and privilege options.
36. As an operator, I want root and API-version info endpoints to behave consistently, so that health checks work across both tiers.
37. As a project manager, I want each completed card to carry an evidence comment and checked deliverables, so that Trello reflects verified work.
38. As a project manager, I want the knowledge base drift to be corrected in the card comments, so that future agents do not rely on false "done" claims.
39. As an AI agent, I want one branch with atomic per-card commits, so that changes remain reviewable and unrelated work is not disturbed.
40. As an AI agent, I want the Trello sync to happen only after verification, so that no card is marked complete without observable evidence.

## Implementation Decisions

### Scope and sequencing

- Nine cards are in scope: catalog CRUD, planner validation endpoint, timetable endpoint, ICS/PDF export, local-draft card closure, production hardening, cloud-sync correction, conflict warning with alternatives, and mobile reflow.
- The concurrency/SSE benchmark card is deferred. Its Trello flag remains false and no artifact is created for it.
- Work is ordered in three waves: backend, frontend, Trello synchronization. Frontend depends on backend-provided section data; mobile reflow is last so it does not rework UI that is still changing.
- All work lands on one feature branch created from the local upstream main ref. One atomic commit per card. No publish or push operation is performed by the agent.

### Degree plan contract

- The canonical persistence contract remains the plural `degree-plans` resource with its `items` sub-resource. The previously proposed `plans/me` naming was reviewed and rejected: the `plans` resource is reserved for AI-generated plan synthesis. The stale description on the cloud-sync card is corrected by a Trello comment, not by changing the code.
- The local-storage draft card is closed as superseded by server persistence. Persistence ownership stays with the database by explicit prior design decision; the browser cache is not reintroduced.
- Selected class sections are not added to the persisted degree-plan item payload. That would require a schema migration, which is outside this effort. Section availability comes from the backend; the user's transient section choice remains client state until a future decision changes the schema.

### Catalog API

- The catalog API gains a single-course read endpoint keyed by course code. A missing course returns not-found with the canonical error code for a missing course; malformed or out-of-range query parameters return unprocessable-entity with the canonical validation error code.
- Prerequisites submitted on create and update are persisted as requirement rules and nodes, and the same reader used by the catalog is the single source for reading them back. The catalog is rebuilt after writes so the next list request reflects the change.
- The update handler's existing no-op assignment is replaced with actual field application. Duplicate codes return conflict; successful create returns created with a location header.
- Dual-tier exposure is preserved: canonical v1 paths and legacy aliases continue to be mounted by the same mechanism.

### Planner validation

- Before constraint validation runs, the handler resolves each course's prerequisites from the database and fills them into the validation payload. A client sending an empty prerequisite array can no longer bypass the check.
- The client-side prerequisite evaluator remains as immediate feedback in the course inspection modal, but the gateway is the authority when a plan is finalized or forwarded.
- The persistence path deliberately does not run academic validation. Referential and parity constraints remain the responsibility of the database triggers and the existing resolution logic. This keeps one rule owner for academic validity.

### Timetable and class sections

- A new backend module exposes two endpoints. A read endpoint returns the class sections and their meeting schedules for a course in an academic period, queried from the class-section and class-schedule tables. A validation endpoint accepts a period and a list of selected course-section pairs, then returns overlapping pairs and conflict-free alternative sections for the same courses.
- Both endpoints follow the standard success envelope for collections and the standard error envelope for not-found and unprocessable cases. Resource naming is plural and kebab-case, and validation is modelled as a noun-style sub-resource to match the existing plan-validation endpoint.
- The frontend replaces its always-empty section placeholder with data from the read endpoint. The conflict algorithm already present in the shared timetable domain remains for instant feedback; the backend validation result is authoritative for the displayed conflict list and alternatives.
- Empty sections are an explicit UI state with a cause and a next action, not a silent empty array.

### Export and print

- The existing iCalendar generator and print stylesheet are kept. The export entry point stops returning silently when there is no schedule and instead surfaces a visible message.
- Export data is derived from the same backend-backed section source as the timetable grid, so the file cannot disagree with what the student sees.

### Production hardening

- A catch-all exception handler returns the standard error envelope with internal-error code and no stack trace. Rate-limit responses carry a retry hint.
- The streaming response generator observes client disconnection and stops work when the client is gone.
- Container runtime drops all capabilities and uses a read-only root where writable paths allow it. The existing non-root user is retained; its numeric id is corrected in evidence comments rather than changed in the image.
- Root and API-version information endpoints are added so both tiers expose the same startup information.
- A dedicated production-readiness test module covers envelope behavior, rate-limit headers, non-root execution, stream cancellation, root parity, and search parity.

### Trello synchronization

- After verification, each in-scope card receives an evidence comment in concise technical Indonesian covering root cause, exact changes, and observable proof; its deliverable checklist items are checked and its due-complete flag is set.
- The superseded local-storage card is closed with an explicit note. The deferred benchmark card is left untouched.
- Comments correct the knowledge-base drift: artifacts from the sibling chatbot repository are not evidence for UI-repo cards, and the container user id claim does not match the image.

## Testing Decisions

### What makes a good test here

A good test exercises externally observable behavior: an HTTP status and envelope, a row that can be read back through a subsequent request, a rendered warning that appears for a real clash, or a downloaded calendar containing the expected recurring events. Tests must not assert private helper calls, internal variable values, or incidental implementation details. A test that only repeats source structure is not acceptable.

### Seams

- **Backend seam — HTTP API through the existing FastAPI test client.** This is the highest existing seam and matches all current backend suites. It covers catalog detail and writes, planner validation, timetable section reads and clash validation, and production-readiness behavior.
- **Frontend seam — the running browser surface against the seeded local environment.** There is no automated component or end-to-end framework in this repo, and adding one is out of scope. The highest available seam is the real rendered page driven through the headless browser available in the local agent environment, with screenshots at 375, 768, and 1280 pixels and the browser console checked for errors.

These two seams are proposed as the complete test surface; no lower-level unit seams are added for logic already covered at the API or browser level.

### Prior art

- Backend prior art: the existing catalog, admin-course, plan, domain, degree-plan, health, and chat suites, all run through pytest with a seeded PostgreSQL database. CI seeds the full catalog before the suite.
- Frontend prior art: no automated frontend test files exist; verification is type checking, production build, formatting check, and manual browser inspection. That practice is retained and strengthened with headless screenshots.
- Verification commands: the repository's existing test and build commands are used; container builds stay quiet. Database-dependent suites require the local database and migrations to be running.

### Coverage by card

- Catalog CRUD: detail success and not-found, prerequisite persistence on create and update, duplicate conflict, validation failure.
- Planner validation: rejection when the client omits prerequisites but the database has them, plus the existing parity and credit-limit cases.
- Timetable: section read for an active period, not-found, clash detection, alternative suggestions, empty-section state.
- Export: iCalendar content with recurring events and non-empty event count; print surface present in the rendered tree.
- Conflict UI: banner and alternatives appear only when backend data contains a real clash; applying an alternative changes the grid.
- Mobile: no horizontal window overflow at narrow widths, tap targets meet the minimum, no console errors.
- Production readiness: six observable behaviors named in the card.

## Out of Scope

- The concurrency, SSE-latency, and memory-stability benchmark card and any artifact or script associated with it.
- Any change in the sibling chatbot repository; its artifacts are not reused as evidence for UI-repo cards.
- Reintroducing browser-local draft storage.
- A schema migration or new column for persisting selected class sections in degree-plan items.
- Changing the canonical degree-plan endpoint contract.
- Adding Playwright, Vitest, or any other frontend test framework or dependency.
- Publishing, pushing, or opening a pull request; Trello changes are limited to the in-scope cards.
- Cards whose titles name other owners, including the cross-team user-acceptance and final-review cards.

## Further Notes

- Four source documents disagree with current code and are treated as drift to be corrected in Trello comments: the local-storage draft requirement, the cloud-sync endpoint naming, the container user id, and the claim that production-readiness work is complete.
- The timetable conflict database view and the class-section tables already exist in the schema baseline; no new schema objects are required for this effort.
- The mobile work must define states across the whole width range, not only a phone and a desktop breakpoint, and must keep every interactive element keyboard reachable and visibly focused.
- All user-facing text stays in formal but friendly Indonesian. No hardcoded color values are introduced; existing design tokens are reused.
- Evidence comments follow the repository's concise technical Indonesian convention and avoid meta phrasing.
