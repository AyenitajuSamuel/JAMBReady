from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import random

from questions.models import Choice, Question, Subject, Topic
from .models import ExamQuestion, ExamSession


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_session(user, exam_type, questions_qs, subject=None, topic=None,
                   duration_seconds=None, pass_mark=50):
    questions = list(questions_qs)
    random.shuffle(questions)
    session = ExamSession.objects.create(
        user=user,
        exam_type=exam_type,
        subject=subject,
        topic=topic,
        duration_seconds=duration_seconds,
        pass_mark=pass_mark,
        total_questions=len(questions),
    )
    ExamQuestion.objects.bulk_create([
        ExamQuestion(session=session, question=q, order=i)
        for i, q in enumerate(questions, start=1)
    ])
    return session


def _reveal_immediately(exam_type):
    return exam_type in (ExamSession.ExamType.PRACTICE_TOPIC,
                         ExamSession.ExamType.WEAKNESS_DRILL)


def _get_profile_subjects(user):
    try:
        profile = user.profile
    except Exception:
        return None
    subjects = profile.subjects.all()
    return subjects if subjects.count() == 4 else None


# ─── Lobby ────────────────────────────────────────────────────────────────────

@login_required
def lobby(request):
    profile_subjects = _get_profile_subjects(request.user)
    subjects = profile_subjects if profile_subjects is not None else Subject.objects.none()
    subjects_json = [
        {
            "id": s.id,
            "name": s.name,
            "topics": [{"id": t.id, "name": t.name} for t in s.topics.all()]
        }
        for s in subjects.prefetch_related("topics")
    ]
    return render(request, "exam/lobby.html", {
        "subjects": subjects,
        "subjects_json": subjects_json,
        "subjects_incomplete": profile_subjects is None,
    })


# ─── Start Exam ───────────────────────────────────────────────────────────────

@login_required
@require_POST
def start_exam(request):
    profile_subjects = _get_profile_subjects(request.user)
    if profile_subjects is None:
        return redirect("select_subjects")

    exam_type  = request.POST.get("exam_type") or ExamSession.ExamType.QUICK_TEST
    subject_id = request.POST.get("subject_id")
    topic_id   = request.POST.get("topic_id")

    subject = profile_subjects.filter(pk=subject_id).first() if subject_id else None
    topic   = Topic.objects.filter(pk=topic_id).first() if topic_id else None

    base_qs = (
        Question.objects
        .filter(subject__in=profile_subjects)
        .prefetch_related("choices")
    )
    if subject:
        base_qs = base_qs.filter(subject=subject)
    if topic:
        base_qs = base_qs.filter(topic=topic)

    if exam_type == ExamSession.ExamType.QUICK_TEST:
        questions = list(base_qs.order_by("?")[:15])
        if not questions:
            return render(request, "exam/no_questions.html", {"exam_type": "Quick Test"})
        session = _build_session(request.user, exam_type, questions, subject=subject)

    elif exam_type == ExamSession.ExamType.TIMED_EXAM:
        questions = list(base_qs.order_by("?")[:40])
        if not questions:
            return render(request, "exam/no_questions.html", {"exam_type": "Timed Exam"})
        session = _build_session(
            request.user, exam_type, questions,
            subject=subject, duration_seconds=3600, pass_mark=50
        )

    elif exam_type == ExamSession.ExamType.PRACTICE_TOPIC:
        if not subject:
            return redirect("exam_lobby")
        questions = list(base_qs)
        if not questions:
            return render(request, "exam/no_questions.html", {"exam_type": "Practice by Topic"})
        session = _build_session(request.user, exam_type, questions,
                                 subject=subject, topic=topic)

    elif exam_type == ExamSession.ExamType.WEAKNESS_DRILL:
        wrong_ids = (
            ExamQuestion.objects
            .filter(
                session__user=request.user,
                is_correct=False,
                question__subject__in=profile_subjects,
            )
            .values_list("question_id", flat=True)
            .distinct()
        )
        questions = list(base_qs.filter(pk__in=wrong_ids).order_by("?")[:20])
        if not questions:
            return render(request, "exam/no_weaknesses.html")
        session = _build_session(request.user, exam_type, questions)

    else:
        return redirect("exam_lobby")

    return redirect("exam_question", session_id=session.id, order=1)


# ─── Question View ────────────────────────────────────────────────────────────

