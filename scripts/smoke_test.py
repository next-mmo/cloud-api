from pathlib import Path
import py_compile
import sys

root = Path(__file__).resolve().parents[1]
python_files = list(root.rglob("*.py"))
for file in python_files:
    py_compile.compile(str(file), doraise=True)
print(f"Compiled {len(python_files)} Python files successfully.")

required = [
    root / "README.md",
    root / "docker-compose.yml",
    root / "apps/web/src/App.tsx",
    root / "workers/wangp/Dockerfile.gpu",
    root / "workers/voxcpm2/Dockerfile.gpu",
    root / "deploy/salad/create-queues.sh",
    root / "deploy/runpod/deploy-voxcpm2.sh",
    root / "deploy/clore/deploy-voxcpm2.sh",
    root / "deploy/vast/deploy-voxcpm2.sh",
    root / "workers/common/runpod_handler.py",
]
missing = [str(path.relative_to(root)) for path in required if not path.exists()]
if missing:
    print("Missing:", *missing, sep="\n- ")
    sys.exit(1)
print("Starter structure is complete.")
