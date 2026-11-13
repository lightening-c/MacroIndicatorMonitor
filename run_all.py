"""
宏观数据跟踪 — 一键运行全流程
"""
import subprocess, sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

STEPS = [
    ("采集数据", "fetch_data.py"),
    ("分析引擎", "analyze.py"),
]


def main():
    for name, script in STEPS:
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"  {name}: {script}")
        print(sep)
        result = subprocess.run([PYTHON, os.path.join(BASE_DIR, script)], cwd=BASE_DIR)
        if result.returncode != 0:
            print(f"  FAIL (exit {result.returncode})")
            sys.exit(1)
        print(f"  OK")

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  ALL DONE!")
    print(sep)


if __name__ == "__main__":
    main()
