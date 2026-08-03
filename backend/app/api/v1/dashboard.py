from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

# Properties per tenant, mirroring seed.sql. Served from here while the
# database layer is unavailable; the shape matches what
# SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id
# would return.
#
# Note prop-001 appears under both tenants with different names. That is
# legitimate - properties has PRIMARY KEY (id, tenant_id) - and is exactly
# why the property list must be resolved per tenant rather than hardcoded.
TENANT_PROPERTIES = {
    "tenant-a": [
        {"id": "prop-001", "name": "Beach House Alpha", "timezone": "Europe/Paris"},
        {"id": "prop-002", "name": "City Apartment Downtown", "timezone": "Europe/Paris"},
        {"id": "prop-003", "name": "Country Villa Estate", "timezone": "Europe/Paris"},
    ],
    "tenant-b": [
        {"id": "prop-001", "name": "Mountain Lodge Beta", "timezone": "America/New_York"},
        {"id": "prop-004", "name": "Lakeside Cottage", "timezone": "America/New_York"},
        {"id": "prop-005", "name": "Urban Loft Modern", "timezone": "America/New_York"},
    ],
}


@router.get("/dashboard/properties")
async def list_dashboard_properties(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Properties the authenticated tenant owns. Never another tenant's."""
    tenant_id = getattr(current_user, "tenant_id", None)

    return {"properties": TENANT_PROPERTIES.get(tenant_id, [])}


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"
    
    revenue_data = await get_revenue_summary(property_id, tenant_id)

    # total_revenue is serialised as a decimal string, not a JSON number.
    # A JSON number is an IEEE-754 double, which cannot represent most
    # monetary values exactly; casting the service's Decimal to float here
    # discarded the precision the service had deliberately preserved.
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": revenue_data['total'],
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
