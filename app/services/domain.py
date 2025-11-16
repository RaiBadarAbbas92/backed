"""Domain-specific rules and utilities for Dragon Funded prop firm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Rule:
    """Represents a compliance rule or benefit."""

    title: str
    description: str
    category: str
    enforcement: str


CHALLENGE_RULES: List[Rule] = [
    Rule(
        title="Daily Loss Limit",
        description="Maximum daily loss is 5% of starting balance. Breaching this results in immediate account failure.",
        category="challenge",
        enforcement="Auto-liquidation at breach; notify compliance and reset challenge.",
    ),
    Rule(
        title="Overall Drawdown",
        description="Total drawdown must stay within 10% of starting balance across the entire challenge.",
        category="challenge",
        enforcement="If exceeded, challenge is failed and reset fee applies.",
    ),
    Rule(
        title="Economic News Restriction",
        description="Trading is prohibited 2 minutes before and after Tier-1 economic news releases.",
        category="challenge",
        enforcement="Violations trigger trade invalidation and potential challenge failure.",
    ),
]

KYC_RULES: List[Rule] = [
    Rule(
        title="Identity Verification",
        description="Government-issued photo ID and proof of residence less than 90 days old are required.",
        category="kyc",
        enforcement="Account remains in review until documents pass compliance.",
    ),
    Rule(
        title="Beneficiary Match",
        description="Withdrawal beneficiary name must match KYC profile exactly.",
        category="kyc",
        enforcement="Mismatches require re-submission and freeze payouts.",
    ),
]

WITHDRAWAL_RULES: List[Rule] = [
    Rule(
        title="Payout Cycle",
        description="First payout eligible after 14 trading days and 10% profit target. Subsequent payouts on bi-weekly schedule.",
        category="withdrawal",
        enforcement="Requests outside window are queued for next eligible date.",
    ),
    Rule(
        title="Preferred Methods",
        description="Supported methods: Bank wire (SWIFT/SEPA), USDT (ERC20/TRC20), Wise.",
        category="withdrawal",
        enforcement="Unsupported methods require finance approval.",
    ),
]

REFERRAL_PROGRAM: Dict[str, str] = {
    "bonus_structure": "Affiliates earn 10% of challenge fee on first purchase, 5% on renewals within 180 days.",
    "tracking": "Unique referral dashboard with real-time status and pending payouts.",
    "payout": "Monthly referral payouts, minimum threshold $50.",
}

DRAGON_CLUB_REWARDS: Dict[str, str] = {
    "trustpilot_reward": "$5 funded credit for published 4★+ Trustpilot review with ticket proof.",
    "video_story_reward": "$15 for 60s+ experience video submitted to support.",
    "social_share_reward": "$15 additional credit when video is posted publicly and link submitted.",
    "point_system": "Rewards delivered as Dragon Points (1 point = $1 credit) applied to next challenge or scaling fee.",
}


def list_rules(category: str) -> List[Rule]:
    """Return rules by category."""
    mapping = {
        "challenge": CHALLENGE_RULES,
        "kyc": KYC_RULES,
        "withdrawal": WITHDRAWAL_RULES,
    }
    return mapping.get(category, [])








