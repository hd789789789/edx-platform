"""
Learner Chat Models
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.django.models import CourseKeyField

User = get_user_model()


class ChatRoom(models.Model):
    """
    Chat room model - represents a chat room for a course
    """
    CHAT_TYPES = [
        ('general', _('Chung')),
        ('qa', _('Hỏi & Đáp')),
        ('technical', _('Kỹ thuật')),
    ]

    course_id = CourseKeyField(max_length=255, db_index=True)
    chat_type = models.CharField(max_length=20, choices=CHAT_TYPES, default='general')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('course_id', 'chat_type')
        verbose_name = _('Chat Room')
        verbose_name_plural = _('Chat Rooms')

    def __str__(self):
        return f"{self.course_id} - {self.get_chat_type_display()}"


class ChatMessage(models.Model):
    """
    Chat message model - stores individual chat messages
    """
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message = models.TextField()
    mentions = models.ManyToManyField(User, related_name='mentioned_in_messages', blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='deleted_chat_messages'
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Chat Message')
        verbose_name_plural = _('Chat Messages')
        indexes = [
            models.Index(fields=['room', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.message[:50]}"

