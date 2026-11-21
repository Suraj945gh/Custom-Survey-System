# Database Design

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
erDiagram
  USERS ||--o{ SURVEYS : "creates"
  SURVEYS ||--o{ SURVEY_VERSIONS : "has"
  SURVEY_VERSIONS ||--o{ QUESTIONS : "contains"
  SURVEY_VERSIONS ||--o{ QUOTAS : "has"
  SURVEYS ||--o{ RESPONSES : "gets"
  SURVEY_VERSIONS ||--o{ RESPONSES : "answered on"
  RESPONDENTS ||--o{ RESPONSES : "gives"
  RESPONSES ||--o{ ANSWERS : "has"
  QUESTIONS ||--o{ ANSWERS : "answer to"

  USERS {
    int id PK
    string email
    string role "admin or researcher"
  }
  SURVEYS {
    int id PK
    string title
    string status "draft, live, closed"
    int target
    datetime deadline
  }
  SURVEY_VERSIONS {
    int id PK
    int survey_id FK
    int version_no "empty until approved"
    text file_text "the uploaded .txt"
    int approved_by FK
  }
  QUESTIONS {
    int id PK
    int version_id FK
    string qid "q1, q2 ..."
    string type
    text text
    json options
    json rules "show-if, skip, terminate"
  }
  QUOTAS {
    int id PK
    int version_id FK
    string question_qid
    string value "Mumbai"
    int target
  }
  RESPONDENTS {
    int id PK
    string phone "for the 3-month rule"
  }
  RESPONSES {
    int id PK
    string token "personal link"
    int survey_id FK
    int version_id FK
    int respondent_id FK
    string status "in progress, completed, terminated"
    string end_reasons "all failed rules"
    bool is_test
  }
  ANSWERS {
    int id PK
    int response_id FK
    int question_id FK
    json value
    string other_text
  }
```

## In plain words

- A **survey** has one or more **versions**. Each version is one uploaded `.txt` file. It gets a
  version number only when an admin approves it, and after that it never changes.
- A version's **questions** and **quotas** are stored as rows, so the same code can show any survey.
- A **respondent** is one person, known by their phone number. This gives us the 3-month rule and
  "one link per person".
- A **response** is one respondent's attempt at one survey. It remembers which version they
  answered, so someone halfway through version 1 can finish on version 1 even after version 2 is out.
- Every **answer** is its own row, saved the moment it is given. If a phone dies at q14, q1 to q13
  are already saved.
- Test runs from preview are marked `is_test` and never counted.
