import re
from typing import Any

INJECTION_PATTERNS = [
    r"ignore\s+previous",
    r"disregard",
    r"you\s+are\s+now",
    r"system\s*:",
    r"<\|",
    r"new\s+instructions",
    r"forget\s+(all|everything|prior)",
]


class Critic:
    """Checks pipeline data for prompt-injection and challenges suspicious findings."""

    def check(
        self,
        fivetran_report: dict[str, Any],
        bq_report: dict[str, Any],
    ) -> dict[str, Any]:
        flagged: list[str] = []

        for key, val in self._flatten(fivetran_report).items():
            if self._is_injected(val):
                flagged.append(f"fivetran.{key}")

        for key, val in self._flatten(bq_report).items():
            if self._is_injected(val):
                flagged.append(f"bq.{key}")

        challenges = self._challenge_findings(fivetran_report, bq_report)

        return {
            "is_safe": len(flagged) == 0,
            "flagged_fields": flagged,
            "challenges": challenges,
        }

    def _is_injected(self, val: Any) -> bool:
        if not isinstance(val, str):
            return False
        return any(re.search(p, val, re.IGNORECASE) for p in INJECTION_PATTERNS)

    def _flatten(self, d: dict, prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, full_key))
            else:
                result[full_key] = v
        return result

    def _challenge_findings(
        self,
        fivetran_report: dict[str, Any],
        bq_report: dict[str, Any],
    ) -> list[str]:
        challenges = []
        ft_rows = fivetran_report.get("row_count", 0)
        bq_rows = bq_report.get("row_count", 0)

        if ft_rows > 0 and bq_rows == 0:
            challenges.append("row_count_mismatch")

        return challenges
