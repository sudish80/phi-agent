"""Comprehensive credential manager test — validates all tools, logs to CSV."""

import sys
import os
import csv
import time
import json
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Clean any existing vault from previous runs
vault_dir = Path(__file__).parent / "backend" / "credentials"
if vault_dir.exists():
    shutil.rmtree(vault_dir)
    print(f"Cleaned existing vault at {vault_dir}")

from backend.tools.credential_manager import (
    credential_set_master_password, credential_verify_master,
    credential_change_master, credential_set_timeout, credential_lock,
    credential_save, credential_save_generated, credential_get,
    credential_search, credential_list, credential_delete,
    credential_update, credential_auto_login, credential_prompt_save,
    credential_health_report, credential_vault_stats,
    credential_export_csv, credential_import_csv, credential_export,
    credential_audit_log, credential_check_strength,
    credential_generate_password,
)

RESULTS = []
MASTER = "TestMaster100k!"
LOG_DIR = Path(__file__).parent / "test_logs"
LOG_DIR.mkdir(exist_ok=True)
CSV_PATH = LOG_DIR / f"credential_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


def log_result(tool: str, status: str, detail: str = "", duration_ms: float = 0.0):
    RESULTS.append({
        "tool": tool,
        "status": status,
        "detail": detail[:200],
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.now().isoformat(),
    })
    print(f"  [{status}] {tool} ({duration_ms:.0f}ms)" + (f" — {detail[:80]}" if detail else ""))


def test(tool_name: str, fn, *args, expected_ok: bool = True, **kwargs):
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        dur = (time.perf_counter() - t0) * 1000
        ok = "Error" not in result[:30] and "Cannot" not in result[:30] and "Failed" not in result[:30] and "Incorrect" not in result[:30] and "already" not in result[:30]
        if expected_ok:
            if ok:
                log_result(tool_name, "PASS", result[:100], dur)
            else:
                log_result(tool_name, "FAIL", f"Unexpected failure: {result[:100]}", dur)
        else:
            if not ok:
                log_result(tool_name, "PASS", f"Expected error: {result[:100]}", dur)
            else:
                log_result(tool_name, "FAIL", f"Expected failure but got: {result[:100]}", dur)
    except Exception as e:
        dur = (time.perf_counter() - t0) * 1000
        log_result(tool_name, "ERROR", f"{type(e).__name__}: {e}", dur)


print("=" * 60)
print("  CREDENTIAL MANAGER — COMPREHENSIVE TEST SUITE")
print("=" * 60)

# ── 1. Master password setup ──
print("\n[1] Master Password Setup")
test("set_master_password", credential_set_master_password, "Test123!")
test("set_master_password_duplicate", credential_set_master_password, "Test456!", expected_ok=False)
test("set_master_password_weak", credential_set_master_password, "a", expected_ok=False)
test("verify_master_correct", credential_verify_master, "Test123!")
test("verify_master_wrong", credential_verify_master, "wrong", expected_ok=False)

# Change to MASTER for the rest of the tests
credential_change_master("Test123!", MASTER)
test("verify_master", credential_verify_master, MASTER)
test("set_timeout", credential_set_timeout, 600)
test("set_timeout_zero", credential_set_timeout, 0)

# ── 2. Save credentials ──
print("\n[2] Save Credentials")
sites = [
    ("youtube", "user@yt.com", "YTpass123!", "https://youtube.com/login", "social"),
    ("github", "dev@gh.com", "GH_Str0ng!Pass", "https://github.com/login", "work"),
    ("gmail", "me@gmail.com", "Gm@il2024!Secure", "", "personal"),
    ("bank", "john.doe@bank.com", "B@nk!Pass99#Secure!", "https://online.bank.com/login", "finance"),
    ("reddit", "red_user", "R3ddit!Pass", "", "social"),
    ("linkedin", "john@linked.com", "L!nked1nPass", "https://linkedin.com/login", "work"),
    ("stackoverflow", "dev@so.com", "S0_0verflow!", "", "work"),
    ("twitter", "tweeter@x.com", "Tw33t!ng123", "", "social"),
    ("amazon", "shop@amz.com", "Amz0n!Shop#1", "https://amazon.com/gp/sign-in.html", "personal"),
    ("netflix", "binge@nf.com", "N3tfl!x#Watch", "https://netflix.com/login", "personal"),
]
for site, user, pwd, url, cat in sites:
    test(f"save_{site}", credential_save, MASTER, site, user, pwd, url, cat)

# ── 3. Get credentials ──
print("\n[3] Get Credentials")
for site, _, _, _, _ in sites:
    test(f"get_{site}", credential_get, MASTER, site)

test("get_nonexistent", credential_get, MASTER, "thissitedoesnotexist")

# ── 4. Search ──
print("\n[4] Search")
test("search_email", credential_search, MASTER, "gmail")
test("search_user", credential_search, MASTER, "dev")
test("search_none", credential_search, MASTER, "zzzzznothing")

# ── 5. List ──
print("\n[5] List")
test("list_all", credential_list, MASTER)
test("list_work", credential_list, MASTER, "work")
test("list_finance", credential_list, MASTER, "finance")
test("list_badcat", credential_list, MASTER, "invalid_cat")

