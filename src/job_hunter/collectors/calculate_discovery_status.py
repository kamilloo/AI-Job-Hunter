from enum import Enum

class DiscoveryStatus(str, Enum):
    complete = "complete"
    partial = "partial"
    failed = "failed"
    no_sources = "no_sources"

def calculate_discovery_status(
    total_sources: int,
    failed_sources: int,
) -> DiscoveryStatus:
    if total_sources < 0 or failed_sources < 0:
        raise ValueError("Counts must be non-negative")
    if failed_sources > total_sources:
        raise ValueError("Failed sources cannot exceed total sources")
    if total_sources == 0:
        return DiscoveryStatus.no_sources
    if failed_sources == 0:
        return DiscoveryStatus.complete
    if failed_sources < total_sources:
        return DiscoveryStatus.partial
    return DiscoveryStatus.failed
