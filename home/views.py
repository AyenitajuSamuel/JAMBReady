from django.shortcuts import render
from questions.models import Subject
from exam.models import ExamSession, ExamQuestion
from recommendations.engine import get_recommendations


def home(request):
    context = {
        "exam_type_list": ["Quick Test", "Timed Exam", "Practice by Topic", "Weakness Drill"],
    }

    if request.user.is_authenticated:
        all_sessions = ExamSession.objects.filter(
            user=request.user, status=ExamSession.Status.COMPLETED
        )
        recent_sessions = all_sessions.select_related("subject").order_by("-started_at")[:5]
        total_exams     = all_sessions.count()
        total_passed    = all_sessions.filter(passed=True).count()

        answered  = ExamQuestion.objects.filter(session__user=request.user, answered=True)
        total_q   = answered.count()
        correct_q = answered.filter(is_correct=True).count()
        readiness_pct = round(correct_q / total_q * 100) if total_q else None

        recs      = get_recommendations(request.user)
        top_recs  = recs[:3]
        rec_count = len(recs)   # drives the bell badge

        context.update({
            "recent_sessions": recent_sessions,
            "total_exams":     total_exams,
            "total_passed":    total_passed,
            "subjects":        Subject.objects.all(),
            "top_recs":        top_recs,
            "readiness_pct":   readiness_pct,
            "rec_count":       rec_count,
        })

    return render(request, "home/home.html", context)