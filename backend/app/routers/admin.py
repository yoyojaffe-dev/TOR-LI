"""Admin / ops endpoints — development and manual-trigger use only.

Mounted only when ENVIRONMENT != "production".
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.agents.discovery_agent import DiscoveryAgent
from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.scraping_agent import ScrapingAgent

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/discovery/run")
async def trigger_discovery(
    lat: Annotated[float, Query(description="Centre latitude (default: Tel Aviv).")] = 32.0853,
    lng: Annotated[float, Query(description="Centre longitude (default: Tel Aviv).")] = 34.7818,
    radius_m: Annotated[
        int, Query(ge=100, le=50000, description="Search radius in metres.")
    ] = 5000,
) -> dict[str, Any]:
    """Trigger one Discovery Agent pass and return the count of shops upserted.

    Example:
        POST /admin/discovery/run?lat=32.0853&lng=34.7818&radius_m=5000
    """
    try:
        count = await DiscoveryAgent().discover(lat, lng, radius_m)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "success": True,
        "barbershops_upserted": count,
        "search": {"lat": lat, "lng": lng, "radius_m": radius_m},
    }


@router.post("/scraping/run")
async def trigger_scraping() -> dict[str, Any]:
    """Run one full Scraping Agent pass synchronously and return stats.

    Example:
        POST /admin/scraping/run
    """
    try:
        stats = await ScrapingAgent().run_once()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"success": True, **stats}


@router.post("/enrichment/run")
async def trigger_enrichment(
    limit: Annotated[int, Query(ge=1, le=500, description="Max shops to enrich this pass.")] = 50,
) -> dict[str, Any]:
    """Run one Enrichment Agent pass (staff + services) and return stats.

    Example:
        POST /admin/enrichment/run?limit=10
    """
    try:
        stats = await EnrichmentAgent().run_once(limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"success": True, **stats}
