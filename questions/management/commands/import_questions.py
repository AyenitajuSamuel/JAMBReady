import csv
from django.core.management.base import BaseCommand
from questions.models import Subject, Topic, Question, Choice, Explanation


class Command(BaseCommand):
    help = 'Import questions from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        with open(options['csv_file'], encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                subject, _ = Subject.objects.get_or_create(name=row['subject'].strip())
                topic, _   = Topic.objects.get_or_create(
                    subject=subject,
                    name=row.get('topic', 'General').strip() or 'General'
                )

                question, created = Question.objects.get_or_create(
                    subject=subject,
                    topic=topic,
                    question_text=row['question'].strip(),
                    defaults={'year': 2024},
                )

                if created:
                    correct = row.get('correct_answer', '').strip().lower()

                    choices = {
                        'a': row.get('choice_a', '').strip(),
                        'b': row.get('choice_b', '').strip(),
                        'c': row.get('choice_c', '').strip(),
                        'd': row.get('choice_d', '').strip(),
                    }

                    for letter, text in choices.items():
                        if text:
                            Choice.objects.create(
                                question=question,
                                option_text=text,
                                is_correct=(letter == correct),
                            )

                    explanation = row.get('explanation', '').strip()
                    if explanation:
                        Explanation.objects.create(
                            question=question,
                            explanation_text=explanation,
                        )

                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — {created_count} questions imported, {skipped_count} skipped (already exist).'
        ))