# ── 6. Update ──
print("\n[6] Update")
test("update_password", credential_update, MASTER, "youtube", password="New!YTpass456#")
test("update_username", credential_update, MASTER, "gmail", username="new@gmail.com")
test("update_url", credential_update, MASTER, "github", url="https://github.com/new-login")
test("update_nonexistent", credential_update, MASTER, "nosuchsite", username="x")

# ── 7. Generate + Save ──
print("\n[7] Generate & Save")
test("save_generated", credential_save_generated, MASTER, "newgen", "gen@user.com", 24, True, "https://newgen.com/login", "other")
test("save_generated_short", credential_save_generated, MASTER, "gen2", "g2@user.com", 12, False)

# ── 8. Check strength ──
print("\n[8] Password Strength")
test("strength_weak", credential_check_strength, "abc")
test("strength_med", credential_check_strength, "MediumPass1")
test("strength_strong", credential_check_strength, "Str0ng!Compl3x#P@ss")
test("strength_empty", credential_check_strength, "")

# ── 9. Generate passwords ──
print("\n[9] Generate Passwords")
test("gen_default", credential_generate_password)
test("gen_short", credential_generate_password, 8, True)
test("gen_long_nosym", credential_generate_password, 32, False)

# ── 10. Health report ──
print("\n[10] Health Report")
test("health_report", credential_health_report, MASTER)

# ── 11. Vault stats ──
print("\n[11] Vault Stats")
test("vault_stats", credential_vault_stats, MASTER)

# ── 12. Export ──
print("\n[12] Export")
test("export_csv", credential_export_csv, MASTER)
test("export_json", credential_export, MASTER)

# ── 13. Import CSV ──
print("\n[13] Import CSV")
csv_data = "Site,Username,Password,URL,Category\nimported-site,imp@user.com,Imp0rt!Pass,https://import.com,other\nsite2,u2@s.com,P@ss2,https://s2.com,work"
test("import_csv", credential_import_csv, MASTER, csv_data)
test("verify_import", credential_list, MASTER)

# ── 14. Prompt save ──
print("\n[14] Prompt Save")
test("prompt_save_missing", credential_prompt_save, MASTER, "prompt-site")
test("prompt_save_full", credential_prompt_save, MASTER, "prompt-site", "prompt@user.com", "Pr0mpt!Pass")

# ── 15. Audit log ──
print("\n[15] Audit Log")
test("audit_log", credential_audit_log, MASTER, 10)

# ── 16. Auto-login (browser not tested, just validates) ──
print("\n[16] Auto-Login (validation only, no browser open)")
test("auto_login_exists", credential_auto_login, MASTER, "youtube")
test("auto_login_missing", credential_auto_login, MASTER, "nosuchsite")

# ── 17. Change master password ──
print("\n[17] Change Master Password")
test("change_master_wrong_old", credential_change_master, "wrong_old", "NewMaster123!", expected_ok=False)
test("change_master_weak_new", credential_change_master, MASTER, "a")
test("change_master_correct", credential_change_master, MASTER, "NewMaster123!")
test("verify_new_master", credential_verify_master, "NewMaster123!")
test("old_master_fails", credential_verify_master, MASTER, expected_ok=False)

# Change back
credential_change_master("NewMaster123!", MASTER)
test("change_master_back", credential_verify_master, MASTER)

# ── 18. Lock ──
print("\n[18] Lock")
test("lock_vault", credential_lock)
test("access_after_lock", credential_get, MASTER, "youtube")
test("lock_unlock", credential_verify_master, MASTER)

# ── 19. Delete ──
print("\n[19] Delete")
test("delete_nonexistent", credential_delete, MASTER, "nosuchsite")
test("delete_twitter", credential_delete, MASTER, "twitter")
test("delete_amazon", credential_delete, MASTER, "amazon")
test("delete_netflix", credential_delete, MASTER, "netflix")
test("verify_deleted", credential_get, MASTER, "twitter")

# ── Cleanup test sites ──
print("\n[20] Cleanup")
for site, _, _, _, _ in sites:
    credential_delete(MASTER, site)
credential_delete(MASTER, "newgen")
credential_delete(MASTER, "gen2")
credential_delete(MASTER, "imported-site")
credential_delete(MASTER, "site2")
credential_delete(MASTER, "prompt-site")
test("cleanup_verify", credential_list, MASTER)

# ── Write CSV ──
print(f"\n{'=' * 60}")
print(f"  Writing results to {CSV_PATH}")
print(f"{'=' * 60}")

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["tool", "status", "detail", "duration_ms", "timestamp"])
    writer.writeheader()
    writer.writerows(RESULTS)

# Summary
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
errors = sum(1 for r in RESULTS if r["status"] == "ERROR")
total = len(RESULTS)
total_ms = sum(r["duration_ms"] for r in RESULTS)

print(f"\n  RESULTS: {passed} PASS, {failed} FAIL, {errors} ERROR ({total} total)")
print(f"  Total time: {total_ms:.0f}ms ({total_ms/1000:.1f}s)")
print(f"  CSV: {CSV_PATH}")

if failed or errors:
    print(f"\n  FAILURES:")
    for r in RESULTS:
        if r["status"] in ("FAIL", "ERROR"):
            print(f"    [{r['status']}] {r['tool']}: {r['detail'][:120]}")
    sys.exit(1)
else:
    print(f"\n  ALL {total} TESTS PASSED")
