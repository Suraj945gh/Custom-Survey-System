# Custom Survey System

A survey tool for the Concave Insights research team. You write a questionnaire as a simple text
file, and the app turns it into a working mobile survey.

> **Walkthrough video:** _link added on submission day_

---

## 1. Project Overview

The research team uploads a questionnaire as a plain `.txt` file. The app checks it and lists every
mistake with its line number. The team clicks through it as a test respondent, then an admin
approves it as a frozen version and puts it live. Respondents answer on their phones through a
personal link, and every answer is saved the moment they tap it. The team watches a live dashboard
and downloads clean results as CSV or Excel, in the same layout for every survey.

**The journey of one survey:**

```
 Write the .txt  ──►  Upload & check  ──►  Preview / test  ──►  Admin approves (v1)  ──►  Live
                      (errors with line                          (frozen, can never                │
                       numbers)                                   change)                          ▼
                                                          Respondents answer on their phones
                                                          (saved after every tap, can resume)
                                                                         │
                                         Live dashboard  ◄───────────────┤
                                         CSV / Excel export ◄────────────┘
```

No AI is used anywhere. The questionnaire format is fixed, so the checks are exact rules: the same
file always gives the same result, instantly.

---

## 2. Tech Stack

| Part | What we used | In plain words |
|---|---|---|
| Backend | **Python 3.11**, **FastAPI** | The "brain": reads files, applies the survey rules, saves answers |
| Database | **SQLite** via **SQLAlchemy** | One file (`backend/survey.db`), no database server needed |
| Frontend | **React 18 + TypeScript**, built with **Vite** | The screens you click |
| Styling | **Tailwind CSS 4**, **lucide-react** icons | Look and feel, mobile-first |
| Export | **openpyxl** (Excel), Python's `csv` | The download files |
| Tests | **pytest** (622 tests), **Vitest** + Testing Library (20 tests) | Checks that run automatically |

Logins use only Python's standard library: passwords are stored as PBKDF2 hashes, and logins use
signed tokens.

**Where things are**

```
backend/
  app/questionnaire/   reads the .txt file (parser) and checks it (validator)
  app/engine/          decides which question comes next: skips, show-if, termination, piping, quotas
  app/services/        the business rules: versions, going live, respondents, dashboard, export
  app/api/             the web addresses (endpoints) the screens call
  app/tables.py        the 8 database tables
  tests/               622 automatic tests
frontend/src/
  respondent/          the phone screens: join, one question per screen, end screens
  staff/               the research team's screens: list, upload, editor, preview, dashboard
design/                Day 2 user flow and database diagram (unchanged since Day 2)
docs/                  later notes about the build
samples/               the two questionnaires from the brief
```

---

## 3. Setup and Run

You need **Python 3.11+** and **Node.js 20+** installed. It takes about 3–5 minutes, most of it
spent downloading packages.

```bash
git clone https://github.com/Suraj945gh/Custom-Survey-System.git
cd Custom-Survey-System
```

**Terminal 1: the backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python -m app.seed                # loads the demo data (see section 4)
uvicorn app.main:app --reload     # runs on http://localhost:8000
```

**Terminal 2: the frontend**

```bash
cd frontend
npm install
npm run dev                       # runs on http://localhost:5173
```

Now open **http://localhost:5173** and log in with one of the demo accounts below.

**Useful extras**

| Want to… | Run |
|---|---|
| Start again from clean demo data | `python -m app.seed --reset` (in `backend`) |
| Demo data without the made-up respondents | `python -m app.seed --reset --no-responses` |
| See and try every API endpoint in the browser | open http://localhost:8000/docs |
| Check a questionnaire from the command line | `python -m app.cli check ../samples/concave_broken_questionnaire.txt` |
| Run the backend tests | `pytest` (in `backend`) |
| Run the frontend tests | `npm test` (in `frontend`) |

**Try it on a real phone.** The phone must be on the same Wi-Fi as the computer. Open a survey,
go to **Preview & share**, and open the link marked **"Open on a phone"**. It looks like
`http://192.168.x.x:5173/s/smartphone_study`. If the phone can't load it, allow Node.js through
the Windows firewall for private networks.

---

## 4. Demo Logins and Test Data

