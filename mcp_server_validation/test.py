from pathlib import Path

from benchmark.discopop_runner import DiscoPoPRunner


project = (
    Path(__file__).resolve().parent.parent
    / ".workspaces"
    / "jqlang__jq-2728"
)

print(f"Project: {project}")
print(f"Exists: {project.exists()}")

runner = DiscoPoPRunner(timeout=600)

result = runner.run(project)

print()
print("=== DiscoPoP RESULT ===")
print(result)