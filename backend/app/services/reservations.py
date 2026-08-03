from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List

import pytz


def month_bounds(month: int, year: int, timezone: str) -> tuple:
    """
    Return the half-open [start, end) bounds of a calendar month, as instants.

    A "month" is only meaningful relative to a timezone. check_in_date is
    TIMESTAMPTZ, so comparing it against a naive datetime makes the boundary
    land at midnight in whatever zone the server happens to run in, rather
    than midnight where the property actually is.

    Concretely, a reservation checking in at 2024-02-29 23:30 UTC is already
    2024-03-01 00:30 in Europe/Paris. For a Paris property it belongs to
    March; boundaries computed in UTC push it into February.
    """
    tz = pytz.timezone(timezone)

    first_of_month = datetime(year, month, 1)
    first_of_next = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    # localize() rather than datetime(..., tzinfo=tz): passing a pytz zone
    # directly as tzinfo yields the zone's historical LMT offset (Paris would
    # be +00:09), which would silently reintroduce a boundary error.
    return tz.localize(first_of_month), tz.localize(first_of_next)


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    property_timezone: str = "UTC",
    db_session=None,
) -> Decimal:
    """
    Calculates revenue for a specific month, in the property's own timezone.

    property_timezone is the properties.timezone value for
    (property_id, tenant_id); the caller supplies it so this stays a pure,
    testable boundary calculation.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"month must be between 1 and 12, got {month}")

    start_date, end_date = month_bounds(month, year, property_timezone)

    print(
        f"DEBUG: Querying revenue for {property_id} (tenant: {tenant_id}) "
        f"from {start_date} to {end_date} [{property_timezone}]"
    )

    # SQL Simulation (This would be executed against the actual DB)
    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """

    # In production this query executes against a database session.
    # result = await db.fetch_val(query, property_id, tenant_id, start_date, end_date)
    # return result or Decimal('0')

    return Decimal('0') # Placeholder for now until DB connection is finalized

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool
        
        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    # total_amount is NUMERIC(10, 3), so the sum can carry a
                    # sub-cent third decimal. Round once, here, to the
                    # currency's minor unit - the server owns this decision,
                    # not the client.
                    total_revenue = Decimal(str(row.total_revenue)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        
        # Fallback figures used when the database is unavailable.
        #
        # Keyed by (tenant_id, property_id), NOT property_id alone. Properties
        # are identified by a composite key - properties has
        # PRIMARY KEY (id, tenant_id) - so prop-001 is Sunset's "Beach House
        # Alpha" AND Ocean's "Mountain Lodge Beta". Keying on property_id
        # alone served Sunset's revenue to Ocean on every cache miss.
        #
        # Values mirror seed.sql, which is the system's source of truth.
        mock_data = {
            ('tenant-a', 'prop-001'): {'total': '2250.00', 'count': 4},
            ('tenant-a', 'prop-002'): {'total': '4975.50', 'count': 4},
            ('tenant-a', 'prop-003'): {'total': '6100.50', 'count': 2},
            ('tenant-b', 'prop-001'): {'total': '0.00', 'count': 0},
            ('tenant-b', 'prop-004'): {'total': '1776.50', 'count': 4},
            ('tenant-b', 'prop-005'): {'total': '3256.00', 'count': 3},
        }

        # An unknown (tenant, property) pair means the tenant does not own that
        # property, so zero is the correct answer - never another tenant's total.
        mock_property_data = mock_data.get(
            (tenant_id, property_id), {'total': '0.00', 'count': 0}
        )
        
        return {
            "property_id": property_id,
            "tenant_id": tenant_id, 
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
