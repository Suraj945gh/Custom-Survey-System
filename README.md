# Custom Survey System

A survey tool for the Concave Insights research team. You write a questionnaire as a simple text
file, and the app turns it into a working mobile survey.

> **Walkthrough video:** [Watch on Google Drive](https://drive.google.com/file/d/196hZw6Da_YVQ-qZQG4V2Tsw8gB23LqV7/view?usp=sharing)

---

## 1. Project Overview

The research team uploads a questionnaire as a plain `.txt` file, and the app lists every mistake
with its line number. They click through it as a test respondent, then an admin approves it as a
frozen version and puts it live. Respondents answer on their phones through a personal link, and
every answer is saved the moment they tap it. The team watches a live dashboard and downloads
results as CSV or Excel, in the same layout for every survey.

**Upload & check → Preview → Admin approves (v1, frozen) → Live on mobile → Dashboard & export**

No AI is used. The file format is fixed, so the checks are exact rules: the same file always gives
the same result.

---

## 2. Tech Stack

- **Backend:** Python 3.11, FastAPI
- **Database:** SQLite through SQLAlchemy (a single file, no database server needed)
- **Frontend:** React 18 + TypeScript, built with Vite; Tailwind CSS 4 for a mobile-first design
- **Export:** openpyxl for Excel, Python's `csv` for CSV
- **Tests:** pytest (622 tests) and Vitest (20 tests)

**Where things are:** `backend/app/questionnaire` reads and checks the file, `backend/app/engine`
decides which question comes next, `backend/app/services` holds the business rules,
`frontend/src/respondent` holds the phone screens, and `frontend/src/staff` holds the team's
screens. `design/` is the Day 2 design and `docs/` has later notes.

---

## 3. Setup and Run

You need **Python 3.11+** and **Node.js 20+**. It takes about 3–5 minutes.

```bash
git clone https://github.com/Suraj945gh/Custom-Survey-System.git
cd Custom-Survey-System
```

**Terminal 1: backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS / Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m app.seed                # loads the demo data
uvicorn app.main:app --reload     # http://localhost:8000
```

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Open **http://localhost:5173** and log in with a demo account (section 4).

- **Start over with fresh demo data:** `python -m app.seed --reset`
- **Try every API endpoint in the browser:** http://localhost:8000/docs
- **Run the tests:** `pytest` in `backend`, `npm test` in `frontend`
- **On a real phone:** connect it to the same Wi-Fi as the computer, then open the "Open on a
  phone" link from the survey's **Preview & share** tab.

---

## 4. Demo Logins and Test Data

| Role | Email | Password |
|---|---|---|
| **Admin** (also approves, goes live, closes, manages the team) | `admin@demo.local` | `admin12345` |
| **Researcher** (uploads, fixes, previews, dashboard, export) | `researcher@demo.local` | `research12345` |
| **Respondent** (no login) | open http://localhost:5173/s/smartphone_study | any 10-digit mobile number |

The login page has a **"Use"** button for each demo account.

**Demo data**
- **Smartphone Usage Study** (the sample file): approved as v1 and live, with 42 made-up
  respondents. 30 completed, 6 were screened out and 6 stopped half-way, so the dashboard and
  export have data.
- **Snack Habits Study** (the broken file): a draft with 11 errors, to show the upload check.

A number that completes a survey can't join another one for 90 days, so use a new number for each
full test.

---

## 5. Features

### Core features: all done ✅

- **Upload and check:** upload, drag and drop or paste a `.txt` file. Every error is shown with
  its line number and a suggested fix ("did you mean `single`?"), and the check re-runs live while
  you edit. All 10 planted mistakes in the broken file are found.
- **Preview and test mode:** click through the survey in a phone frame with every rule working.
  Test answers are kept apart and never counted.
- **Approve and version:** approval freezes the file as v1, v2, … Every response records its version.
- **All 13 question types:** single, multi (with a live counter), dropdown (with search), yesno,
  rating, nps, matrix, text, longtext, number, formatted (pincode / phone / email), info, consent.
- **Rules:** required questions, Other (specify) with the typed text used everywhere, None of
  these, and shuffle with fixed options kept last.
- **Logic:** skip-to; show-if with AND / OR; termination that keeps every reason
  (`q4: City not in scope | q5: Not a smartphone user`), including silent termination; piping;
  options-from.
- **Many surveys at once:** Draft / Live / Closed, each with its own target, quotas and deadline.
  A survey closes when its target is reached, when its deadline passes, or when an admin closes it.
- **Mobile filling:** a unique token link per person, every answer saved instantly, resume, Back,
  a progress bar, and four end screens (Completed, Not eligible, Survey closed, Already completed).
- **Live dashboard:** started, completed, terminated and in-progress counts, quota bars, and a
  count per termination reason. It refreshes every 5 seconds.
- **Export:** CSV and Excel in the standard format.
- **Also:** the 3-month cool-off rule, admin and researcher roles, and empty, loading and error
  states on every screen.

### Bonus features done ✅

- **Quality flags:** speeders (too fast) and straight-liners (the same answer on every matrix row)
  are flagged on the dashboard and in the export. A flag never deletes a response.
- **Clone:** "Copy as new wave" turns a survey into a new, separate survey for a second wave.
- **Drop-off report:** shows the last question answered by people who are still half-way.

---

## 6. Database Design

The Day 2 diagrams are in **[/design](design/)** ([user flow](design/user_flow.md),
[database](design/database.md)). Columns added during the build are listed in
[docs/database_build_notes.md](docs/database_build_notes.md).

| Table | One row is… |
|---|---|
| `users` | a team member (admin or researcher) |
| `surveys` | one study, with its status, target and deadline |
| `survey_versions` | one copy of the questionnaire file: a draft, or a frozen v1, v2, … |
| `questions` | one question of a version, with its options and rules stored as data |
| `quotas` | one quota of a version, e.g. Mumbai = 80 |
| `respondents` | one person, by mobile number (used for the cool-off rule) |
| `responses` | one person taking one survey: token link, version answered, status, end reasons |
| `answers` | one answer to one question, saved the moment it is given |

```
surveys ──< survey_versions ──< questions ──< answers >── responses >── respondents
                    └──< quotas                              (a response also points to its survey and version)
```

- **The questionnaire is stored as data, not code,** so every survey is shown by the same screens.
- **A response points to the exact version it answered,** so later changes never change old answers.
- **Each answer is saved straight away.** If a phone dies at q14, q1–q13 are already saved.

---

## 7. API Endpoints

All addresses start with `http://localhost:8000`. Staff endpoints need the header
`Authorization: Bearer <token>` from login. Respondent endpoints (`/api/public/...`) need no login.
Errors always come back as plain JSON such as `{"detail": "Only an admin can do this."}`.

### Overview

| Method | URL | Who | Purpose |
|---|---|---|---|
| GET | `/api/health` | anyone | Is the server running? |
| POST | `/api/auth/login` | anyone | Log in, get a token |
| GET | `/api/auth/me` | staff | Who am I? |
| GET | `/api/users` | admin | List team members |
| POST | `/api/users` | admin | Add a team member |
| POST | `/api/check` | staff | Check questionnaire text without saving it |
| GET | `/api/surveys` | staff | List all surveys |
| POST | `/api/surveys` | staff | Save pasted text as a draft (a new survey, or a new draft of the survey with the same id) |
| POST | `/api/surveys/upload` | staff | Same, from an uploaded `.txt` file |
| GET | `/api/surveys/{id}` | staff | One survey with its versions and draft |
| PUT | `/api/surveys/{id}/draft` | staff | Replace the draft text (the in-app editor) |
| DELETE | `/api/surveys/{id}/draft` | staff | Throw the draft away |
| GET | `/api/surveys/{id}/versions/{no}` | staff | One frozen version, with its file text |
| POST | `/api/surveys/{id}/test-runs` | staff | Start a test run (preview mode) |
| GET | `/api/surveys/{id}/dashboard` | staff | Live numbers |
| GET | `/api/surveys/{id}/export?format=csv\|xlsx` | staff | Download the completes |
| POST | `/api/surveys/{id}/approve` | admin | Freeze the draft as the next version |
| POST | `/api/surveys/{id}/go-live` | admin | Go live (or reopen) with a deadline |
| PATCH | `/api/surveys/{id}/deadline` | admin | Change the deadline |
| POST | `/api/surveys/{id}/close` | admin | Close the survey |
| GET | `/api/meta/network` | staff | The computer's local addresses, for the phone link |
| GET | `/api/public/surveys/{slug}` | anyone | Survey title, and whether it is open |
| POST | `/api/public/surveys/{slug}/join` | anyone | Join with a mobile number, get a personal link |
| GET | `/api/public/r/{token}` | link holder | The current screen (resumes at the next unanswered question) |
| GET | `/api/public/r/{token}/questions/{qid}` | link holder | Go back to an earlier question, with its saved answer |
| POST | `/api/public/r/{token}/answers` | link holder | Save one answer, get the next screen |

### Samples

<details>
<summary><b>Login and users</b></summary>

```http
POST /api/auth/login
{"email": "admin@demo.local", "password": "admin12345"}
```
```json
200 {"token": "1.1795557350.bFE561J8…", "user": {"id": 1, "email": "admin@demo.local", "name": "Asha Admin", "role": "admin", "is_active": true}}
```

```http
GET /api/auth/me
```
```json
200 {"id": 1, "email": "admin@demo.local", "name": "Asha Admin", "role": "admin", "is_active": true}
```

```http
GET /api/users
```
```json
200 [{"id": 1, "email": "admin@demo.local", "name": "Asha Admin", "role": "admin", "is_active": true},
     {"id": 2, "email": "researcher@demo.local", "name": "Ravi Researcher", "role": "researcher", "is_active": true}]
```

```http
POST /api/users
{"email": "neha@demo.local", "name": "Neha", "role": "researcher", "password": "neha12345"}
```
```json
201 {"id": 3, "email": "neha@demo.local", "name": "Neha", "role": "researcher", "is_active": true}
```
A researcher calling this gets `403 {"detail": "Only an admin can do this."}`.

```http
GET /api/health
```
```json
200 {"status": "ok"}
```
</details>

<details>
<summary><b>Checking and saving a questionnaire</b></summary>

```http
POST /api/check
{"text": "<survey id=\"snack_study\" …the broken file…"}
```
```json
200 {
  "ok": false, "error_count": 11, "warning_count": 0,
  "issues": [
    {"line": 11, "severity": "error", "code": "unknown_type",
     "message": "Question q3 has an unknown type 'singel'. Did you mean 'single'?"},
    {"line": 16, "severity": "error", "code": "missing_id",
     "message": "The question on line 16 has no id. Add one, e.g. id=\"q4\", so rules, quotas and the export can refer to it."},
    {"line": 21, "severity": "error", "code": "unknown_value",
     "message": "Question q5: terminate-on=\"Never\" can never happen. 'Never' is not one of the answers of q5 (Yes, No)."}
  ]
}
```

```http
POST /api/surveys
{"text": "<survey id=\"smartphone_wave2\" title=\"Smartphone Study, Wave 2\" target=\"200\"> …", "file_name": "wave2.txt"}
```
```json
201 {"id": 3, "slug": "smartphone_wave2", "title": "Smartphone Study, Wave 2", "status": "draft",
     "current_version_no": null, "has_draft": true, "versions": [],
     "draft": {"id": 4, "file_name": "wave2.txt", "text": "…", "updated_by": "Ravi Researcher", "check": {"ok": true, "error_count": 0, "warning_count": 0, "issues": []}}}
```

`POST /api/surveys/upload` does the same with a file (`multipart/form-data`, field `file`).
`PUT /api/surveys/{id}/draft` takes the same body and replaces the draft.
`DELETE /api/surveys/{id}/draft` returns `204` (no body).

```http
GET /api/surveys
```
```json
200 [{"id": 1, "slug": "smartphone_study", "title": "Smartphone Usage Study", "status": "live", "target": 200,
      "deadline": "2026-12-09T09:55:50Z", "current_version_no": 1, "has_draft": false, "completed": 30, …}]
```

```http
GET /api/surveys/1
```
```json
200 {"id": 1, "slug": "smartphone_study", "status": "live", …,
     "versions": [{"id": 1, "version_no": 1, "file_name": "concave_sample_questionnaire.txt",
                   "approved_at": "2026-11-24T09:55:50Z", "approved_by": "Asha Admin", "question_count": 18}],
     "draft": null}
```

```http
GET /api/surveys/1/versions/1
```
```json
200 {"id": 1, "version_no": 1, "question_count": 18, "text": "<survey id=\"smartphone_study\" …",
     "questions": [{"qid": "q0", "type": "info", "text": "Thank you for joining…", "required": false}, …],
     "quotas": [{"question_qid": "q3", "value": "Male", "target": 100}, …]}
```
</details>

<details>
<summary><b>Approving, going live, closing (admin)</b></summary>

```http
POST /api/surveys/2/approve          (the draft still has errors)
```
```json
409 {"detail": "The draft has 11 errors. Fix them before approving.", "issues": [{"line": 11, …}, …]}
```

```http
POST /api/surveys/3/approve
```
```json
200 {…the survey…, "current_version_no": 1, "draft": null}
```

```http
POST /api/surveys/3/go-live
{"deadline": "2026-12-09T18:00:00Z"}            (optional; the default is 15 days from now)
```
```json
200 {…, "status": "live", "deadline": "2026-12-09T18:00:00Z"}
```

```http
PATCH /api/surveys/3/deadline
{"deadline": "2026-12-12T18:00:00Z"}
```
```json
200 {…, "deadline": "2026-12-12T18:00:00Z"}
```

```http
POST /api/surveys/3/close
```
```json
200 {…, "status": "closed", "closed_reason": "closed_by_team", "closed_at": "2026-11-24T10:02:11Z"}
```
</details>

<details>
<summary><b>Preview, dashboard and export</b></summary>

```http
POST /api/surveys/1/test-runs
{"use_draft": false}
```
```json
201 {"token": "muO96gJyXm_CBKoSD8OY6g", "version_no": 1, "is_draft": false}
```
The token works with the respondent endpoints below, but the run is marked as a test and never counted.

```http
GET /api/surveys/1/dashboard
```
```json
200 {
  "status": "live", "target": 200, "started": 42, "completed": 30, "terminated": 6, "in_progress": 6, "progress": 15,
  "quotas": [{"question": "q3", "value": "Male", "target": 100, "done": 17, "left": 83, "full": false}, …],
  "reasons": [{"reason": "q4: City not in scope", "count": 4}, {"reason": "q5: Not a smartphone user", "count": 3}],
  "drop_off": [{"question": "q3", "count": 2}, …],
  "quality": {"checked": 30, "speeders": 2, "straight_liners": 2,
              "flagged": [{"respondent_id": 28, "flags": ["Speeder"], "seconds": 55}, …]},
  "versions": [{"version_no": 1, "started": 42, "completed": 30}],
  "test_runs": 0, "updated_at": "2026-11-24T10:05:00Z"
}
```

```http
GET /api/surveys/1/export?format=csv          (or format=xlsx)
```
```
200  a file download: smartphone_study_completes_2026-11-24.csv
Respondent ID,Version,Completed at,Quality flags,Q1. Do you agree to take part in this survey?,Q2. What is your age?,…
18,1,2026-11-20 10:23,,Yes,45,Male,Pune,…
```

```http
GET /api/meta/network
```
```json
200 {"addresses": ["192.168.1.23"]}
```
</details>

<details>
<summary><b>Respondent: join, answer, go back</b></summary>

```http
GET /api/public/surveys/smartphone_study
```
```json
200 {"slug": "smartphone_study", "title": "Smartphone Usage Study", "open": true, "message": null}
```

```http
POST /api/public/surveys/smartphone_study/join
{"phone": "9876543210"}
```
```json
200 {"token": "seqoeRcEguC63MBWju7-BQ", "resumed": false}
```
Joining again with the same number returns the same token with `"resumed": true`. A number that
completed a survey in the last 90 days gets
`403 {"detail": "You took part in one of our surveys recently. You can join again from 12 Feb 2027.", "code": "cool_off", …}`.

```http
GET /api/public/r/seqoeRcEguC63MBWju7-BQ
```
```json
200 {"kind": "question", "survey_title": "Smartphone Usage Study", "is_test": false, "progress": 0, "previous_qid": null,
     "question": {"qid": "q0", "type": "info", "text": "Thank you for joining. This survey takes about 5 minutes.",
                  "required": false, "options": [], "rows": [], "settings": {}},
     "answer": null}
```

```http
POST /api/public/r/seqoeRcEguC63MBWju7-BQ/answers
{"qid": "q6", "value": ["Samsung", "Other (specify)"], "other_text": "Nokia"}
```
```json
200 {"kind": "question", "progress": 39, "previous_qid": "q6",
     "question": {"qid": "q7", "type": "single", "text": "Which of these brands do you use now?",
                  "options": [{"value": "Samsung", "label": "Samsung", …}, {"value": "Nokia", "label": "Nokia", …}], …}}
```
A missing required answer gives `422 {"detail": "Please answer this question.", "code": "invalid_answer"}`.
After the last question the reply is an end screen:
`{"kind": "end", "end": "completed", "title": "Thank you!", "message": "Your answers have been saved. You can close this page.", "progress": 100}`.
The other end screens are `not_eligible`, `closed` and `already_completed`.

```http
GET /api/public/r/seqoeRcEguC63MBWju7-BQ/questions/q4
```
```json
200 {"kind": "question", "question": {"qid": "q4", "type": "dropdown", …}, "answer": {"value": "Mumbai", "other_text": null}, …}
```
</details>


---

## 8. Assumptions and Decisions

### In-progress responses (the open question in the brief)

- **Version 2 is approved while someone is half-way through version 1:** they finish on version 1.
  New people get version 2, and the export's Version column shows which version each row answered.
  Switching someone half-way could ask questions that don't fit their earlier answers.
- **The survey closes while someone is half-way:** reopening the link shows "This survey is
  closed" with the reason. Their answers are kept but never counted, because only complete
  participation counts.

### Other decisions

- **Checking the file:** the file looks like XML but isn't quite, so I wrote my own parser that
  keeps line numbers and reports every problem, not just the first. Errors block approval;
  warnings don't.
- **Versions:** edits before approval change one draft. The version number is given only on
  approval. A file with an existing `<survey id>` becomes a new draft of that survey.
- **Several termination reasons:** reasons are collected through the screening questions, then
  saved together, joined with `|`.
- **Quotas:** only completes count. A full quota group screens out new people in that group.
- **Unique links and cool-off:** people join with their mobile number and get a personal link back;
  the same number always gets the same link. A number that completed any survey in the last 90 days
  must wait.
- **Roles:** researchers prepare and test; only admins approve, go live and close.
- **Deadline:** 15 days after going live by default (the company's project cycle). The admin can
  change it.
- **Export:** completed responses only. Headers use the newest question wording, and times are in UTC.

---

## 9. Known Issues and Next Steps

- **Phone numbers are not verified.** A one-time SMS code would fix this.
- **It runs locally.** A real launch needs hosting with HTTPS, a strong secret key and PostgreSQL
  (only a setting changes).
- **Team members can be added but not edited or switched off** from the screen yet.
- **Next to build:** payments for completes and referral rewards, a respondent status page, and
  the remaining bonus ideas (nested quotas, shuffled matrix rows, AB/BA rotation, a second language).
