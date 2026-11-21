# Database Design

SQLite (via SQLAlchemy). The diagram source is [`diagrams/06_database.mmd`](diagrams/06_database.mmd).

```mermaid
erDiagram
  USERS ||--o{ SURVEYS : "creates"
  USERS ||--o{ QUESTIONNAIRE_VERSIONS : "uploads / approves"
  SURVEYS ||--o{ QUESTIONNAIRE_VERSIONS : "has"
  SURVEYS |o--o| QUESTIONNAIRE_VERSIONS : "current version"
  QUESTIONNAIRE_VERSIONS ||--o{ QUESTIONS : "contains"
  QUESTIONS ||--o{ OPTIONS : "has"
  QUESTIONS ||--o{ MATRIX_ROWS : "has"
  QUESTIONNAIRE_VERSIONS ||--o{ QUOTAS : "defines"
  QUOTAS ||--|{ QUOTA_CONDITIONS : "matches on"
  SURVEYS ||--o{ RESPONSES : "receives"
  QUESTIONNAIRE_VERSIONS ||--o{ RESPONSES : "answered on"
  RESPONDENTS ||--o{ RESPONSES : "gives"
  RESPONSES ||--o{ ANSWERS : "contains"
  QUESTIONS ||--o{ ANSWERS : "answered in"
  RESPONSES ||--o{ TERMINATION_REASONS : "records"
  QUESTIONS |o--o{ TERMINATION_REASONS : "caused by"

  USERS {
    int id PK
    string email UK
    string name
    string password_hash
    string role "admin or researcher"
    datetime created_at
  }
  SURVEYS {
    int id PK
    string slug UK "survey id from the file"
    string title
    string status "draft, live, closed"
    int target "total completes wanted"
    datetime deadline_at "default go-live + 15 days"
    int current_version_id FK
    string closed_reason "target_reached, deadline, admin"
    datetime opened_at
    datetime closed_at
    int created_by FK
  }
  QUESTIONNAIRE_VERSIONS {
    int id PK
    int survey_id FK
    int version_no "null while draft"
    string status "draft, approved"
    text source_text "raw .txt as uploaded"
    string source_hash
    json issues "checker errors and warnings"
    int screener_end_position
    int uploaded_by FK
    int approved_by FK
    datetime uploaded_at
    datetime approved_at
  }
  QUESTIONS {
    int id PK
    int version_id FK
    string qid "q1, q2 ..."
    int position
    string type
    text text "may contain piping"
    bool required
    string show_if "q12=Yes AND q4=Mumbai"
    string terminate_on
    string terminate_reason
    bool terminate_silent
    string options_from_qid
    bool shuffle
    json limits "min, max, minlength, format, labels"
    int source_line
  }
  OPTIONS {
    int id PK
    int question_id FK
    int position
    string label
    bool fixed
    bool is_other
    bool exclusive
    string skip_to_qid
  }
  MATRIX_ROWS {
    int id PK
    int question_id FK
    int position
    string label
  }
  QUOTAS {
    int id PK
    int version_id FK
    string label "Mumbai"
    int target
  }
  QUOTA_CONDITIONS {
    int id PK
    int quota_id FK
    string question_qid
    string value
  }
  RESPONDENTS {
    int id PK
    string phone UK "identity for cool-off"
    datetime created_at
  }
  RESPONSES {
    int id PK
    string token UK "the unique link"
    int survey_id FK
    int version_id FK
    int respondent_id FK "null for test runs"
    bool is_test
    string status "in_progress, completed, terminated"
    string termination_summary "reasons joined by pipe"
    json display_order "shuffled options and rows seen"
    datetime started_at
    datetime last_answered_at
    datetime finished_at
  }
  ANSWERS {
    int id PK
    int response_id FK
    int question_id FK
    json value "text, number, list or row map"
    string other_text
    datetime answered_at
    datetime updated_at
  }
  TERMINATION_REASONS {
    int id PK
    int response_id FK
    int question_id FK "null for quota-full at end"
    string reason
    bool silent
  }
```

## How the tables fit together

| Group | Tables | Idea |
|---|---|---|
| Staff | `users` | One table, `role` = admin or researcher. |
| Survey definition | `surveys` → `questionnaire_versions` → `questions` → `options`, `matrix_rows`; `quotas` → `quota_conditions` | A survey is the long-lived project (status, target, deadline). Each upload is a version row. The parsed file is stored as rows so the same code renders every survey. |
| People | `respondents` | One row per phone number. Used for the 3-month cool-off and "one link per person per survey". |
| Answers | `responses` → `answers`, `termination_reasons` | One response = one person's attempt at one survey. One answer row per question, written the moment it is given. |

## Key rules the schema enforces

- **Versions are immutable once approved.** Re-uploading before approval overwrites the draft row.
  Approval sets `version_no = max + 1`, and the questions, options and quotas of that version are
  never edited again. `source_text` keeps the exact file that was approved.
- **Every response records its version** (`responses.version_id`). A respondent mid-way through v1
  stays on v1 after v2 is approved. Export adds a `Version` column.
- **One response per person per survey:** unique (`survey_id`, `respondent_id`). Reopening the
  link resumes it, or shows "Already completed".
- **One answer per question per response:** unique (`response_id`, `question_id`). Going Back and
  changing an answer updates the row (`updated_at`), so nothing is lost or duplicated.
- **Test runs never count:** `is_test = true`, no respondent row. They are excluded from
  dashboards, quotas, exports and the cool-off rule.
- **Quotas count across versions.** A quota group is matched by question id + value
  (`quota_conditions`) over completed, non-test responses of the survey, whatever version they
  answered. Several conditions on one quota give nested quotas (Mumbai + Male = 25).
- **Termination keeps every reason:** one `termination_reasons` row each (for the dashboard
  counts) plus `termination_summary` joined by `|` (for the export).
- **Shuffled order is saved** in `responses.display_order`, so Back and resume show the same order.

## Why rows instead of one JSON blob per version

Answers point at a real `questions.id`, so exports, dashboards and drop-off reports are plain SQL
joins, and a deleted or mistyped question can never silently orphan answers. The raw `.txt` is
still stored, so any version can be re-parsed or downloaded exactly as approved.
