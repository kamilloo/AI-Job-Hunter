import logging

import pytest

from job_hunter.collectors.calculate_discovery_status import DiscoveryStatus
from job_hunter.discovery_log_level import discovery_log_level


@pytest.mark.parametrize(
    ("status", "expected_level"),
    [
        (DiscoveryStatus.complete, logging.INFO),
        (DiscoveryStatus.partial, logging.WARNING),
        (DiscoveryStatus.failed, logging.ERROR),
        (DiscoveryStatus.no_sources, logging.WARNING),
    ],
)
def test_discovery_log_level(status, expected_level):
    assert discovery_log_level(status) == expected_level