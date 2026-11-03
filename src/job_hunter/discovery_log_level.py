import logging

from job_hunter.collectors.calculate_discovery_status import DiscoveryStatus

def discovery_log_level(status: DiscoveryStatus) -> int:
    return {
        DiscoveryStatus.complete: logging.INFO,
        DiscoveryStatus.partial: logging.WARNING,
        DiscoveryStatus.failed: logging.ERROR,
        DiscoveryStatus.no_sources: logging.WARNING,
    }[status]