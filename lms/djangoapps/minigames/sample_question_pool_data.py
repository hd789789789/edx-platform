#!/usr/bin/env python
"""
Sample data script to populate QuestionPool table with test data.

This script creates sample question pool entries for testing purposes.

Usage:
    python sample_question_pool_data.py
"""

import os
import sys
import django
import json

# Setup Django environment
if __name__ == "__main__":
    # Add the edx-platform directory to the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms.envs.production')

    django.setup()

    from .models import QuestionPool

    # Sample data
    sample_data = [
        {
            'mate_id': 'math_quiz_001',
            'cat_list': ['math', 'algebra', 'basic'],
            'mate_meta': {
                'title': 'Basic Algebra Quiz',
                'difficulty': 'easy',
                'tags': ['math', 'algebra', 'quiz'],
                'created_by': 'admin'
            },
            'mate_content': {
                'questions': [
                    {
                        'id': 'q1',
                        'type': 'multiple_choice',
                        'question': 'What is 2 + 2?',
                        'options': ['3', '4', '5', '6'],
                        'correct_answer': '4'
                    }
                ],
                'total_questions': 1
            },
            'status': 1
        },
        {
            'mate_id': 'physics_lesson_001',
            'cat_list': ['physics', 'mechanics', 'intermediate'],
            'mate_meta': {
                'title': 'Newton\'s Laws',
                'difficulty': 'intermediate',
                'tags': ['physics', 'mechanics', 'laws'],
                'created_by': 'teacher1'
            },
            'mate_content': {
                'lessons': [
                    {
                        'id': 'l1',
                        'title': 'First Law of Motion',
                        'content': 'An object at rest stays at rest...',
                        'examples': ['Car on road', 'Book on table']
                    }
                ],
                'total_lessons': 1
            },
            'status': 1
        },
        {
            'mate_id': 'chemistry_exam_001',
            'cat_list': ['chemistry', 'organic', 'advanced'],
            'mate_meta': {
                'title': 'Organic Chemistry Final Exam',
                'difficulty': 'advanced',
                'tags': ['chemistry', 'organic', 'exam'],
                'created_by': 'professor_x'
            },
            'mate_content': {
                'exam_config': {
                    'duration': 120,  # minutes
                    'total_marks': 100,
                    'passing_marks': 40
                },
                'questions': [
                    {
                        'id': 'exam_q1',
                        'type': 'essay',
                        'question': 'Explain the mechanism of SN1 reaction.',
                        'marks': 20
                    }
                ]
            },
            'status': 2  # Review status
        }
    ]

    print("Creating sample QuestionPool data...")

    for data in sample_data:
        try:
            obj, created = QuestionPool.objects.get_or_create(
                mate_id=data['mate_id'],
                defaults=data
            )
            if created:
                print(f"✓ Created: {data['mate_id']}")
            else:
                print(f"⚠ Already exists: {data['mate_id']}")
        except Exception as e:
            print(f"✗ Error creating {data['mate_id']}: {e}")

    print("\n✓ Sample data creation completed!")
    print(f"Total QuestionPool entries: {QuestionPool.objects.count()}")
