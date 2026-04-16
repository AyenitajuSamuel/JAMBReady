# ExamReady

JAMBReady is a Django web app for JAMB exam preparation. Students register, pick their 4 JAMB subjects, then take practice exams drawn from a bank of past questions. The app tracks performance over time and surfaces personalised recommendations based on what each user is getting wrong.

---

## Tech Stack

- **Python 3.12+** / **Django 6.0**
- SQLite (default, swappable for Postgres in production)
- Pillow for avatar uploads
- HTML with inline JS
-   CSS
---

## Project Layout

```
JAMBReady/          # Django project settings, URLs, wsgi/asgi
exam/               # Exam sessions, questions, lobby, results
home/               # Landing page and dashboard
questions/          # Question bank: subjects, topics, choices, explanations
recommendations/    # Recommendation engine (pure Python, no models)
users/              # Custom user model, profiles, subject selection
templates/          # Global base template
```

Each app owns its own `templates/<app>/` directory

---

## Getting Started

```bash
git clone <repo>
cd JAMBReady
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The app runs at `http://127.0.0.1:8000`. The admin panel is at `/admin/`.

Questions must be imported via the admin or a custom management command. Without questions in the database, exam types will render the `no_questions.html` fallback.

---

## Data Models

### questions app

The question bank is built around four related models.

`Subject` is just a name (e.g. "Mathematics", "English Language"). `Topic` belongs to a subject and has a name — questions can be filtered by topic inside the Practice by Topic exam type. `Question` links to both a subject and a topic, carries the question text and the year the question appeared in JAMB. Each question has multiple `Choice` rows (the answer options), exactly one of which has `is_correct=True`. An optional `Explanation` row can be attached to a question — it's shown on the answer reveal screen for practice modes.

### users app

The project uses a custom `User` model extending `AbstractUser`, with email enforced as unique. Each user has a `Profile` (created on registration) which stores a bio, an optional avatar, and a many-to-many relation to `Subject`. A user must select exactly 4 subjects before they can sit any exam — the `subjects_complete` property on `Profile` checks this.

### exam app

`ExamSession` records a single sitting. It stores the exam type (Quick Test, Timed Exam, Practice by Topic, Weakness Drill), the subject and topic if scoped, timing data, and the final score once completed. The `ExamQuestion` through-model links a session to its questions in order, tracking whether each question was answered, which choice was selected, and whether it was correct.

Results are not calculated until the session completes — `calculate_results()` runs a single aggregation pass over the `ExamQuestion` rows and saves the totals.

---

## Exam Types

| Type | Questions | Time limit | Shows answer immediately |
|------|-----------|------------|--------------------------|
| Quick Test | 15 (random) | None | No |
| Timed Exam | 40 (random) | 60 minutes | No |
| Practice by Topic | All in subject/topic | None | Yes |
| Weakness Drill | Up to 20 previously wrong | None | Yes |

For Quick Test and Timed Exam, users see their full results only after completing or abandoning. For Practice by Topic and Weakness Drill, each answer is revealed immediately with the correct choice highlighted and an explanation if one exists.

The countdown for Timed Exam is entirely client-side. The start timestamp is embedded in the page as JSON and the timer counts down in the browser — when it hits zero, the abandon form submits automatically.

---

## User Flow

1. Register → Profile is created, user redirected to subject selection.
2. Select exactly 4 subjects → saved to `Profile.subjects`.
3. Visit `/exam/` → lobby shows only the user's 4 subjects.
4. Submit the lobby form → `start_exam` view shuffles and slices the question pool, creates a session, bulk-creates `ExamQuestion` rows, and redirects to the first question.
5. Answer each question → `submit_answer` records the response. For reveal-mode exams, it renders `answer_reveal.html` inline; otherwise it redirects to the next question.
6. After the last question (or on manual abandon), the session is marked complete and results are calculated.

The exam lobby form uses a small JS snippet to populate the topic dropdown dynamically from a JSON block rendered into the page, keeping the subject/topic relationship in sync without any AJAX calls.

---

## Recommendation Engine

`recommendations/engine.py` is a standalone module — no models, no migrations. It's called by the home view and returns up to 3 `Recommendation` objects to display on the dashboard.

The engine runs a series of checks in priority order:

- If the user has fewer than 4 subjects selected, it returns early with a single onboarding prompt.
- If the user has no completed sessions, it suggests a first Quick Test.
- Otherwise it builds per-subject accuracy stats, then checks for weak subjects (below 50% accuracy on 10+ questions), untouched subjects, a backlog of wrong answers suitable for a Weakness Drill, inactivity over 3 days, a low overall pass rate, and whether the user has ever tried a Timed Exam.

Each recommendation carries a `kind` (danger / warning / success / info), an `icon` slug, a priority score, and a CTA URL that can pre-fill the lobby form via query parameters.

---

## URL Structure

```
/                       home
/admin/                 Django admin
/users/register/        registration
/users/login/           login
/users/logout/          logout (POST to confirm, GET shows confirmation page)
/users/profile/         profile edit (bio + avatar)
/users/select-subjects/ subject selection

/exam/                  exam lobby
/exam/start/            POST — creates session, redirects to first question
/exam/<id>/             current question
/exam/<id>/submit/      POST — record answer
/exam/<id>/abandon/     POST — mark abandoned
/exam/<id>/complete/    results and breakdown
/exam/history/          all completed sessions
```

---

## Settings Notes

- `AUTH_USER_MODEL = 'users.User'` — the custom user model is referenced throughout; don't swap this after initial migrations.
- `SECRET_KEY` is hardcoded in the repo. Replace it before any deployment.
- `DEBUG = True` and `ALLOWED_HOSTS = []` — both need changing for production.
- Media files (avatars) are served via Django in debug mode via the `static()` helper appended to `urlpatterns`. There's a duplicate block in `ExamReady/urls.py` — one of them can be removed.
- No `DEFAULT_AUTO_FIELD` is set, so Django will use its framework default. Adding `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` suppresses the system check warning.

---

## CI

GitHub Actions runs `python manage.py test` on every push and PR to `main`, across Python 3.12 and 3.13. The workflow is in `.github/workflows/django.yml`. Tests currently use the default empty test cases — filling them out is the obvious next step for contributors.

---

## Admin

Questions, choices, and explanations are managed through the Django admin. `QuestionAdmin` includes inline editing for choices and explanations, so a complete question can be created in one form. `ExamSessionAdmin` shows session results and provides a read-only inline view of every question in that session.

---

## Contributing

See `.github/pull_request_template.md` for the PR checklist and `.github/ISSUE_TEMPLATE/` for bug report and feature request forms.
