from datasets import load_dataset

from benchmark.case import BenchmarkCase


class SWEBenchLoader:
    """
    Loads SWE-bench Multilingual cases and converts them into
    the benchmark's generic BenchmarkCase format.
    """

    DATASET = "SWE-bench/SWE-bench_Multilingual"

    def __init__(self, split: str = "test"):
        self.split = split
        self.dataset = None

    def load(self):
        self.dataset = load_dataset(
            self.DATASET,
            split=self.split,
        )

        return self.dataset

    def get_case(self, index: int) -> BenchmarkCase:
        if self.dataset is None:
            self.load()

        item = self.dataset[index]

        return BenchmarkCase(
            instance_id=item["instance_id"],
            task_type="software-engineering",
            repo=item["repo"],
            base_commit=item["base_commit"],
            problem_statement=item["problem_statement"],
            evaluator="swebench",
            language=item.get("language"),
            metadata={
                "patch": item["patch"],
                "test_patch": item["test_patch"],
                "FAIL_TO_PASS": item["FAIL_TO_PASS"],
                "PASS_TO_PASS": item["PASS_TO_PASS"],
                "eval_script": item["eval_script"],
                "version": item["version"],

                # SWE-bench dataset information
                "dataset": self.DATASET,
                "split": self.split,
            },
        )

    def size(self) -> int:
        if self.dataset is None:
            self.load()

        return len(self.dataset)