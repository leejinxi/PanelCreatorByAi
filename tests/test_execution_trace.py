import unittest

from agent.execution_trace import (
    begin_trace,
    end_trace,
    llm_trace_phase,
    record_llm,
    snapshot_trace,
)


class ExecutionTraceTests(unittest.TestCase):
    def test_records_parse_and_decision_durations_separately(self) -> None:
        token = begin_trace("direct-mock")
        try:
            with llm_trace_phase("parse"):
                record_llm(120)
            with llm_trace_phase("parse"):
                record_llm(30)
            with llm_trace_phase("decision"):
                record_llm(80)
            trace = snapshot_trace()
        finally:
            end_trace(token)

        self.assertEqual(trace["llm_duration_ms"], 230)
        self.assertEqual(trace["llm_call_count"], 3)
        self.assertEqual(trace["llm_calls"], [
            {"phase": "parse", "duration_ms": 120},
            {"phase": "parse", "duration_ms": 30},
            {"phase": "decision", "duration_ms": 80},
        ])


if __name__ == "__main__":
    unittest.main()
