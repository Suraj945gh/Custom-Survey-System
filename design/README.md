# /design

Day 2 design for the Custom Survey System.

| File | What it shows |
|---|---|
| [user_flow.md](user_flow.md) | How the research team and the respondent move through the app |
| [database.md](database.md) | The tables and how they connect |
| [diagrams/](diagrams/) | Source of each diagram (Mermaid) |

## Main decisions

1. **Two staff roles.** A researcher uploads, fixes, previews and exports. An admin also approves,
   puts surveys live and closes them. Respondents use a personal link and never log in.
2. **A version number is given only on approval.** Edits before that change the same draft.
3. **Halfway when version 2 is approved:** the person finishes on the version they started.
4. **Halfway when the survey closes:** opening the link shows "Survey closed" and why. Their partial
   answers are kept but never counted as complete.
5. **More than one termination reason:** screening finishes first, then every failed rule is saved
   together, separated by `|`.
6. **3-month cool-off:** a phone number that completed any survey in the last 90 days must wait.
7. **Deadline:** 15 days after going live by default. The admin can change it.
