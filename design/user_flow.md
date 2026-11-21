# User Flow

There are two kinds of people in this app:

- **The research team** logs in. A **researcher** uploads, fixes and previews surveys. An
  **admin** can do all of that, and also approves surveys, puts them live and closes them.
- **The respondent** never logs in. They open a link on their phone and answer.

## 1. Research team

```mermaid
---
config:
  theme: base
  themeVariables:
    fontFamily: "Segoe UI, Helvetica, Arial, sans-serif"
    primaryColor: "#ffffff"
    secondaryColor: "#ffffff"
    tertiaryColor: "#ffffff"
    mainBkg: "#ffffff"
    nodeBorder: "#000000"
    primaryBorderColor: "#000000"
    primaryTextColor: "#000000"
    nodeTextColor: "#000000"
    textColor: "#000000"
    lineColor: "#888888"
    edgeLabelBackground: "#ffffff"
    relationLabelBackground: "#ffffff"
    relationLabelColor: "#000000"
    attributeBackgroundColorOdd: "#ffffff"
    attributeBackgroundColorEven: "#ffffff"
---
flowchart TD
  A["Write the questionnaire<br/>as a .txt file"] --> B["Upload it in the app"]
  B --> C{"Is the file OK?"}
  C -- "No" --> D["See every error with its line number<br/>fix it in the app's editor"]
  D --> C
  C -- "Yes" --> E["Preview it like a respondent<br/>(test answers are not counted)"]
  E --> F["Admin approves it<br/>→ saved and locked as Version 1"]
  F --> G["Admin makes it Live<br/>deadline = 15 days by default"]
  G --> H["Share the survey link<br/>on social media"]
  G --> I["Watch the live dashboard"]
  I --> J{"Target reached, deadline over,<br/>or admin closes it?"}
  J -- "No" --> I
  J -- "Yes" --> K["Survey closed"]
  K --> L["Download results<br/>as CSV or Excel"]
  G -. "file changed later" .-> M["New draft → admin approves<br/>→ Version 2"]
```

A survey is **Draft** until an admin approves it and puts it live, then **Live**, then **Closed**.
A version number is given only when an admin approves. Before that, every upload or fix just
updates the same draft.

## 2. Respondent (on a phone)

```mermaid
---
config:
  theme: base
  themeVariables:
    fontFamily: "Segoe UI, Helvetica, Arial, sans-serif"
    primaryColor: "#ffffff"
    secondaryColor: "#ffffff"
    tertiaryColor: "#ffffff"
    mainBkg: "#ffffff"
    nodeBorder: "#000000"
    primaryBorderColor: "#000000"
    primaryTextColor: "#000000"
    nodeTextColor: "#000000"
    textColor: "#000000"
    lineColor: "#888888"
    edgeLabelBackground: "#ffffff"
    relationLabelBackground: "#ffffff"
    relationLabelColor: "#000000"
    attributeBackgroundColorOdd: "#ffffff"
    attributeBackgroundColorEven: "#ffffff"
---
flowchart TD
  A["Opens the survey link<br/>on their phone"] --> B["Types their phone number"]
  B --> C{"Can they take part?"}
  C -- "Survey is closed" --> X1["Survey closed<br/>(shows why)"]
  C -- "Took a survey in<br/>the last 3 months" --> X2["Not eligible right now"]
  C -- "Already finished<br/>this survey" --> X3["Already completed"]
  C -- "Yes" --> D["Gets their own personal link"]
  D --> E["Answers one question per screen<br/>each answer is saved instantly"]
  E --> F{"After each answer"}
  F -- "next question" --> E
  F -- "failed a screening rule<br/>or quota is full" --> X4["Not eligible<br/>(reason saved)"]
  F -- "all questions done" --> X5["Thank you!<br/>Completed"]
  E -. "phone dies, opens link again" .-> E
```

A response is always **In progress**, **Completed** or **Terminated**.

## 3. What happens after each answer

```mermaid
---
config:
  theme: base
  themeVariables:
    fontFamily: "Segoe UI, Helvetica, Arial, sans-serif"
    primaryColor: "#ffffff"
    secondaryColor: "#ffffff"
    tertiaryColor: "#ffffff"
    mainBkg: "#ffffff"
    nodeBorder: "#000000"
    primaryBorderColor: "#000000"
    primaryTextColor: "#000000"
    nodeTextColor: "#000000"
    textColor: "#000000"
    lineColor: "#888888"
    edgeLabelBackground: "#ffffff"
    relationLabelBackground: "#ffffff"
    relationLabelColor: "#000000"
    attributeBackgroundColorOdd: "#ffffff"
    attributeBackgroundColorEven: "#ffffff"
---
flowchart TD
  A["Respondent answers a question"] --> B{"Is the answer valid?<br/>required, min/max, format"}
  B -- "No" --> B1["Show a message<br/>on the same screen"]
  B -- "Yes" --> C["Save the answer right away"]
  C --> D{"Consent = No?"}
  D -- "Yes" --> T1["End: Not eligible"]
  D -- "No" --> E["Note any failed screening rule<br/>or full quota"]
  E --> F["Pick the next question<br/>using skip-to and show-if"]
  F --> G{"Screening over and<br/>a rule failed?"}
  G -- "Yes" --> T2["End: Not eligible<br/>all reasons saved together"]
  G -- "No" --> H{"Any question left?"}
  H -- "Yes" --> I["Show it, with piping<br/>e.g. your Samsung phone"]
  H -- "No" --> J["End: Completed"]
```

- **Skip-to and show-if** decide which question comes next.
- **Piping** puts an earlier answer into the text ("How happy are you with your *Samsung* phone?").
- **Screening:** while the person is in the first few screening questions, every failed rule is
  noted. When screening ends, they are stopped with all the reasons together
  (`q4: City not in scope | q5: Not a smartphone user`). Consent "No" stops them at once.