| Role | Email | Password | What they can do |
|---|---|---|---|
| **Admin** | `admin@demo.local` | `admin12345` | Everything a researcher can do, **plus** approve versions, go live, change deadlines, close surveys, add team members |
| **Researcher** | `researcher@demo.local` | `research12345` | Upload and fix questionnaires, preview and test, see dashboards, export, copy a survey |
| **Respondent** | no login | | Opens **http://localhost:5173/s/smartphone_study**, types a mobile number, answers |

The login page has a **"Use"** button next to each demo account, so you don't need to type them.

**What the demo data contains**

| Survey | State | Why it's there |
|---|---|---|
| **Smartphone Usage Study** (`samples/concave_sample_questionnaire.txt`) | Approved as v1, **live**, deadline in 15 days, **42 made-up respondents** | Shows a running survey with a full dashboard and a real export |
| **Snack Habits Study** (`samples/concave_broken_questionnaire.txt`) | Draft with **11 errors** | Shows the upload check: every mistake with its line number |

The 42 made-up respondents answered through the same code as real people: 30 completed, 6 were
screened out, and 6 stopped half-way. Two of them answered too fast and two gave the same answer on
every matrix row, so the quality flags have something to show. Their phone numbers start with
`70000`.

**Things to try as a respondent**
- Use any 10-digit number starting with 6–9. A number that **completes** a survey can't join
  another one for 90 days (the cool-off rule), so use a new number for each full test.
- Type age `12`. You get a clear message on the same screen.
- Pick **Other (specify)** in the brands question and type `Nokia`. Later questions then say
  "your Nokia phone".
- Close the page half-way, then open the link again. It continues where you stopped.
- Pick city **Other city**. You are screened out with a polite "not eligible" screen.

---

## 5. Features

### Core features (all from the brief)

| Feature | Status | Notes |
|---|---|---|
| **Upload** a `.txt` questionnaire | ✅ Done | Drag and drop, choose a file, or paste / type into the editor |
| **Upload check** with line numbers | ✅ Done | Finds all 10 planted mistakes in the broken file, each with its line. Suggests fixes ("did you mean `single`?"). Re-checks live while you type |
| **Preview and test mode** | ✅ Done | Runs inside a phone frame with every rule working. Test answers are flagged and never counted. Testers see why a test run ended |
| **Approve and version** | ✅ Done | Approving freezes v1, v2, …. Every response records its version. An identical file can't be approved twice |
| **All 13 question types** | ✅ Done | single, multi (live counter), dropdown (with search), yesno, rating (labelled ends), nps (coloured 0–10), matrix, text, longtext, number, formatted (pincode / phone / email), info, consent |
| **Required questions** | ✅ Done | A clear message on the same screen |
| **Other (specify)** | ✅ Done | The typed text is used on screen, in piping, in "options-from" and in the export (`Other-Nokia`) |
| **None of these** | ✅ Done | Picking it clears every other option |
| **Shuffle** | ✅ Done | Fixed options ("Other", "None") stay last. Each person's order is saved, so Back and resume show the same order |
| **Skip logic and show-if** (AND / OR) | ✅ Done | Brackets and `= != > >= < <=` work too |
| **Termination** with every reason | ✅ Done | All failed rules are kept, joined with `\|` (e.g. `q4: City not in scope \| q5: Not a smartphone user`). Silent termination supported |
| **Piping and options-from** | ✅ Done | `[q7]` shows the earlier answer. options-from shows only what was picked earlier |
| **Many surveys at once** | ✅ Done | Draft / Live / Closed, each with its own target, quotas and deadline |
| **Unique links** | ✅ Done | Each person gets a private token link. Opening it after finishing shows "Already completed" |
| **Closing** | ✅ Done | Closes automatically when the target is reached or the deadline passes, or when an admin closes it. A full quota group screens out new people in that group |
| **Save every answer** | ✅ Done | Each answer is saved the moment it is given |
| **Resume and Back** | ✅ Done | Reopening continues at the next unanswered question. Back keeps every answer |
| **Progress bar and status** | ✅ Done | In progress / Completed / Terminated. Half-filled responses are never counted |
| **End screens** | ✅ Done | Completed, Not eligible, Survey closed (with the reason), Already completed |
| **Live dashboard** | ✅ Done | Started / completed / terminated / in-progress, quota bars (target, done, left), count per reason. Refreshes every 5 seconds |
| **Export CSV and Excel** | ✅ Done | Exactly the brief's format (details in section 8) |
| **Local setup with the sample loaded** | ✅ Done | `python -m app.seed` |
| **3-month cool-off** (from the background section) | ✅ Done | See section 8 |
| **Roles: admin and researcher** | ✅ Done | Admin-only actions are refused by the server, not just hidden |
| **Empty, loading and error states** | ✅ Done | On every screen. If the phone goes offline, the answer stays on screen and is sent again when the person taps Next |

