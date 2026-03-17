from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, ProfileForm, RegisterForm, SubjectSelectionForm
from .models import Profile

User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        Profile.objects.create(user=user)
        auth_login(request, user)
        messages.success(request, "Account created! Now select your 4 JAMB subjects.")
        return redirect("select_subjects")

    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        messages.success(request, f"Welcome back, {form.get_user().username}!")
        return redirect(request.GET.get("next", "home"))

    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        auth_logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("login")
    return render(request, "users/logout_confirm.html")


@login_required
def select_subjects_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = SubjectSelectionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        profile.subjects.set(form.cleaned_data["subjects"])
        messages.success(request, "Subjects saved successfully!")
        return redirect("home")

    return render(request, "users/select_subjects.html", {
        "form":    form,
        "profile": profile,
    })


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully!")
        return redirect("profile")

    return render(request, "users/profile.html", {
        "form":    form,
        "profile": profile,
    })