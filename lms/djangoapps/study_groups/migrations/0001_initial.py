"""
Initial migration for Study Groups app.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import opaque_keys.edx.django.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyGroup',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(db_index=True, max_length=255)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_study_groups',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'study_groups_studygroup',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StudyGroupMember',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('role', models.CharField(
                    choices=[
                        ('admin', 'Admin'),
                        ('staff', 'Staff'),
                        ('member', 'Member')
                    ],
                    default='member',
                    max_length=10
                )),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='study_groups.studygroup'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='study_group_memberships',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'study_groups_studygroupmember',
                'unique_together': {('group', 'user')},
            },
        ),
        migrations.CreateModel(
            name='StudyGroupComment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to='study_groups.studygroup'
                )),
                ('parent_comment', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='replies',
                    to='study_groups.studygroupcomment'
                )),
                ('user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='study_group_comments',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'study_groups_studygroupcomment',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CommentAttachment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('file_name', models.CharField(max_length=255)),
                ('file_path', models.FileField(upload_to='study_groups/attachments/')),
                ('file_type', models.CharField(
                    choices=[
                        ('image', 'Image'),
                        ('document', 'Document'),
                        ('video', 'Video')
                    ],
                    max_length=20
                )),
                ('file_size', models.BigIntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('comment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='study_groups.studygroupcomment'
                )),
            ],
            options={
                'db_table': 'study_groups_commentattachment',
            },
        ),
        migrations.CreateModel(
            name='CommentReaction',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('reaction_type', models.CharField(
                    choices=[
                        ('like', 'Like'),
                        ('love', 'Love'),
                        ('haha', 'Haha'),
                        ('wow', 'Wow'),
                        ('sad', 'Sad'),
                        ('angry', 'Angry')
                    ],
                    max_length=10
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('comment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='study_groups.studygroupcomment'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='study_group_reactions',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'study_groups_commentreaction',
                'unique_together': {('comment', 'user')},
            },
        ),
        migrations.AddIndex(
            model_name='studygroup',
            index=models.Index(fields=['course_id'], name='study_group_course_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroup',
            index=models.Index(fields=['created_at'], name='study_group_created_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupmember',
            index=models.Index(fields=['group', 'user'], name='study_group_member_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupmember',
            index=models.Index(fields=['user'], name='study_group_member_user_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupcomment',
            index=models.Index(fields=['group', '-created_at'], name='study_group_comment_group_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupcomment',
            index=models.Index(fields=['user'], name='study_group_comment_user_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupcomment',
            index=models.Index(fields=['parent_comment'], name='study_group_comment_parent_idx'),
        ),
        migrations.AddIndex(
            model_name='commentattachment',
            index=models.Index(fields=['comment'], name='comment_attachment_comment_idx'),
        ),
        migrations.AddIndex(
            model_name='commentreaction',
            index=models.Index(fields=['comment', 'reaction_type'], name='comment_reaction_idx'),
        ),
    ]

