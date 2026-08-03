"""
Minimal tenant resolver for authentication.
"""
from typing import Optional
import logging

from jose import JWTError, jwt

from ..config import settings

logger = logging.getLogger(__name__)


class TenantResolver:
    """Minimal tenant resolver that extracts tenant_id from JWT claims."""

    @staticmethod
    def resolve_tenant_from_token(token_payload: dict) -> Optional[str]:
        """
        Extract tenant_id from JWT token payload.

        Args:
            token_payload: Decoded JWT payload

        Returns:
            Tenant ID if found, None otherwise
        """
        # Try user_metadata first (most common location)
        if 'user_metadata' in token_payload:
            tenant_id = token_payload['user_metadata'].get('tenant_id')
            if tenant_id:
                return tenant_id

        # Try app_metadata as fallback
        if 'app_metadata' in token_payload:
            tenant_id = token_payload['app_metadata'].get('tenant_id')
            if tenant_id:
                return tenant_id

        # Try root level
        tenant_id = token_payload.get('tenant_id')
        if tenant_id:
            return tenant_id

        logger.warning("No tenant_id found in token payload")
        return None

    @staticmethod
    def resolve_tenant_from_user(user_data: dict) -> Optional[str]:
        """
        Extract tenant_id from user data.

        Args:
            user_data: User data dictionary

        Returns:
            Tenant ID if found, None otherwise
        """
        # Check various possible locations
        if 'tenant_id' in user_data:
            return user_data['tenant_id']

        if 'user_metadata' in user_data:
            tenant_id = user_data['user_metadata'].get('tenant_id')
            if tenant_id:
                return tenant_id

        if 'app_metadata' in user_data:
            tenant_id = user_data['app_metadata'].get('tenant_id')
            if tenant_id:
                return tenant_id

        return None

    @staticmethod
    async def resolve_tenant_id(
        user_id: str, user_email: str, token: Optional[str] = None
    ) -> Optional[str]:
        """
        Resolve the tenant ID for a user.

        Returns None when the tenant cannot be established. Callers must
        treat that as "no access", never as a default tenant.
        """
        # The token is the authority: it is signed, and the tenant claim was
        # put there at login. Prefer it over any local mapping.
        if token:
            try:
                payload = jwt.decode(
                    token,
                    settings.secret_key,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                tenant_id = TenantResolver.resolve_tenant_from_token(payload)
                if tenant_id:
                    return tenant_id
            except JWTError as exc:
                logger.warning(f"Could not read tenant claim from token: {exc}")

        # Fallback mapping by known user email, for tokens issued before the
        # claim was populated.
        known_tenants = {
            "sunset@propertyflow.com": "tenant-a",
            "ocean@propertyflow.com": "tenant-b",
            "candidate@propertyflow.com": "tenant-a",
        }
        if user_email in known_tenants:
            return known_tenants[user_email]

        # Fail closed. Defaulting here would hand an unrecognised user a real
        # tenant's data.
        logger.warning(f"Could not resolve a tenant for user {user_email!r}; denying access")
        return None

    @staticmethod
    async def update_user_tenant_metadata(user_id: str, tenant_id: str) -> None:
        """
        Update user metadata with tenant_id.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
        """
        # No-op in this resolver implementation.
        pass