### Bonus features

We picked the bonus features that add real value for little code, and kept the rest for later.

| Feature | Status | Notes |
|---|---|---|
| **Drop-off report** | ✅ Done | Dashboard card: the last question answered by people who are still in progress |
| **Quality flags** | ✅ Done | **Speeder**: under 2 seconds per question, or under a third of the median time once there are 5+ completes. **Straight-lining**: the same answer on every row of a matrix with 3+ rows. Shown on the dashboard and in an export column. Flags never delete a response |
| **Clone** | ✅ Done | "Copy as new wave" opens the questionnaire as a new, separate survey (`smartphone_study_wave2`, "… (Wave 2)") |
| Shuffle matrix rows and save the order | ❌ Not done | The saved-order mechanism already exists for options, so this would be a small step |
| Nested quota (Mumbai + Male) | ❌ Not done | Needs a new quota tag format |
| Balanced AB / BA rotation | ❌ Not done | |
| Two languages | ❌ Not done | |
| Payments and referral rewards (from the background section) | ❌ Not done | See section 9 |

---

## 6. Database Design

The full diagrams are in **[/design](design/)**: [user flow](design/user_flow.md) and
[database](design/database.md), drawn on Day 2. The columns added while building are listed in
[docs/database_build_notes.md](docs/database_build_notes.md). No table was added or removed.

**8 tables, in plain words**

| Table | One row is… | Key links |
|---|---|---|
| `users` | a team member (admin or researcher) | |
| `surveys` | one study, e.g. "Smartphone Usage Study". Holds its status (draft / live / closed), target and deadline | |
| `survey_versions` | one copy of the questionnaire file. A **draft** has no number; approval gives it v1, v2, … and freezes it | → survey |
| `questions` | one question of one version, with its options and rules stored as data (JSON) | → version |
| `quotas` | one quota of one version, e.g. Mumbai = 80 | → version |
| `respondents` | one person, identified by mobile number (used for the 90-day cool-off) | |
| `responses` | one person taking one survey: the token link, the **version** they answered, status, end reasons, test flag | → survey, version, respondent |
| `answers` | one answer to one question, saved the moment it is given | → response, question |

```
users
surveys ──< survey_versions ──< questions ──< answers >── responses >── respondents
                    │                                        │
                    └──< quotas                              └── also points to survey + version
```
(`──<` means "one to many": one survey has many versions, one version has many questions, and so on.)

