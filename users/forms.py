from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from questions.models import Subject
from .models import Profile

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model  = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    class Meta:
        model  = User
        fields = ("username", "password")


class SubjectSelectionForm(forms.Form):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Select exactly 4 subjects"
    )

    def clean_subjects(self):
        subjects = self.cleaned_data.get("subjects")
        if subjects and subjects.count() != 4:
            raise forms.ValidationError("You must select exactly 4 subjects.")
        return subjects


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = Profile
        fields = ("bio", "avatar")