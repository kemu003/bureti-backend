# students/permissions.py
from rest_framework import permissions

class IsAdminOrCommittee(permissions.BasePermission):
    """
    Permission to only allow admin or committee members.
    Admin role = Django admin (is_staff) OR role='admin'
    Committee role = role='committee'
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # 1. Django admin users
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # 2. Check custom role field
        if hasattr(request.user, 'role'):
            # Admin users (from custom role)
            if request.user.role == 'admin':
                return True
            # Committee members
            if request.user.role == 'committee':
                return True
            # Staff members
            if request.user.role == 'staff':
                return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # For now, same as has_permission
        return self.has_permission(request, view)