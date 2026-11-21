# User Flow

Main screens, who uses them, and the steps a survey and a respondent go through.
Diagram sources live in [`diagrams/`](diagrams/) (`.mmd`); GitHub renders the blocks below.

## 1. Screen map

Two apps in one frontend: a **staff app** (login: Admin or Researcher) and a **respondent app**
(phone-first, no login, reached by link).

```mermaid
flowchart LR
  subgraph STAFF["Staff app · login required"]
    direction TB
    L["Login"] --> SL["Surveys list<br/>status · progress · deadline"]
    SL --> UP["Upload or edit questionnaire<br/>(.txt upload or in-app editor)"]
    UP --> CK["Check results<br/>errors with line numbers"]
    CK --> UP
    SL --> SD["Survey detail"]
    SD --> D1["Live dashboard"]
    SD --> D2["Versions<br/>draft · v1 · v2 …"]
    SD --> D3["Preview / test mode"]
    SD --> D4["Share link"]
    SD --> D5["Export CSV / Excel"]
    SL --> US["Team users<br/>(admin only)"]
  end
  subgraph RESP["Respondent · phone · no login"]
    direction TB
    J["Join page<br/>/s/survey-id"] --> QS["Question screen<br/>/r/token"]
    QS --> EN["End screens<br/>Completed · Not eligible ·<br/>Survey closed · Already completed"]
  end
  D4 -. "link posted on social media" .-> J
```

## 2. Life of a survey (staff side)

Uploads and edits before approval only change the **draft**. A version number (v1, v2, ...) is
given **only when an admin approves**, and an approved version is frozen forever.

```mermaid
flowchart TD
  A["Researcher uploads .txt<br/>or pastes it into the editor"] --> B{"Checker"}
  B -- "errors found" --> C["Draft + error list<br/>line numbers · did-you-mean hints<br/>Approve button disabled"]
  C --> D["Fix in the in-app editor<br/>or upload a corrected file<br/>(replaces the draft, no new version)"]
  D --> B
  B -- "no errors" --> E["Draft ready<br/>(no version number yet)"]
  E --> F["Preview / test mode<br/>test answers kept apart, never counted"]
  F -- "wants a change" --> D
  F --> G{"Admin approves?"}
  G -- "no, send back" --> D
  G -- "yes" --> H["Frozen as next version<br/>v1, then v2, v3 …"]
  H --> I{"Survey status"}
  I -- "Draft (first approval)" --> J["Admin sets deadline<br/>default = today + 15 days<br/>then Go live"]
  I -- "already Live" --> K["New version becomes current<br/>new respondents get it ·<br/>people mid-way stay on their version"]
  J --> L(["LIVE"])
  K --> L
  L -. "researcher uploads a changed file<br/>(same survey id)" .-> D
  L --> M{"Close trigger"}
  M -- "total target reached" --> N(["CLOSED"])
  M -- "deadline passed" --> N
  M -- "admin closes it" --> N
  N --> O["Dashboard and export<br/>stay available"]
```

| Step | Researcher | Admin |
|---|:---:|:---:|
| Upload / edit questionnaire, see check results | ✅ | ✅ |
| Preview and test mode | ✅ | ✅ |
| Approve a draft (freeze as a version) | ❌ | ✅ |
| Go live, set or extend the deadline, close a survey | ❌ | ✅ |
| Dashboard and export | ✅ | ✅ |
| Manage team users | ❌ | ✅ |

## 3. Respondent journey (phone)

```mermaid
flowchart TD
  S["Sees the survey post<br/>on social media"] --> J["Join page<br/>title · time needed · phone number"]
  J --> C1{"Survey live?"}
  C1 -- "no" --> E1["Survey closed<br/>+ why: target reached,<br/>deadline passed or closed by team"]
  C1 -- "yes" --> C2{"This phone already has<br/>a response for this survey?"}
  C2 -- "yes" --> R["Open their own link<br/>/r/token"]
  C2 -- "no" --> C3{"Completed any survey<br/>in the last 90 days?"}
  C3 -- "yes" --> E2["Not eligible right now<br/>can take part again after a date"]
  C3 -- "no" --> N["Create response on the current version<br/>+ unique token"]
  N --> R
  R --> C4{"Response status"}
  C4 -- "completed" --> E3["Already completed"]
  C4 -- "terminated" --> E4["Not eligible"]
  C4 -- "in progress, but survey closed" --> E1
  C4 -- "in progress" --> Q["Next unanswered question<br/>progress bar · Back keeps answers"]
  Q -- "answer saved instantly" --> EN{"Engine:<br/>what next?"}
  EN -- "another question" --> Q
  EN -- "rules failed at end of screening<br/>or quota group full" --> E4
  EN -- "last question answered" --> E5["Completed · thank you"]
```

End screens: **Completed**, **Not eligible**, **Survey closed** (with the reason), **Already
completed**, and **Not eligible right now** (3-month cool-off).

## 4. What happens after every answer (the engine)

One backend function decides the next step from the saved answers, so the phone keeps no state
and a refresh or a dead battery loses nothing.

```mermaid
flowchart TD
  A["Answer arrives for question X"] --> V{"Valid?<br/>required · min/max · minlength ·<br/>format · max picks · exclusive"}
  V -- "no" --> VE["Message on the same screen<br/>nothing saved"]
  V -- "yes" --> S["Save answer<br/>one row per response + question,<br/>updated if changed via Back"]
  S --> CN{"Consent answered No?"}
  CN -- "yes" --> T1["Terminate now<br/>reason: no consent"]
  CN -- "no" --> R["Re-check every terminate-on rule<br/>and every full quota group<br/>against ALL current answers"]
  R --> N["Find next question:<br/>option skip-to, else next in order;<br/>skip questions whose show-if is false"]
  N --> SE{"Any failed rules AND<br/>screening section finished?"}
  SE -- "yes" --> T2["Terminate with every reason<br/>joined by a pipe, e.g.<br/>q4: City not in scope | q5: Not a smartphone user"]
  SE -- "no" --> L{"Next question exists?"}
  L -- "yes" --> NX["Send next question<br/>with piping and options-from applied<br/>Other text used everywhere"]
  L -- "no" --> FQ{"Final quota check<br/>inside a DB transaction"}
  FQ -- "a group filled meanwhile" --> T2
  FQ -- "ok" --> C["Completed"]
```

**Screening section** = every question up to and including the last question that has a
`terminate-on` rule or a quota. For the sample file that is q0 to q5. Failed rules are collected
while the person is in the screening section, and they are ended once it is over, so every reason
is saved (`q4: City not in scope | q5: Not a smartphone user`). Consent "No" ends at once.

## 5. Statuses

```mermaid
stateDiagram-v2
  direction LR
  state Survey {
    [*] --> Draft
    Draft --> Live: admin goes live (needs an approved version)
    Live --> Closed: target reached / deadline / admin
  }
  state Questionnaire_version {
    [*] --> Draft_copy: upload or edit
    Draft_copy --> Draft_copy: re-check after each edit
    Draft_copy --> Approved: admin approves (numbered, frozen)
  }
  state Response {
    [*] --> In_progress: respondent joins
    In_progress --> Completed: last question answered
    In_progress --> Terminated: rules failed or quota full
  }
```
