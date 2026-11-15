"""Total ordering over the `Tier` enum.

Lives in CE so any module can compare tiers without depending on EE code.
"""

from nortpole.server.settings.models import Tier
from nortpole.utils.variable_functionality import global_version

TIER_RANK: dict[Tier, int] = {
    Tier.COMMUNITY: 0,
    Tier.BUSINESS: 1,
    Tier.ENTERPRISE: 2,
}


def tier_at_least(current: Tier, required: Tier) -> bool:
    return TIER_RANK[current] >= TIER_RANK[required]


def get_current_tier() -> Tier:
    """The deployment's tier; Community when EE code is not loaded."""
    if not global_version.is_ee_version():
        return Tier.COMMUNITY
    from ee.nortpole.utils.tier import get_tier

    return get_tier()
