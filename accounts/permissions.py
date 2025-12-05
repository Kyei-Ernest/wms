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


class IsCollectorOrCompanyAdmin(BasePermission):
    """Allow:
    - collectors to view/update their own data
    - company admins to view all collectors in their company
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "collector":
            return obj.user == user  

        if user.role == "company":
            return obj.company and obj.company.user == user  # company admin owns them

        return False
    
class IsSupervisorOrCompanyAdmin(BasePermission):
        """Rules:
        - Supervisors can edit their own profile
        - Company admin can view/update supervisors in their company
        """

        def has_object_permission(self, request, view, obj):
            user = request.user

            if user.role == "supervisor":
                return obj.user == user

            if user.role == "company":
                return obj.company.user == user

            return False