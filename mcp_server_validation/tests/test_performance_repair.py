import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.case import BenchmarkCase
from benchmark.evaluator import BenchmarkEvaluator
from benchmark.performance_repair import (
    MIN_PERFORMANCE_RATIO, bootstrap_interval, performance_point,
)


class PerformanceRepairTests(unittest.TestCase):
    def test_performance_runs_only_after_correctness(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            command = (
                "touch performance_ran; "
                "printf '%s' '{\"schema_version\":1,\"status\":\"pass\","
                "\"performance_point\":1,\"comparisons\":[]}'"
            )
            base = dict(
                index=1, repository="openmp_correctness_repair",
                name="synthetic", workspace=workspace, task="repair",
                build_command="true", profiling_command=None,
                performance_command=command,
            )
            failed = BenchmarkEvaluator().evaluate(
                BenchmarkCase(**base, test_command="false"), workspace
            )
            self.assertFalse(failed["passed"])
            self.assertFalse((workspace / "performance_ran").exists())

            passed = BenchmarkEvaluator().evaluate(
                BenchmarkCase(**base, test_command="true"), workspace
            )
            self.assertTrue(passed["passed"])
            self.assertTrue((workspace / "performance_ran").exists())
            self.assertEqual(passed["performance"]["report"]["performance_point"], 1)

    def test_paired_confidence_interval(self):
        self.assertEqual(bootstrap_interval([1.0] * 9), [1.0, 1.0])
        self.assertGreater(bootstrap_interval([1.0] * 9)[0], MIN_PERFORMANCE_RATIO)

    def test_performance_point_threshold(self):
        self.assertEqual(performance_point([0.91, 1.01]), ("pass", 1))
        self.assertEqual(performance_point([0.70, 0.89]), ("fail", 0))
        self.assertEqual(performance_point([0.85, 0.96]), ("inconclusive", None))


if __name__ == "__main__":
    unittest.main()
