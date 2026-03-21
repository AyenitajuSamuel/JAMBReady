from .engine import get_recommendations


def rec_count(request):
    """Injects rec_count into every template so the bell badge works site-wide."""
    if request.user.is_authenticated:
        return {"rec_count": len(get_recommendations(request.user))}
    return {"rec_count": 0}