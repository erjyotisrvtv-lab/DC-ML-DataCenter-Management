
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent

SOURCE = ROOT / "dashboard_ML_Based_Distributed_Cloud_Data_Center_Management.py"
OUTPUT = ROOT / "dashboard_3DC_Separate_Tabs.py"

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Dashboard file not found: {SOURCE.name}"
    )

source = SOURCE.read_text(encoding="utf-8-sig")

# Check original Python syntax
ast.parse(source)

if "tab_infra, tab_ml = st.tabs(" in source:
    raise RuntimeError("Source dashboard already contains the new tabs.")

lines = source.splitlines(keepends=True)

# Find beginning of Infrastructure Monitoring
infra_marker = "# DUAL ISP MONITORING - ISP-1 AND ISP-2"

# Find beginning of AI / ML Intelligence
ml_marker = (
    "st.subheader("
    "'🧠 AI / ML Intelligence | Anomaly Monitoring'"
    ")"
)

infra_index = next(
    (
        i for i, line in enumerate(lines)
        if infra_marker in line
    ),
    None
)

ml_index = next(
    (
        i for i, line in enumerate(lines)
        if ml_marker in line
    ),
    None
)

if infra_index is None or ml_index is None:
    raise RuntimeError(
        "Unable to locate Infrastructure or AI/ML sections."
    )

if ml_index <= infra_index:
    raise RuntimeError("Unexpected dashboard section order.")

# Include the divider before the Infrastructure section
infra_start = infra_index

while infra_start > 0 and (
    lines[infra_start - 1].strip() == ""
    or lines[infra_start - 1].strip().startswith("#")
    or lines[infra_start - 1].strip() == "st.divider()"
):
    infra_start -= 1

# Include divider immediately before AI/ML
ml_start = ml_index

while ml_start > infra_start and (
    lines[ml_start - 1].strip() == ""
    or lines[ml_start - 1].strip() == "st.divider()"
):
    ml_start -= 1


def indent_code(code_lines):
    return "".join(
        "    " + line if line.strip() else line
        for line in code_lines
    )


# Preserve dashboard configuration, imports,
# CSS, cached data loaders and sidebar controls.
common_code = "".join(lines[:infra_start])

infrastructure_code = "".join(
    lines[infra_start:ml_start]
)

ai_ml_code = "".join(
    lines[ml_start:]
)

tabs_header = """
# ==========================================================
# TOP-LEVEL DASHBOARD NAVIGATION
# ==========================================================

tab_infra, tab_ml = st.tabs([
    "🌐 Infrastructure Monitoring",
    "🧠 AI / ML Intelligence"
])

"""

new_source = (
    common_code
    + tabs_header
    + "\nwith tab_infra:\n"
    + indent_code(infrastructure_code.splitlines(keepends=True))
    + "\nwith tab_ml:\n"
    + indent_code(ai_ml_code.splitlines(keepends=True))
)

# Important: the original dashboard uses `scoped`
# for both router metrics and interface observations.
# Keep metric scope separate so the AI/ML tab can use
# the selected router data without being overwritten.
new_source = new_source.replace(
    "    scoped = latest_if if dc=='ALL' else latest_if[latest_if['data_center']==dc]",
    "    interface_scoped = latest_if if dc=='ALL' else latest_if[latest_if['data_center']==dc]"
)

# Replace the interface-health local references only.
begin = new_source.find("    interface_scoped = latest_if")
end = new_source.find("    routing = load_optional('routing_health.csv')", begin)

if begin >= 0 and end > begin:
    section = new_source[begin:end]
    section = section.replace("scoped", "interface_scoped")
    section = section.replace(
        "interface_interface_scoped",
        "interface_scoped"
    )
    new_source = new_source[:begin] + section + new_source[end:]

# Validate before writing
ast.parse(new_source)

OUTPUT.write_text(new_source, encoding="utf-8")

print("=" * 65)
print("SUCCESS: New dashboard created")
print("=" * 65)
print("Infrastructure Monitoring: Separate Tab")
print("AI / ML Intelligence: Separate Tab")
print("Original dashboard: Unchanged")
print("New dashboard:", OUTPUT.name)
print("Python syntax validation: PASSED")
print("=" * 65)
