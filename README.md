## 1. Project Overview

A web app where the research team uploads a questionnaire written as a plain `.txt` file. The app checks the file and lists every error with its line number. Researchers can preview the survey as a test respondent, then approve it as a frozen version and run it live alongside other surveys.

Respondents answer on their phones through a personal link, every answer is saved the moment it is given, and researchers follow a live dashboard and export clean data in one standard CSV / Excel format.

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI |
| Database | SQLite via SQLAlchemy |
| Frontend | React + Vite + TypeScript, Tailwind CSS |
| Main libraries | _TBD_ |

## 3. Setup and Run

_TBD: step-by-step commands to run locally in under 5 minutes, with the sample survey preloaded._

## 4. Demo Logins and Test Data

| Role | Can do | Login |
|---|---|---|
| Admin | Everything a researcher can, plus approve versions, put surveys live, set deadlines, close surveys, manage users | _TBD_ |
| Researcher | Upload and fix questionnaires, preview / test, dashboard, export | _TBD_ |
| Respondent | No login. Opens a personal survey link on their phone | _TBD: demo link_ |

Test files: [`samples/concave_sample_questionnaire.txt`](samples/concave_sample_questionnaire.txt)
(valid, preloaded) and [`samples/concave_broken_questionnaire.txt`](samples/concave_broken_questionnaire.txt)
(upload it to see the error check).

## 5. Features

_TBD: every core and bonus feature marked Done / Partly done / Not done._

## 6. Database Design

See the [`/design`](design/) folder for the user flow and database diagram.

_TBD: summary of main tables and how they connect._

## 7. API Endpoints

_TBD: method, URL, purpose, sample request and response for each endpoint._

## 8. Assumptions and Decisions

The design-time decisions are listed in [`design/README.md`](design/README.md). Full reasoning
for each will be written here as features are built.

_TBD_

## 9. Known Issues and Next Steps

_TBD_
