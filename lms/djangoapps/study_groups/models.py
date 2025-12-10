"""
Django models for Study Groups functionality.
"""

import os
import uuid
from datetime import datetime

import pytz
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Count, Sum
from django.utils.translation import gettext_lazy as _
from opaque_keys.edx.django.models import CourseKeyField

from common.djangoapps.student.models import CourseEnrollment

User = get_user_model()


def utc_now():
    """Return current UTC datetime."""
    return datetime.utcnow().replace(tzinfo=pytz.utc)


def upload_attachment_path(instance, filename):
    """
    Generate upload path for comment attachments.
    """
    # Generate unique filename to avoid conflicts
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('study_groups', 'attachments', filename)


class StudyGroup(models.Model):
    """
    Model representing a study group within a course.
    
    .. no_pii:
    """
    
    class Meta:
        app_label = 'study_groups'
        db_table = 'study_groups_studygroup'
        indexes = [
            models.Index(fields=['course_id'], name='study_group_course_idx'),
            models.Index(fields=['created_at'], name='study_group_created_idx'),
        ]
        ordering = ['-created_at']

    id = models.BigAutoField(primary_key=True)
    course_id = CourseKeyField(max_length=255, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_study_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.course_id})"

    def get_member_count(self):
        """Get the number of members in this group."""
        return self.members.count()

    def is_member(self, user):
        """Check if user is a member of this group."""
        return self.members.filter(user=user).exists()

    def get_user_role(self, user):
        """Get the role of a user in this group, or None if not a member."""
        try:
            membership = self.members.get(user=user)
            return membership.role
        except StudyGroupMember.DoesNotExist:
            return None

    def can_user_access(self, user):
        """
        Check if user can access this group.
        Admin/Staff can access all groups, regular users only their own groups.
        """
        from .permissions import has_course_staff_privileges
        
        if has_course_staff_privileges(user, self.course_id):
            return True
        return self.is_member(user)


class StudyGroupMember(models.Model):
    """
    Model representing membership of a user in a study group.
    
    .. no_pii:
    """
    
    ROLE_CHOICES = [
        ('admin', _('Admin')),
        ('staff', _('Staff')),
        ('member', _('Member')),
    ]

    class Meta:
        app_label = 'study_groups'
        db_table = 'study_groups_studygroupmember'
        unique_together = (('group', 'user'),)
        indexes = [
            models.Index(fields=['group', 'user'], name='study_group_member_idx'),
            models.Index(fields=['user'], name='study_group_member_user_idx'),
        ]

    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='study_group_memberships'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({self.role})"

    def clean(self):
        """Validate that user is enrolled in the course."""
        if not CourseEnrollment.is_enrolled(self.user, self.group.course_id):
            raise ValidationError(
                _('User must be enrolled in the course to join a study group.')
            )

    def save(self, *args, **kwargs):
        """Override save to validate enrollment."""
        self.clean()
        super().save(*args, **kwargs)


class StudyGroupComment(models.Model):
    """
    Model representing a comment/post in a study group.
    
    .. no_pii:
    """
    
    class Meta:
        app_label = 'study_groups'
        db_table = 'study_groups_studygroupcomment'
        indexes = [
            models.Index(fields=['group', '-created_at'], name='study_group_comment_group_idx'),
            models.Index(fields=['user'], name='study_group_comment_user_idx'),
            models.Index(fields=['parent_comment'], name='study_group_comment_parent_idx'),
        ]
        ordering = ['-created_at']

    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='study_group_comments'
    )
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user.username if self.user else 'Deleted User'} in {self.group.name}"

    def get_reaction_counts(self):
        """Get counts of each reaction type for this comment."""
        return self.reactions.values('reaction_type').annotate(
            count=Count('id')
        ).values('reaction_type', 'count')

    def get_user_reaction(self, user):
        """Get the reaction type for a specific user, or None."""
        try:
            reaction = self.reactions.get(user=user)
            return reaction.reaction_type
        except CommentReaction.DoesNotExist:
            return None

    def can_user_edit(self, user):
        """Check if user can edit this comment."""
        from .permissions import has_course_staff_privileges
        
        if has_course_staff_privileges(user, self.group.course_id):
            return True
        return self.user == user

    def can_user_delete(self, user):
        """Check if user can delete this comment."""
        return self.can_user_edit(user)


class CommentAttachment(models.Model):
    """
    Model representing file attachments for comments.
    
    .. no_pii:
    """
    
    FILE_TYPE_CHOICES = [
        ('image', _('Image')),
        ('document', _('Document')),
        ('video', _('Video')),
    ]

    class Meta:
        app_label = 'study_groups'
        db_table = 'study_groups_commentattachment'
        indexes = [
            models.Index(fields=['comment'], name='comment_attachment_comment_idx'),
        ]

    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(
        StudyGroupComment,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to=upload_attachment_path)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.BigIntegerField()  # Size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.comment.id})"

    def get_file_url(self):
        """Get the URL to access this file."""
        if self.file_path:
            return self.file_path.url
        return None


class CommentReaction(models.Model):
    """
    Model representing a reaction to a comment.
    
    .. no_pii:
    """
    
    REACTION_TYPES = [
        ('like', _('Like')),
        ('love', _('Love')),
        ('haha', _('Haha')),
        ('wow', _('Wow')),
        ('sad', _('Sad')),
        ('angry', _('Angry')),
    ]

    class Meta:
        app_label = 'study_groups'
        db_table = 'study_groups_commentreaction'
        unique_together = (('comment', 'user'),)
        indexes = [
            models.Index(fields=['comment', 'reaction_type'], name='comment_reaction_idx'),
        ]

    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(
        StudyGroupComment,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='study_group_reactions'
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} {self.reaction_type} on comment {self.comment.id}"

