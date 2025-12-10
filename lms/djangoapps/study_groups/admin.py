"""
Django admin configuration for Study Groups.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    StudyGroup,
    StudyGroupMember,
    StudyGroupComment,
    CommentAttachment,
    CommentReaction,
)


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    """Admin interface for StudyGroup model."""
    
    list_display = ('id', 'name', 'course_id', 'created_by', 'created_at', 'member_count_display')
    list_filter = ('created_at', 'course_id')
    search_fields = ('name', 'description', 'course_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'course_id', 'name', 'description')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def member_count_display(self, obj):
        """Display member count."""
        count = obj.get_member_count()
        return format_html('<strong>{}</strong>', count)
    member_count_display.short_description = 'Members'


@admin.register(StudyGroupMember)
class StudyGroupMemberAdmin(admin.ModelAdmin):
    """Admin interface for StudyGroupMember model."""
    
    list_display = ('id', 'user', 'group', 'role', 'joined_at')
    list_filter = ('role', 'joined_at', 'group__course_id')
    search_fields = ('user__username', 'user__email', 'group__name')
    readonly_fields = ('id', 'joined_at')
    date_hierarchy = 'joined_at'
    
    fieldsets = (
        ('Membership', {
            'fields': ('id', 'group', 'user', 'role', 'joined_at')
        }),
    )


@admin.register(StudyGroupComment)
class StudyGroupCommentAdmin(admin.ModelAdmin):
    """Admin interface for StudyGroupComment model."""
    
    list_display = ('id', 'group', 'user', 'content_preview', 'created_at', 'replies_count_display')
    list_filter = ('created_at', 'group__course_id')
    search_fields = ('content', 'user__username', 'group__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Comment', {
            'fields': ('id', 'group', 'user', 'parent_comment', 'content')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def content_preview(self, obj):
        """Display a preview of the comment content."""
        preview = obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
        return format_html('<span title="{}">{}</span>', obj.content, preview)
    content_preview.short_description = 'Content'
    
    def replies_count_display(self, obj):
        """Display replies count."""
        count = obj.replies.count()
        return format_html('<strong>{}</strong>', count)
    replies_count_display.short_description = 'Replies'


@admin.register(CommentAttachment)
class CommentAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for CommentAttachment model."""
    
    list_display = ('id', 'comment', 'file_name', 'file_type', 'file_size_display', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('file_name', 'comment__content')
    readonly_fields = ('id', 'uploaded_at', 'file_url_display')
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Attachment', {
            'fields': ('id', 'comment', 'file_name', 'file_path', 'file_type', 'file_size')
        }),
        ('Metadata', {
            'fields': ('uploaded_at', 'file_url_display')
        }),
    )
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    file_size_display.short_description = 'Size'
    
    def file_url_display(self, obj):
        """Display file URL."""
        url = obj.get_file_url()
        if url:
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return '-'
    file_url_display.short_description = 'File URL'


@admin.register(CommentReaction)
class CommentReactionAdmin(admin.ModelAdmin):
    """Admin interface for CommentReaction model."""
    
    list_display = ('id', 'comment', 'user', 'reaction_type', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__username', 'comment__content')
    readonly_fields = ('id', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Reaction', {
            'fields': ('id', 'comment', 'user', 'reaction_type', 'created_at')
        }),
    )

