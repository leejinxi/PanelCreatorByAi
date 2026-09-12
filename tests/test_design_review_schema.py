import unittest

from pydantic import ValidationError

from schemas.design_review_schema import DesignReviewReport


def report_payload() -> dict:
    return {
        "ruleset_version": "demo-panel-review-1.0",
        "project_revision": "mock-r1",
        "outcome": "passed_with_warnings",
        "items": [{
            "rule_id": "PANEL-DEMO-004",
            "title": "邻近板架厚度一致性",
            "status": "warning",
            "summary": "存在差异。",
            "evidence": ["requested=14mm", "nearby=12mm"],
            "data_source": "mock_project_context",
        }],
        "plan_revision": {
            "changed": True,
            "disposition": "proceed_with_notice",
            "original_plan": ["准备创建"],
            "revised_plan": ["携带提醒创建"],
            "trigger_rule_ids": ["PANEL-DEMO-004"],
            "summary": "保留用户参数。",
        },
    }


class DesignReviewSchemaTests(unittest.TestCase):
    def test_accepts_consistent_warning_report(self) -> None:
        report = DesignReviewReport.model_validate(report_payload())
        self.assertEqual(report.outcome, "passed_with_warnings")
        self.assertFalse(report.has_blocker())

    def test_rejects_outcome_inconsistent_with_items(self) -> None:
        payload = report_payload()
        payload["outcome"] = "passed"
        with self.assertRaises(ValidationError):
            DesignReviewReport.model_validate(payload)

    def test_rejects_changed_plan_without_trigger(self) -> None:
        payload = report_payload()
        payload["plan_revision"]["trigger_rule_ids"] = []
        with self.assertRaises(ValidationError):
            DesignReviewReport.model_validate(payload)

    def test_rejects_unknown_fields(self) -> None:
        payload = report_payload()
        payload["hidden_reasoning"] = "not allowed"
        with self.assertRaises(ValidationError):
            DesignReviewReport.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
