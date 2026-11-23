# Database: what the build adds to the Day 2 design

`/design/database.md` is the Day 2 design and is kept unchanged. The real tables
([backend/app/tables.py](../backend/app/tables.py)) follow it: the same 8 tables and the same
relations. They add the practical columns below. No table was added or removed.

| Table | Added columns | Why |
|---|---|---|
| users | `name`, `password_hash`, `is_active`, `created_at` | Log in with a hashed password; switch an account off without deleting its history |
| surveys | `slug`, `created_by_id`, `created_at`, `live_at`, `closed_at`, `closed_reason` | `slug` is the `<survey id>` from the file, used to match a re-upload to its survey. `closed_reason` is `closed_by_team`, `deadline_passed` or `target_reached`, shown to respondents who reopen their link |
| survey_versions | `file_name`, `created_by_id`, `created_at`, `updated_at`, `approved_at` | Who uploaded and approved what, and when |
| questions | `position`, `required`, `rows`, `line` | Question order; matrix rows; the line in the file, so the screens can point back to it |
| responses | `option_orders`, `silent_end`, `started_at`, `updated_at`, `ended_at` | `option_orders` saves each respondent's shuffled option order, so Back and resume show the same order. `silent_end` marks a `silent="true"` screen-out: the person sees a normal thank-you, and the reason is still saved |
| answers | `answered_at` | Time of each answer (for the drop-off and speeder checks) |

## Rules enforced by the database

- One draft per survey. A draft is a version row with `version_no` empty. `version_no` is unique per survey.
- One question id per version: `(version_id, qid)` is unique.
- One response per person per survey: `(survey_id, respondent_id)` is unique. Test runs have no respondent.
- One answer per question per response: `(response_id, question_id)` is unique. Changing an answer updates that row.
- Deleting a draft deletes its questions, its quotas and its test runs (foreign keys use `ON DELETE CASCADE`).

## Why questions are stored for drafts too

When a draft has no errors, its questions are written to the `questions` table right away. Preview
and test mode can then run through the same engine as a live survey. Every save of the draft
rebuilds these rows and removes old test runs, because they no longer match. Once approved, the rows
never change again.
