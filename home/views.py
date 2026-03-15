from django.shortcuts import render
from questions.models import Subject


def home(request):
    context = {}

    if request.user.is_authenticated:
        try:
            from exam.models import ExamSession

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
            })
        except Exception:
            context.update({
                "recent_sessions": [],
                "total_exams":     0,
                "total_passed":    0,
            })

        context["subjects"] = Subject.objects.all()

    return render(request, "home/home.html", context)