@login_required
def exam_question(request, session_id, order=None):
    session = get_object_or_404(
        ExamSession, pk=session_id, user=request.user,
        status=ExamSession.Status.IN_PROGRESS
    )

    all_questions = session.examquestion_set.select_related(
        "question", "selected_choice"
    ).order_by("order")

    total = all_questions.count()

    # If no order given, go to first unanswered; if all answered go to complete
    if order is None:
        exam_q = all_questions.filter(answered=False).first()
        if not exam_q:
            return redirect("exam_complete", session_id=session.id)
        order = exam_q.order
    else:
        exam_q = get_object_or_404(ExamQuestion, session=session, order=order)

    answered_count = all_questions.filter(answered=True).count()
    progress = round((answered_count / total) * 100) if total else 0

    # Build list of question statuses for navigation dots
    nav_questions = [
        {
            "order":    q.order,
            "answered": q.answered,
            "current":  q.order == order,
        }
        for q in all_questions
    ]

    return render(request, "exam/question.html", {
        "session":       session,
        "exam_q":        exam_q,
        "question":      exam_q.question,
        "choices":       exam_q.question.choices.all(),
        "answered":      answered_count,
        "total":         total,
        "progress":      progress,
        "reveal_now":    _reveal_immediately(session.exam_type),
        "nav_questions": nav_questions,
        "has_prev":      order > 1,
        "has_next":      order < total,
        "prev_order":    order - 1,
        "next_order":    order + 1,
    })


# ─── Submit Answer ────────────────────────────────────────────────────────────

@login_required
@require_POST
def submit_answer(request, session_id):
    session = get_object_or_404(
        ExamSession, pk=session_id, user=request.user,
        status=ExamSession.Status.IN_PROGRESS
    )

    exam_q_id = request.POST.get("exam_question_id")
    choice_id = request.POST.get("choice_id")
    exam_q    = get_object_or_404(ExamQuestion, pk=exam_q_id, session=session)

    # ── Bug fix: no answer selected ──────────────────────────────────────────
    if not choice_id:
        messages.warning(request, "Please select an answer before continuing.")
        return redirect("exam_question", session_id=session.id, order=exam_q.order)

    choice = get_object_or_404(Choice, pk=choice_id, question=exam_q.question)

    exam_q.selected_choice = choice
    exam_q.is_correct      = choice.is_correct
    exam_q.answered        = True
    exam_q.answered_at     = timezone.now()
    exam_q.save()

    if _reveal_immediately(session.exam_type):
        correct_choice = exam_q.question.choices.filter(is_correct=True).first()
        try:
            explanation = exam_q.question.explanation.explanation_text
        except Exception:
            explanation = None
        return render(request, "exam/answer_reveal.html", {
            "session":        session,
            "exam_q":         exam_q,
            "question":       exam_q.question,
            "selected":       choice,
            "correct_choice": correct_choice,
            "is_correct":     choice.is_correct,
            "explanation":    explanation,
        })

    # Go to next unanswered question
    next_unanswered = session.examquestion_set.filter(answered=False).first()
    if not next_unanswered:
        return redirect("exam_complete", session_id=session.id)
    return redirect("exam_question", session_id=session.id, order=next_unanswered.order)


# ─── Abandon ──────────────────────────────────────────────────────────────────

@login_required
@require_POST
def abandon_exam(request, session_id):
    session = get_object_or_404(ExamSession, pk=session_id, user=request.user)
    session.status       = ExamSession.Status.ABANDONED
    session.completed_at = timezone.now()
    session.save()
    return redirect("exam_lobby")


# ─── Complete ─────────────────────────────────────────────────────────────────

@login_required
def exam_complete(request, session_id):
    session = get_object_or_404(ExamSession, pk=session_id, user=request.user)

    if session.status == ExamSession.Status.IN_PROGRESS:
        session.status       = ExamSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save()
        session.calculate_results()
        session.refresh_from_db()

    exam_questions = session.examquestion_set.select_related(
        "question", "selected_choice"
    ).prefetch_related("question__choices")

    return render(request, "exam/complete.html", {
        "session":        session,
        "exam_questions": exam_questions,
    })


# ─── History ──────────────────────────────────────────────────────────────────

@login_required
def exam_history(request):
    sessions = (
        ExamSession.objects
        .filter(user=request.user, status=ExamSession.Status.COMPLETED)
        .select_related("subject")
        .order_by("-started_at")
    )
    return render(request, "exam/history.html", {"sessions": sessions})