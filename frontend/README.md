# RehabTwin Therapist View

Build the Week 1 Therapist Dashboard for my project RehabTwin.

Use the uploaded image as the primary visual reference. Recreate its overall layout, visual hierarchy, spacing, sidebar, cards, patient list, session information, charts, session comparison and recent sessions.

IMPORTANT:

This is ONLY the Week 1 frontend. Do not build the complete RehabTwin platform yet.

TECH STACK:

- React

- TypeScript

- Vite

- Tailwind CSS

- Recharts

- Lucide React

The future backend will be Python FastAPI.

For now, use mock data only.

WEEK 1 REQUIREMENTS:

1. Therapist Dashboard

Create a professional healthcare dashboard with:

- Sidebar

- Dashboard

- Patients

- Sessions

- Exercises

- Alerts

- Reports

- Analytics

- Settings

2. Patient List

Create mock patients:

P001 — Patient 001

P002 — Patient 002

P003 — Patient 003

P004 — Patient 004

P005 — Patient 005

The therapist must be able to select a patient.

3. Patient Details

When a patient is selected, display:

- Patient ID

- Name

- Age

- Condition

- Rehabilitation start date

- Number of sessions

- Recovery score

- Status

4. Latest Session

Display:

- Exercise

- Repetitions

- ROM

- Movement Quality

- Performance Score

- Date/time

Example:

Exercise: Elbow Flexion

Repetitions: 10

ROM: 148.5°

Movement Quality: Good

Performance Score: 87

5. Progress Charts

Create:

- ROM trend across sessions

- Performance score trend across sessions

Use this mock data:

Session 1: ROM 130°, Score 72

Session 2: ROM 138°, Score 76

Session 3: ROM 142°, Score 81

Session 4: ROM 148°, Score 87

6. Session Comparison

Allow the therapist to select two sessions and compare:

- Repetitions

- ROM

- Movement Quality

- Performance Score

- Date

Show improvement values where appropriate.

7. Recent Sessions

Create a table showing:

- Session

- Date/time

- Exercise

- Repetitions

- ROM

- Quality

- Score

8. Mock Data Architecture

DO NOT hardcode data directly inside UI components.

Create a separate mock data layer, for example:

src/data/mockData.ts

Create TypeScript interfaces/types, for example:

src/types/rehab.ts

Use reusable components for:

- PatientList

- PatientDetails

- LatestSession

- ProgressCharts

- SessionComparison

- RecentSessions

- MetricCard

- Sidebar

IMPORTANT BACKEND PREPARATION:

The frontend will later connect to:

React

↓

FastAPI

↓

PostgreSQL

Do not implement the backend now.

Do not connect to PostgreSQL.

Do not create fake API endpoints.

Keep the data access layer separated so that mock data can later be replaced with FastAPI API calls without rewriting the UI components.

Add a clearly visible:

"Mock Data — Demo Mode"

indicator.

DESIGN:

- Match the uploaded reference image closely

- Professional healthcare/clinical appearance

- Dark navy/indigo sidebar

- Light main content area

- Purple/blue primary accents

- Green for improving/good

- Orange/red for attention

- Rounded cards

- Clean typography

- Responsive design

- Desktop-first

- Minimal animations

- Prioritize usability

DO NOT IMPLEMENT YET:

- Patient Dashboard

- AI recovery prediction

- AI recommendations

- Medical diagnosis

- IMU integration

- EMG integration

- Smartwatch integration

- Real sensor data

- PostgreSQL

- FastAPI backend

- Real authentication

- 3D Digital Twin

SUCCESS CRITERIA:

When I run the application:

Therapist Dashboard

↓

Select P001

↓

Patient details update

↓

Latest session updates

↓

ROM and score charts update

↓

Select Session 1 + Session 4

↓

Comparison updates

↓

Recent sessions are displayed

The application must be functional, not just a static UI.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/bef7512d-1bd1-4999-b312-2092ea5630e9).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
