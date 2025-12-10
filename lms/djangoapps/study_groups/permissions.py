"""
Permission utilities for Study Groups.
"""

from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
from lms.djangoapps.courseware.courses import has_access
from opaque_keys.edx.keys import CourseKey


def has_course_staff_privileges(user, course_id):
    """
    Check if user has staff or instructor privileges for a course.
    
    Args:
        user: The user to check
        course_id: The course ID (string or CourseKey)
        
    Returns:
        bool: True if user is staff or instructor
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        if isinstance(course_id, str):
            course_key = CourseKey.from_string(course_id)
        else:
            course_key = course_id
            
        # Check if user is staff or instructor
        # has_access returns AccessResponse object, convert to bool
        return (
            bool(has_access(user, 'staff', course_key)) or
            bool(has_access(user, 'instructor', course_key)) or
            CourseStaffRole(course_key).has_user(user) or
            CourseInstructorRole(course_key).has_user(user)
        )
    except Exception:
        return False


def is_course_admin(user, course_id):
    """
    Check if user is an admin (instructor) for a course.
    
    Args:
        user: The user to check
        course_id: The course ID
        
    Returns:
        bool: True if user is instructor/admin
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        if isinstance(course_id, str):
            course_key = CourseKey.from_string(course_id)
        else:
            course_key = course_id
            
        return (
            bool(has_access(user, 'instructor', course_key)) or
            CourseInstructorRole(course_key).has_user(user)
        )
    except Exception:
        return False


def is_course_staff(user, course_id):
    """
    Check if user is staff (but not necessarily admin) for a course.
    
    Args:
        user: The user to check
        course_id: The course ID
        
    Returns:
        bool: True if user is staff
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        if isinstance(course_id, str):
            course_key = CourseKey.from_string(course_id)
        else:
            course_key = course_id
            
        return (
            bool(has_access(user, 'staff', course_key)) or
            CourseStaffRole(course_key).has_user(user)
        )
    except Exception:
        return False


def can_user_create_group(user, course_id):
    """
    Check if user can create a study group.
    Only Admin and Staff can create groups.
    
    Args:
        user: The user to check
        course_id: The course ID
        
    Returns:
        bool: True if user can create groups
    """
    return has_course_staff_privileges(user, course_id)


def can_user_edit_group(user, group):
    """
    Check if user can edit a study group.
    Admin and Staff can edit any group, members cannot.
    
    Args:
        user: The user to check
        group: The StudyGroup instance
        
    Returns:
        bool: True if user can edit the group
    """
    return has_course_staff_privileges(user, group.course_id)


def can_user_delete_group(user, group):
    """
    Check if user can delete a study group.
    Only Admin and Staff can delete groups.
    
    Args:
        user: The user to check
        group: The StudyGroup instance
        
    Returns:
        bool: True if user can delete the group
    """
    return has_course_staff_privileges(user, group.course_id)


def can_user_manage_members(user, group):
    """
    Check if user can add/remove members from a study group.
    Only Admin and Staff can manage members.
    
    Args:
        user: The user to check
        group: The StudyGroup instance
        
    Returns:
        bool: True if user can manage members
    """
    return has_course_staff_privileges(user, group.course_id)


def can_user_view_group(user, group):
    """
    Check if user can view a study group.
    Admin/Staff can view all groups, regular users only their own groups.
    
    Args:
        user: The user to check
        group: The StudyGroup instance
        
    Returns:
        bool: True if user can view the group
    """
    if has_course_staff_privileges(user, group.course_id):
        return True
    return group.is_member(user)


def can_user_comment(user, group):
    """
    Check if user can add comments to a study group.
    Only members can comment.
    
    Args:
        user: The user to check
        group: The StudyGroup instance
        
    Returns:
        bool: True if user can comment
    """
    return group.is_member(user) or has_course_staff_privileges(user, group.course_id)


def can_user_edit_comment(user, comment):
    """
    Check if user can edit a comment.
    Admin/Staff can edit any comment, users can only edit their own.
    
    Args:
        user: The user to check
        comment: The StudyGroupComment instance
        
    Returns:
        bool: True if user can edit the comment
    """
    return comment.can_user_edit(user)


def can_user_delete_comment(user, comment):
    """
    Check if user can delete a comment.
    Admin/Staff can delete any comment, users can only delete their own.
    
    Args:
        user: The user to check
        comment: The StudyGroupComment instance
        
    Returns:
        bool: True if user can delete the comment
    """
    return comment.can_user_delete(user)

