from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .engine import get_recommendations


@login_required
def recommendations_view(request):
    recs = get_recommendations(request.user)
    return render(request, "recommendations/recommendations.html", {
        "recommendations": recs,
    })