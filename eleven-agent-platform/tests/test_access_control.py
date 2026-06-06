from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authz.access_control import AccessController


def test_access_controller_intersects_requested_prefixes():
    controller = AccessController(
        enabled=True,
        default_allow=False,
        raw_rules="u1=doc-public|doc-team-a;u2=*",
    )

    decision = controller.resolve("u1", ["doc-team-a-secret", "doc-private"])

    assert decision.allowed is True
    assert decision.effective_prefixes == ["doc-team-a-secret"]


def test_access_controller_denies_user_without_policy_when_default_deny():
    controller = AccessController(
        enabled=True,
        default_allow=False,
        raw_rules="u1=doc-public",
    )

    decision = controller.resolve("u9", None)

    assert decision.allowed is False
    assert decision.reason == "no_policy"
