from rest_framework.permissions import BasePermission


class IsRole(BasePermission):
    """
    Generic permission class to check if the authenticated user
    has one of the allowed roles.

    Usage:
        class SomeView(APIView):
            permission_classes = [IsRole(["company", "client"])]
    """

    def __init__(self, allowed_roles=None):
        self.allowed_roles = allowed_roles or []

    def has_permission(self, request, view):
        user = request.user

        # Must be authenticated
        if not user or not user.is_authenticated:
            return False

        # Must have a role attribute
        if not hasattr(user, "role"):
            return False

        return user.role in self.allowed_roles


class IsCompany(BasePermission):
    """
    Allows access only to users with role = 'company'.
    """
    message = "Access restricted to company accounts only."

    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and request.user.role == "company"
        )


class IsClient(BasePermission):
    """
    Allows access only to users with role = 'client'.
    """
    message = "Access restricted to client accounts only."

    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and request.user.role == "client"
        )


class IsCollector(BasePermission):
    """
    Allows access only to users with role = 'collector'.
    """
    message = "Access restricted to collector accounts only."

    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and request.user.role == "collector"
        )


class IsPrivateCollector(BasePermission):
    """
    Allows access only to users who are collectors
    AND marked as private collectors.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # Ensure the user has a linked collector profile
        collector = getattr(user, "collector", None)
        if collector and collector.is_private_collector:
            return True

        return False
    
    
class IsCompanyCollector(BasePermission):
    """
    Allows access only to users who are collectors
    AND employed by a company (not private).
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        collector = getattr(user, "collector", None)
        if collector and not collector.is_private_collector:
            return True

        return False
    

class IsSupervisor(BasePermission):
    """
    Allows access only to users with role = 'supervisor'.
    """
    message = "Access restricted to supervisor accounts only."

    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and request.user.role == "supervisor"
        )


class IsCollectorOrCompanyAdmin(BasePermission):
    """Allow:
    - collectors to view/update their own data
    - company admins to view all collectors in their company
    """


    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return user.role in ("collector", "company")

    
class IsSupervisorOrCompanyAdmin(BasePermission):
    """
    Allows access to supervisors or company admins
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return user.role in ("supervisor", "company")
    
class IsSupervisorOrCollector(BasePermission):
    """
    Allows access to supervisors or company admins
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return user.role in ("supervisor", "collector")