**Why this shape?**
- **The questionnaire is stored as data, not code** (the brief's Safety Rule). Every survey is
  shown by the same screens, which read the `questions` rows.
- **Versions are frozen copies.** A response points at the exact version it answered, so changing
  the file later can never change what an old answer meant.
- **One answer row per question**, written immediately. If a phone dies at q14, q1–q13 are already
  in the database.
- **The database itself stops duplicates:** one response per person per survey, one answer per
  question per response, one question id per version.

---

## 7. API Endpoints

All addresses start with `http://localhost:8000`. Staff endpoints need the header
`Authorization: Bearer <token>`, which you get from the login endpoint. Respondent endpoints
(`/api/public/...`) need no login: the token in the link is the key.

Every error comes back as plain JSON, never as a crash, for example:
`{"detail": "Only an admin can do this."}`. The status codes are 401 (not logged in), 403 (not
allowed), 404 (not found), 409 (not possible right now) and 422 (bad input).

You can also try every endpoint in the browser at **http://localhost:8000/docs**.

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

### The open question from the brief: what happens to in-progress responses?

**When version 2 is approved while someone is half-way through version 1:**
they **finish on version 1**. Every response is pinned to the version it started on, and their
link keeps showing version 1 questions. New people get version 2. The export has a **Version**
column, so analysts can see which version each row answered.
*Why:* switching someone to v2 half-way could ask questions their earlier answers don't fit, or
skip questions v2 needs. Pinning keeps every response consistent.

**When the survey closes while someone is half-way:**
reopening the link shows **"This survey is closed"** with the reason (target reached, deadline
passed, or closed by the team). Their partial answers are **kept but never counted**. They stay
"In progress", don't count towards quotas, and are not in the export.
*Why:* the brief says half-filled responses are never complete, and the company pays only for
complete participation. Keeping the data still lets the team see where people stopped.

### Other decisions

| Topic | What we decided | Why |
|---|---|---|
| **Checking the file** | A custom reader that keeps line numbers, then exact rule checks. Suggestions like "did you mean `single`?" use simple text similarity. **No AI** | The file is *almost* XML but not quite (`required` has no value, `Haldiram's` has an apostrophe), so a normal XML reader would stop at the first problem. The brief wants every problem with its line |
| **Errors vs warnings** | Errors block approval. Warnings (e.g. a quota bigger than the target) are shown but allowed | Some odd things are intentional; real mistakes must be fixed |
| **Drafts and versions** | Edits before approval change one draft. A version number is given **only on approval** and then frozen. Uploading a file whose `<survey id>` already exists creates a new draft of *that* survey | "A changed file creates a new version" without creating a version for every typo |
| **Several termination reasons** | During the **screening part** (up to the last question with a termination rule or quota), failed rules are collected. When the person leaves that part, they are screened out with **all** reasons joined by `\|`. Consent "No" ends immediately | The brief asks to keep every reason. Going Back and changing an answer clears its reason |
| **Quotas** | Only completes count. A full quota group screens out new people in that group with the reason `q3: Quota full (Male)`. The final check happens inside a database transaction, so two people can't take the last place | Matches "each quota group closes when its target is reached" |
| **Unique links and the 3-month cool-off** | The share link `/s/<survey>` asks for a mobile number, then gives a personal token link. The same number on the same survey gets the same link back. A number that **completed** any survey in the last 90 days is told when it can join again. Screen-outs and test runs don't trigger the cool-off | The background says people can't join another survey for 3 months. A phone number is the simplest identity that works on mobile |
| **Roles** | **Researcher**: upload, edit, preview, dashboard, export. **Admin**: also approve, go live, deadlines, close, team | Going live affects payments and data, so it needs a second pair of eyes |
| **Deadline** | 15 days after going live by default (the company's project cycle). The admin can change it | From the background section |
| **Closing on deadline** | Checked whenever the survey is read. No background job | Simpler, and nothing can slip through |
| **Export format** | One row per **completed** response. Columns: Respondent ID, Version, Completed at, Quality flags, then `Q6. <full text>` columns. Multi-select: one column per option (the option name or blank). Other: `Other-Nokia`. Matrix: one column per row. Info screens: no column | Exactly the brief's table, plus Quality flags |
| **Export across versions** | Headers use the newest wording. A column that one version didn't have stays blank | Same question id = same question |
| **Other (specify) in options-from** | The typed text becomes the option ("Nokia", not "Other (specify)") | The brief says the typed text is used everywhere |
| **Test runs** | Stored like responses but flagged `is_test`. Never in counts, quotas or exports. Saving a new draft deletes its old test runs | "Test answers are kept apart and never counted" |
| **Times** | Stored in UTC. Shown in the viewer's local time on screen. The export's "Completed at" is in UTC | One clear rule for every survey |

---

## 9. Known Issues and Next Steps

**Known limits (honest list)**
- **Phone numbers are not verified.** Anyone can type any number, so the cool-off rule trusts the
  number given. Next step: a one-time SMS code.
- **Runs on one computer.** The phone link works on the same Wi-Fi. A real launch needs hosting
  with HTTPS, a strong `SECRET_KEY` setting and PostgreSQL instead of SQLite. Only the database
  setting changes; the code stays the same.
- **Team members can be added but not edited or switched off from the screen.** The database
  already supports switching an account off (`is_active`).
- **Quality flag thresholds are fixed in code** (2 seconds per question, a third of the median).
  They should become settings per survey.
- **The drop-off report** counts people who are still in progress. It doesn't yet show a full
  question-by-question funnel.

**What we would build next, in order**
1. **Payments for completes and referral rewards** (from the background: the company pays only for
   complete participation and pays for referrals). The data is ready for this: every completed
   response has a respondent and a time.
2. Respondent profile and status page, so people stop calling the team about payments and survey status.
3. Nested quotas, shuffled matrix rows, balanced AB/BA rotation, and a second language.
4. One-time SMS codes, hosting, and PostgreSQL.
