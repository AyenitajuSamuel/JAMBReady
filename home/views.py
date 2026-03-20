from django.shortcuts import render
from questions.models import Subject
from exam.models import ExamSession
from recommendations.engine import get_recommendations


def home(request):
    context = {}

    if request.user.is_authenticated:
        all_sessions = ExamSession.objects.filter(
            user=request.user, status=ExamSession.Status.COMPLETED
        )
        recent_sessions = all_sessions.select_related("subject").order_by("-started_at")[:5]
        total_exams     = all_sessions.count()
        total_passed    = all_sessions.filter(passed=True).count()

        context.update({
            "recent_sessions": recent_sessions,
            "total_exams":     total_exams,
            "total_passed":    total_passed,
            "subjects":        Subject.objects.all(),
            "top_recs":        get_recommendations(request.user)[:3],
        })

    return render(request, "home/home.html", context)