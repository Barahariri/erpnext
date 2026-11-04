"""Offline source checks. This does not validate ERPNext runtime or financial correctness."""
from pathlib import Path
from collections import Counter
import ast
import re

ROOT = Path(__file__).resolve().parent
B = ROOT / "erpnext_clean_multicompany_v2.py"
V = ROOT / "erpnext_complete_v3.py"
bs = B.read_text(encoding="utf-8")
vs = V.read_text(encoding="utf-8")
bt = ast.parse(bs, filename=str(B))
vt = ast.parse(vs, filename=str(V))

def literal(tree, key):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == key for x in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing constant: {key}")

companies = literal(bt, "DATA")
coa = literal(bt, "COA")
fleet = literal(bt, "FLEET_CATALOG")
months = literal(vt, "START_MONTHS")
days = literal(vt, "POST_DAYS")
assert [(x["company"], x["abbr"], x["currency"]) for x in companies] == [
    ("Al Muhannadi Contracting", "AMQ", "QAR"),
    ("Al Furqan Contracting", "AFK", "KWD"),
    ("Al Salem Contracting", "ALS", "SYP"),
]
assert len({x["company"] for x in companies}) == 3
assert sum(len(x["projects"]) for x in companies) == 9
assert len({p[0] for x in companies for p in x["projects"]}) == 9
assert sum(len(x["staff"]) for x in companies) == 36
assert sum(map(len, fleet.values())) == 12
nums = [num for _, num, _, _ in coa]
nums += [num+i for _, num, _, leaves in coa for i in range(1, len(leaves)+1)]
assert len(nums) == len(set(nums)) and len(nums) >= 50, "Duplicate/insufficient chart codes"
assert all(100000 <= v < 600000 for v in nums)
assert months == ("2026-09", "2026-10", "2026-11")
assert days == (18, 16, 1)
assert days[-1]+3 <= 4, "November banking transaction is dated after Nov 4"
# Source contract for ERPNext v16 mandatory Sales Order/Invoice pricing fields.
assert "def setup_company_price_lists(d):" in bs
assert bs.count('"selling_price_list":') >= 2, "V2 Sales Order/Invoice price lists absent"
assert bs.count('"buying_price_list":') >= 2, "V2 Purchase Order price lists absent"
assert vs.count('"selling_price_list":') >= 1, "V3 Sales Invoice price list absent"
assert vs.count('"buying_price_list":') >= 3, "V3 purchasing price lists absent"
assert '"debit_to": frappe.db.get_value(' in bs, "V2 Sales Invoice receivable account absent"
assert '"posting_date": "2026-08-31", "posting_time": "12:00:00"' in bs, "V2 historical Sales Invoice posting time absent"
assert '"set_posting_time": 1, "due_date": "2026-09-30"' in bs, "V2 backdated invoice will reset to current date"
assert 'update_account_number(row.name' not in bs, "Per-account renaming regression"
for path in (B, V):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
runner = (ROOT / "run_from_git.sh").read_text()
for required in ("erpnext-clean-backend-1", "erpnext-clean-db-1", "bench --site", "backup", "install-app hrms"):
    assert required in runner
for unsafe in ("docker stop", "docker restart", "docker compose down", "docker system prune", "erpnext-backend-1:/tmp/"):
    assert unsafe not in runner, unsafe
print("SOURCE_CHECK_PASS: 3 companies, numbered chart, 9 projects, 36 staff, 12 fleet, Sep-Nov 2026")
print("IMPORTANT: Static checks are not acceptance tests; run the ERPNext audit on the NEW site.")
