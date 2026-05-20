import json
import subprocess
import sys


def run_benchmark(import_stmt):
    script = f"""
import time
import sys
import os
import json

# Add src to sys.path
src_path = os.path.abspath(os.path.join(os.getcwd(), 'src'))
sys.path.insert(0, src_path)

start = time.monotonic()
try:
    {import_stmt}
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)
end = time.monotonic()

loaded_chutils = [m for m in sys.modules if m.startswith('chutils.')]
print(json.dumps({{"duration": end - start, "modules": loaded_chutils}}))
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        try:
            return json.loads(result.stdout)
        except:
            return None
    return json.loads(result.stdout)


if __name__ == "__main__":
    import_stmts = [
        "import chutils",
        "from chutils import retry",
        "from chutils import setup_logger",
        "from chutils import get_config_value"
    ]

    for stmt in import_stmts:
        print(f"\n--- Benchmarking: {stmt} ---")
        data = run_benchmark(stmt)
        if data:
            if "error" in data:
                print(f"Error: {data['error']}")
                continue
            print(f"Time taken: {data['duration']:.6f} seconds")
            print(f"Loaded chutils submodules: {len(data['modules'])}")
            if len(data['modules']) > 10:
                print(f"  (showing first 10 of {len(data['modules'])})")
                for m in sorted(data['modules'])[:10]:
                    print(f"  - {m}")
            else:
                for m in sorted(data['modules']):
                    print(f"  - {m}")
