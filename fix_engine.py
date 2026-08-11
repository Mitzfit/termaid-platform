with open("backend/engine.py", "r") as f:
    lines = f.readlines()

clean_lines = [l for l in lines if "from backend.shell_engine import run_native_command" not in l]

insert_idx = 0
for i, line in enumerate(clean_lines):
    if line.startswith("from __future__"):
        insert_idx = i + 1

clean_lines.insert(insert_idx, "from backend.shell_engine import run_native_command\n")

with open("backend/engine.py", "w") as f:
    f.writelines(clean_lines)
