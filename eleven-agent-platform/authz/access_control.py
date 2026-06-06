from dataclasses import dataclass


def _sanitize_prefixes(prefixes: list[str] | None) -> list[str]:
    if not prefixes:
        return []
    return [item.strip() for item in prefixes if item and item.strip()]


@dataclass
class AccessDecision:
    allowed: bool
    effective_prefixes: list[str] | None
    reason: str | None = None
    policy_prefixes: list[str] | None = None


class AccessController:
    def __init__(
        self,
        enabled: bool,
        default_allow: bool,
        raw_rules: str,
    ) -> None:
        self.enabled = enabled
        self.default_allow = default_allow
        self._rules = self._parse_rules(raw_rules)

    @staticmethod
    def _parse_rules(raw_rules: str) -> dict[str, list[str]]:
        rules: dict[str, list[str]] = {}
        for block in (raw_rules or "").split(";"):
            item = block.strip()
            if not item or "=" not in item:
                continue
            user_id, raw_prefixes = item.split("=", 1)
            prefixes = [prefix.strip() for prefix in raw_prefixes.split("|") if prefix.strip()]
            if user_id.strip() and prefixes:
                rules[user_id.strip()] = prefixes
        return rules

    @staticmethod
    def _intersect_prefixes(
        policy_prefixes: list[str],
        requested_prefixes: list[str],
    ) -> list[str]:
        effective: list[str] = []
        for requested in requested_prefixes:
            for allowed in policy_prefixes:
                if requested.startswith(allowed):
                    effective.append(requested)
                    break
                if allowed.startswith(requested):
                    effective.append(allowed)
        return list(dict.fromkeys(effective))

    def resolve(
        self,
        user_id: str,
        requested_prefixes: list[str] | None = None,
    ) -> AccessDecision:
        sanitized_requested = _sanitize_prefixes(requested_prefixes)
        if not self.enabled:
            return AccessDecision(
                allowed=True,
                effective_prefixes=sanitized_requested or None,
                reason="authz_disabled",
                policy_prefixes=None,
            )

        policy_prefixes = self._rules.get(user_id)
        if policy_prefixes and "*" in policy_prefixes:
            return AccessDecision(
                allowed=True,
                effective_prefixes=sanitized_requested or None,
                reason="wildcard_policy",
                policy_prefixes=policy_prefixes,
            )

        if not policy_prefixes:
            if self.default_allow:
                return AccessDecision(
                    allowed=True,
                    effective_prefixes=sanitized_requested or None,
                    reason="default_allow",
                    policy_prefixes=None,
                )
            return AccessDecision(
                allowed=False,
                effective_prefixes=[],
                reason="no_policy",
                policy_prefixes=None,
            )

        if not sanitized_requested:
            return AccessDecision(
                allowed=True,
                effective_prefixes=policy_prefixes,
                reason="policy_applied",
                policy_prefixes=policy_prefixes,
            )

        effective = self._intersect_prefixes(policy_prefixes, sanitized_requested)
        if not effective:
            return AccessDecision(
                allowed=False,
                effective_prefixes=[],
                reason="prefix_denied",
                policy_prefixes=policy_prefixes,
            )
        return AccessDecision(
            allowed=True,
            effective_prefixes=effective,
            reason="policy_intersection",
            policy_prefixes=policy_prefixes,
        )
