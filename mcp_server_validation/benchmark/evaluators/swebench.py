import json
import subprocess
from pathlib import Path
from typing import Any, Dict


class SWEBenchEvaluator:
    """
    Evaluates generated patches using the official SWE-bench evaluator.
    """

    def evaluate(
        self,
        instance_id: str,
        model_name: str,
        patch: str,
        run_id: str,
        predictions_dir=None,
        reports_dir=None,
        dataset: str = "SWE-bench/SWE-bench_Multilingual",
        split: str = "test",
    ) -> Dict[str, Any]:

        if predictions_dir is None or reports_dir is None:
            raise ValueError(
                "predictions_dir and reports_dir are required"
            )

        predictions_dir = Path(predictions_dir)
        reports_dir = Path(reports_dir)

        predictions_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        reports_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        prediction_file = self._write_prediction(
            predictions_dir=predictions_dir,
            instance_id=instance_id,
            model_name=model_name,
            patch=patch,
        )

        command = [
            "swebench",
            "eval",
            dataset,
            "-p",
            str(prediction_file),
            "-i",
            instance_id,
            "--split",
            split,
            "--run-id",
            run_id,
            "--report-dir",
            str(reports_dir),
            "-j",
            "1",
        ]

        print("SWE-bench evaluation command:")
        print(" ".join(command))

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {
                "dataset": dataset,
                "split": split,
                "instance_id": instance_id,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "prediction_file": str(prediction_file),
                "report_file": None,
                "status": "evaluator_error",
                "accuracy": "N/A",
            }

        report_file = self._find_report(
            reports_dir=reports_dir,
            run_id=run_id,
        )

        evaluation = {
            "dataset": dataset,
            "split": split,
            "instance_id": instance_id,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "prediction_file": str(prediction_file),
            "report_file": (
                str(report_file)
                if report_file is not None
                else None
            ),
        }

        if report_file is None:
            evaluation["status"] = "N/A"
            evaluation["accuracy"] = "N/A"

            return evaluation

        evaluation.update(
            self._extract_result(
                report_file,
                instance_id,
            )
        )

        return evaluation

    def _write_prediction(
            self,
            predictions_dir: Path,
            instance_id: str,
            model_name: str,
            patch: str,
    ) -> Path:

        prediction_file = (
                predictions_dir / f"{instance_id}.json"
        )

        prediction = [
            {
                "instance_id": instance_id,
                "model_name_or_path": model_name,
                "model_patch": patch,
            }
        ]

        with prediction_file.open(
                "w",
                encoding="utf-8",
        ) as file:
            json.dump(
                prediction,
                file,
                indent=2,
            )

        return prediction_file

    def _find_report(
        self,
        reports_dir: Path,
        run_id: str,
    ) -> Path | None:

        reports = list(
            reports_dir.glob(f"*.{run_id}.json")
        )

        if not reports:
            return None

        return reports[0]

    def _extract_result(
            self,
            report_file: Path,
            instance_id: str,
    ) -> Dict[str, Any]:

        with report_file.open(
                "r",
                encoding="utf-8",
        ) as file:
            report = json.load(file)

        resolved_ids = report.get(
            "resolved_ids",
            [],
        )

        unresolved_ids = report.get(
            "unresolved_ids",
            [],
        )

        infra_failure_ids = report.get(
            "infra_failure_ids",
            [],
        )

        error_ids = report.get(
            "error_ids",
            [],
        )

        if instance_id in resolved_ids:
            accuracy = "100%"
            status = "resolved"

        elif instance_id in unresolved_ids:
            accuracy = "0%"
            status = "unresolved"

        elif instance_id in infra_failure_ids:
            accuracy = "N/A"
            status = "infra_failure"

        elif instance_id in error_ids:
            accuracy = "N/A"
            status = "error"

        else:
            accuracy = "N/A"
            status = "unknown"

        return {
            "status": status,
            "accuracy": accuracy,
            "resolved": instance_id in resolved_ids,
            "unresolved": instance_id in unresolved_ids,
            "infra_failure": instance_id in infra_failure_ids,
            "error": instance_id in error_ids,
            "report": report,
        }