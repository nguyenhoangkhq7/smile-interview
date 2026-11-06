from typing import Dict, List
from skill_gap.domain.models import MatchResult


def build_match_map(match_results: List[MatchResult]) -> Dict[str, MatchResult]:
    """
    Builds a dictionary mapping jd_skill_id to MatchResult for O(1) lookup.
    If duplicate jd_skill_id entries exist, the first encountered match is preserved.
    """
    match_map: Dict[str, MatchResult] = {}
    for match in match_results:
        if match.jd_skill_id not in match_map:
            match_map[match.jd_skill_id] = match
    return match_map
