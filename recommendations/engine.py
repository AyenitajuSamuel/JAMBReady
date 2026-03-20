"""
Recommendation engine for ExamReady.

Analyses a user's exam history and profile to produce a ranked list of
actionable recommendations. No database models required — everything is
derived on the fly from ExamSession / ExamQuestion data.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from exam.models import ExamQuestion, ExamSession
from questions.models import Subject, Topic


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """A single, actionable suggestion for the user."""

    # Display
    title: str
    body: str
    cta_label: str          # Button / link text
    cta_url: str            # Where the CTA points

    # Metadata for sorting / rendering
    priority: int = 0       # Higher = more important; shown first
    kind: str = "info"      # "danger" | "warning" | "success" | "info"
    icon: str = "chart"     # Matches template icon set

    # Optional subject / topic context (used to pre-fill exam lobby)
    subject_id: Optional[int] = None
    topic_id: Optional[int] = None


@dataclass
class SubjectStats:
    subject: Subject
    total: int = 0
    correct: int = 0
    sessions: int = 0

    @property
    def accuracy(self) -> float:
        return round(self.correct / self.total * 100, 1) if self.total else 0.0

    @property
    def has_data(self) -> bool:
        return self.total > 0


# ── Engine ─────────────────────────────────────────────────────────────────────

def get_recommendations(user) -> list[Recommendation]:
    """
    Return a list of Recommendation objects for *user*, ordered by priority.
    Handles brand-new users gracefully (returns onboarding nudges).
    """
    recs: list[Recommendation] = []

    # ── 0. Profile completeness ──────────────────────────────────────────────
    try:
        profile = user.profile
    except Exception:
        profile = None

    selected_subjects = list(profile.subjects.all()) if profile else []

    if len(selected_subjects) < 4:
        recs.append(Recommendation(
            title="Complete your subject selection",
            body="You need to choose exactly 4 JAMB subjects before you can start practising.",
            cta_label="Select subjects",
            cta_url="/users/select-subjects/",
            priority=100,
            kind="danger",
            icon="alert",
        ))
        # Nothing more useful to say until subjects are set
        return sorted(recs, key=lambda r: -r.priority)

    # ── 1. Load history ──────────────────────────────────────────────────────
    completed_sessions = (
        ExamSession.objects
        .filter(user=user, status=ExamSession.Status.COMPLETED)
        .select_related("subject", "topic")
        .order_by("-started_at")
    )
    session_list = list(completed_sessions)
    total_sessions = len(session_list)

    # Brand-new user — no history yet
    if total_sessions == 0:
        recs.append(Recommendation(
            title="Take your first exam",
            body="Start with a Quick Test to get a feel for JAMB-style questions across your chosen subjects.",
            cta_label="Start Quick Test",
            cta_url="/exam/",
            priority=90,
            kind="info",
            icon="play",
        ))
        return sorted(recs, key=lambda r: -r.priority)

    # ── 2. Build per-subject stats ───────────────────────────────────────────
    subject_stats: dict[int, SubjectStats] = {
        s.id: SubjectStats(subject=s) for s in selected_subjects
    }

    exam_questions = (
        ExamQuestion.objects
        .filter(session__user=user, answered=True,
                question__subject__in=selected_subjects)
        .select_related("question__subject", "question__topic")
    )

    for eq in exam_questions:
        sid = eq.question.subject_id
        if sid in subject_stats:
            subject_stats[sid].total += 1
            if eq.is_correct:
                subject_stats[sid].correct += 1

    for session in session_list:
        if session.subject_id and session.subject_id in subject_stats:
            subject_stats[session.subject_id].sessions += 1

    stats_list = list(subject_stats.values())

    # ── 3. Weak subjects (accuracy < 50 %, at least 10 questions) ───────────
    weak_subjects = [
        s for s in stats_list
        if s.has_data and s.total >= 10 and s.accuracy < 50
    ]
    weak_subjects.sort(key=lambda s: s.accuracy)

    for ws in weak_subjects[:2]:           # Surface at most 2
        recs.append(Recommendation(
            title=f"Improve your {ws.subject.name} score",
            body=(
                f"You're answering only {ws.accuracy:.0f}% of {ws.subject.name} questions "
                f"correctly ({ws.correct}/{ws.total}). Focused practice will help."
            ),
            cta_label=f"Practise {ws.subject.name}",
            cta_url=f"/exam/?prefill_subject={ws.subject.id}&exam_type=practice_topic",
            priority=80,
            kind="danger",
            icon="target",
            subject_id=ws.subject.id,
        ))

    # ── 4. Neglected subjects (no questions attempted) ───────────────────────
    untouched = [s for s in stats_list if not s.has_data]
    for us in untouched[:2]:
        recs.append(Recommendation(
            title=f"Start practising {us.subject.name}",
            body=f"You haven't attempted any {us.subject.name} questions yet. JAMB tests all 4 subjects equally.",
            cta_label=f"Begin {us.subject.name}",
            cta_url=f"/exam/?prefill_subject={us.subject.id}&exam_type=quick_test",
            priority=70,
            kind="warning",
            icon="book",
            subject_id=us.subject.id,
        ))

    # ── 5. Weakness Drill — if the user has wrong answers stored ─────────────
    wrong_count = (
        ExamQuestion.objects
        .filter(session__user=user, is_correct=False,
                question__subject__in=selected_subjects)
        .values("question_id")
        .distinct()
        .count()
    )
    if wrong_count >= 5:
        recs.append(Recommendation(
            title=f"Drill your {wrong_count} weak questions",
            body=(
                "You have questions you've previously got wrong. A Weakness Drill targets "
                "exactly those — the fastest way to convert weak spots into marks."
            ),
            cta_label="Start Weakness Drill",
            cta_url="/exam/?prefill_exam_type=weakness_drill",
            priority=75,
            kind="warning",
            icon="repeat",
        ))

    # ── 6. Never tried a Timed Exam ─────────────────────────────────────────
    has_timed = any(
        s.exam_type == ExamSession.ExamType.TIMED_EXAM for s in session_list
    )
    if not has_timed and total_sessions >= 3:
        recs.append(Recommendation(
            title="Simulate real exam conditions",
            body="You've done practice sessions but never a Timed Exam. Training under time pressure is essential for JAMB readiness.",
            cta_label="Try a Timed Exam",
            cta_url="/exam/?prefill_exam_type=timed_exam",
            priority=60,
            kind="info",
            icon="clock",
        ))

    # ── 7. Inactivity (no session in the last 3 days) ───────────────────────
    if session_list:
        last_active = session_list[0].started_at
        days_idle = (timezone.now() - last_active).days
        if days_idle >= 3:
            recs.append(Recommendation(
                title=f"You've been away for {days_idle} day{'s' if days_idle != 1 else ''}",
                body="Consistent daily practice builds long-term retention. Even a short Quick Test today will help.",
                cta_label="Quick Test now",
                cta_url="/exam/?prefill_exam_type=quick_test",
                priority=50,
                kind="info",
                icon="calendar",
            ))

    # ── 8. Low overall pass rate ─────────────────────────────────────────────
    if total_sessions >= 5:
        passed = sum(1 for s in session_list if s.passed)
        pass_rate = passed / total_sessions * 100
        if pass_rate < 40:
            recs.append(Recommendation(
                title="Your pass rate needs attention",
                body=(
                    f"You've passed {passed} of {total_sessions} exams ({pass_rate:.0f}%). "
                    "Try practicing by topic to strengthen specific areas before taking full exams."
                ),
                cta_label="Practice by Topic",
                cta_url="/exam/?prefill_exam_type=practice_topic",
                priority=65,
                kind="danger",
                icon="chart",
            ))

    # ── 9. Positive reinforcement — on a good streak ─────────────────────────
    if total_sessions >= 3:
        recent_three = session_list[:3]
        if all(s.passed for s in recent_three):
            best_subject = max(
                (s for s in stats_list if s.has_data),
                key=lambda s: s.accuracy,
                default=None,
            )
            if best_subject:
                recs.append(Recommendation(
                    title="Keep the momentum going",
                    body=(
                        f"You've passed your last 3 exams — great work! "
                        f"Your strongest subject is {best_subject.subject.name} "
                        f"({best_subject.accuracy:.0f}%). Challenge yourself with a Timed Exam."
                    ),
                    cta_label="Take a Timed Exam",
                    cta_url="/exam/?prefill_exam_type=timed_exam",
                    priority=40,
                    kind="success",
                    icon="star",
                ))

    # ── 10. Fallback — always have something to show ─────────────────────────
    if not recs:
        recs.append(Recommendation(
            title="Keep practising",
            body="Regular practice is the key to JAMB success. Take a Quick Test to stay sharp.",
            cta_label="Quick Test",
            cta_url="/exam/?prefill_exam_type=quick_test",
            priority=10,
            kind="info",
            icon="play",
        ))

    return sorted(recs, key=lambda r: -r.priority)