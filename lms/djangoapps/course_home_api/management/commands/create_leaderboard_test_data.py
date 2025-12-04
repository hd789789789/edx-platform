"""
Management command to create test data for leaderboard testing.
Creates 100 test users with random grades and progress.

Usage:
    python manage.py lms create_leaderboard_test_data course-v1:PiStudy+TOAN7+2025_T9
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.student.models import CourseEnrollment, UserProfile
from lms.djangoapps.grades.models import PersistentCourseGrade


User = get_user_model()


class Command(BaseCommand):
    help = 'Create 100 test users with random grades and progress for leaderboard testing'

    def add_arguments(self, parser):
        parser.add_argument(
            'course_id',
            type=str,
            help='Course ID to enroll users in (e.g., course-v1:PiStudy+TOAN7+2025_T9)'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Number of test users to create (default: 100)'
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='testuser',
            help='Username prefix for test users (default: testuser)'
        )
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing test users before creating new ones'
        )

    def handle(self, *args, **options):
        course_id = options['course_id']
        count = options['count']
        prefix = options['prefix']
        delete_existing = options['delete_existing']

        try:
            course_key = CourseKey.from_string(course_id)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Invalid course ID: {course_id}'))
            return

        self.stdout.write(f'Creating {count} test users for course: {course_id}')

        # Delete existing test users if requested
        if delete_existing:
            existing_users = User.objects.filter(username__startswith=prefix)
            deleted_count = existing_users.count()
            existing_users.delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted_count} existing test users'))

        # Vietnamese names for realistic data
        first_names = [
            'An', 'Bình', 'Cường', 'Dũng', 'Đức', 'Giang', 'Hà', 'Hải', 'Hiếu', 'Hoàng',
            'Hùng', 'Hương', 'Khang', 'Khánh', 'Kiên', 'Lan', 'Linh', 'Long', 'Mai', 'Minh',
            'Nam', 'Nga', 'Ngọc', 'Nhân', 'Như', 'Phong', 'Phúc', 'Quang', 'Quốc', 'Sơn',
            'Tâm', 'Thảo', 'Thành', 'Thiên', 'Thịnh', 'Thu', 'Thủy', 'Tiến', 'Trang', 'Trí',
            'Trung', 'Tú', 'Tuấn', 'Uyên', 'Văn', 'Việt', 'Vũ', 'Xuân', 'Yến', 'Ý'
        ]
        last_names = [
            'Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ', 'Đặng',
            'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương', 'Lý', 'Đinh', 'Lương', 'Trương', 'Cao'
        ]

        created_count = 0
        enrolled_count = 0
        grades_count = 0

        for i in range(1, count + 1):
            username = f'{prefix}_{i:03d}'
            email = f'{username}@test.edu'
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'User {username} already exists, skipping...')
                continue

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='Test@12345',
                is_active=True
            )
            created_count += 1

            # Create profile with Vietnamese name
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            full_name = f'{last_name} {first_name}'
            
            try:
                profile = UserProfile.objects.get(user=user)
                profile.name = full_name
                profile.save()
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(user=user, name=full_name)

            # Enroll user in course with random enrollment date
            days_ago = random.randint(1, 90)  # Enrolled 1-90 days ago
            enrollment_date = timezone.now() - timedelta(days=days_ago)
            
            enrollment, created = CourseEnrollment.objects.get_or_create(
                user=user,
                course_id=course_key,
                defaults={
                    'is_active': True,
                    'mode': 'audit',
                }
            )
            if created:
                enrollment.created = enrollment_date
                enrollment.save()
                enrolled_count += 1

            # Create random grade (0-100%, converted to 0-1 for percent_grade)
            # Distribution: some high, some medium, some low
            grade_type = random.choices(
                ['high', 'medium', 'low', 'zero'],
                weights=[20, 40, 30, 10]
            )[0]
            
            if grade_type == 'high':
                percent_grade = random.uniform(0.7, 1.0)  # 70-100%
            elif grade_type == 'medium':
                percent_grade = random.uniform(0.4, 0.7)  # 40-70%
            elif grade_type == 'low':
                percent_grade = random.uniform(0.1, 0.4)  # 10-40%
            else:
                percent_grade = 0.0  # 0%

            # Determine if passed
            passed = percent_grade >= 0.6
            passed_timestamp = None
            if passed:
                # Random passed date (after enrollment)
                days_after_enrollment = random.randint(1, min(days_ago, 30))
                passed_timestamp = enrollment_date + timedelta(days=days_after_enrollment)

            # Create grade record with random modified time
            hours_ago = random.randint(1, 24 * days_ago)
            modified_time = timezone.now() - timedelta(hours=hours_ago)

            try:
                grade, created = PersistentCourseGrade.objects.update_or_create(
                    user_id=user.id,
                    course_id=course_key,
                    defaults={
                        'percent_grade': percent_grade,
                        'letter_grade': self.get_letter_grade(percent_grade),
                        'passed_timestamp': passed_timestamp,
                        'course_edited_timestamp': timezone.now(),
                        'course_version': '',
                        'grading_policy_hash': 'test_policy_hash',
                    }
                )
                # Update modified time
                PersistentCourseGrade.objects.filter(id=grade.id).update(modified=modified_time)
                grades_count += 1
            except Exception as e:
                self.stderr.write(f'Error creating grade for {username}: {e}')

            if i % 10 == 0:
                self.stdout.write(f'Progress: {i}/{count} users created')

        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted!\n'
            f'- Users created: {created_count}\n'
            f'- Enrollments created: {enrolled_count}\n'
            f'- Grades created: {grades_count}'
        ))

    def get_letter_grade(self, percent_grade):
        if percent_grade >= 0.9:
            return 'A'
        elif percent_grade >= 0.8:
            return 'B'
        elif percent_grade >= 0.7:
            return 'C'
        elif percent_grade >= 0.6:
            return 'D'
        else:
            return 'F'

