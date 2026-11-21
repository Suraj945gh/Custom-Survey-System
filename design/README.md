# /design

Day 2 design for the Custom Survey System. Frozen after Day 2; later changes go in new files under `docs/`.

| File | What it shows |
|---|---|
| [user_flow.md](user_flow.md) | Screen map, life of a survey (draft → approve → version → live → closed), respondent journey, the next-question engine, statuses |
| [database.md](database.md) | Database diagram (ER), how the tables connect, and the rules the schema enforces |
| [diagrams/](diagrams/) | Mermaid sources for every diagram |

## Decisions shown in this design

1. **Two staff roles.** Researchers upload, fix, preview, follow the dashboard and export. Admins
   also approve versions, put surveys live, set deadlines, close surveys and manage users.
   Respondents never log in; they use a personal link.
2. **Versions only on approval.** Uploads and in-app edits before approval change one draft. An
   admin approval freezes it as v1, v2, ...
3. **Mid-way when v2 is approved:** the respondent finishes on the version they started. New
   respondents get the new version.
4. **Mid-way when the survey closes:** reopening the link shows "Survey closed" with the reason
   (target reached, deadline passed, or closed by the team). Partial answers stay saved as
   In progress and are never counted as complete.
5. **Several termination reasons:** the screening section is finished first, then the person is
   ended with every failed rule joined by `|`. Consent "No" ends at once.
6. **3-month cool-off:** the join page asks for a phone number. A phone that completed any survey in
   the last 90 days is told when it can take part again. Only completes count (screened-out
   people were never paid).
7. **Deadline:** defaults to go-live + 15 days (the project cycle); the admin can change it. A survey
   also closes early when its total target is reached.
