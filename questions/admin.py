from django.contrib import admin
from .models import Question, Subject, Choice 

admin.site.register(Question)
admin.site.register(Subject)
admin.site.register(Choice)
