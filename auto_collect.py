
import subprocess
import sys
import time

while True:
    print("\nCollecting LEAF1 metrics...")

    subprocess.run(
        [sys.executable, "collector.py"],
        check=False
    )

    print("Next collection after 30 seconds...")
    time.sleep(30)
