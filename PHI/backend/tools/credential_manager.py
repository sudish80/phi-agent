"""Credential manager — encrypted vault, auto-login, password health, and agent utilities.

Provides tools for the agent to:
  - Save/retrieve/update/delete credentials in an encrypted local vault (Fernet AES-128-CBC)
  - Auto-login: open browser login page + display credentials
  - Generate strong random passwords when saving
  - Password strength analysis and health reports
  - Bulk import/export (CSV, JSON)
  - Search across sites by keyword
  - Audit log of recent logins
  - Master password management (set, verify, change, session timeout)
  - Categorize saved sites (work, personal, finance, etc.)

Vault file: PHI/credentials/credentials.enc
Master hash: PHI/credentials/.master_hash
"""

import os
import json
import csv
import io
import base64
import hashlib
import secrets
import string
import logging
import asyncio
import time
import webbrowser
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).resolve().parent.parent / "credentials"
VAULT_FILE = VAULT_DIR / "credentials.enc"
MASTER_HASH_FILE = VAULT_DIR / ".master_hash"
AUDIT_LOG_FILE = VAULT_DIR / "audit.log"

# ── Defaults ─────────────────────────────────────────────────
SESSION_TIMEOUT_SECONDS = 300  # 5 min idle before re-prompt
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# ── In-memory state ──────────────────────────────────────────
_vault_cache: Optional[Dict] = None
_last_unlock: float = 0.0
_master_key: Optional[bytes] = None
_session_timeout: int = SESSION_TIMEOUT_SECONDS


# ====================================================================
#  INTERNAL HELPERS
# ====================================================================

def _ensure_vault_dir():
    VAULT_DIR.mkdir(parents=True, exist_ok=True)


def _vault_key_from_master(master_password: str) -> bytes:
    raw = hashlib.sha256(master_password.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)


def _hash_master(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _master_hash_exists() -> bool:
    return MASTER_HASH_FILE.exists()


def _get_stored_master_hash() -> Optional[str]:
    if not _master_hash_exists():
        return None
    return MASTER_HASH_FILE.read_text(encoding="utf-8").strip()


def _save_master_hash(password: str):
    _ensure_vault_dir()
    MASTER_HASH_FILE.write_text(_hash_master(password), encoding="utf-8")


def _normalize_site(site: str) -> str:
    s = site.strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    s = s.rstrip("/")
    return s


def _password_strength(password: str) -> Tuple[str, int]:
    """Return (label, score_0_to_100)."""
    score = 0
    if len(password) >= 8:
        score += 20
    if len(password) >= 12:
        score += 10
    if len(password) >= 16:
        score += 10
    if re.search(r"[a-z]", password):
        score += 10
    if re.search(r"[A-Z]", password):
        score += 10
    if re.search(r"[0-9]", password):
        score += 10
    if re.search(r"[^a-zA-Z0-9]", password):
        score += 15
    if len(set(password)) >= len(password) * 0.7:
        score += 5
    common = ["password", "123456", "qwerty", "abc123", "letmein", "admin", "welcome"]
    if password.lower() not in common:
        score += 10
    score = min(score, 100)
    if score < 40:
        label = "Weak"
    elif score < 70:
        label = "Moderate"
    else:
        label = "Strong"
    return label, score


def _generate_password(length: int = 20, include_digits: bool = True,
                       include_symbols: bool = True) -> str:
    chars = string.ascii_letters
    if include_digits:
        chars += string.digits
    if include_symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    if length < 4:
        length = 4
    if length > PASSWORD_MAX_LENGTH:
        length = PASSWORD_MAX_LENGTH
    return "".join(secrets.choice(chars) for _ in range(length))


def _audit_log(action: str, site: str = "", username: str = ""):
    """Append an audit entry (no sensitive data — just site + action)."""
    try:
        _ensure_vault_dir()
        ts = datetime.now(timezone.utc).isoformat()
        line = f"[{ts}] {action} | site={site} | user={username}\n"
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.warning("Audit log write failed: %s", e)


def _vault_stats() -> Dict:
    if not _vault_cache:
        return {"total": 0, "weak": 0, "old": 0, "avg_strength": 0}
    total = len(_vault_cache)
    weak = 0
    strengths = []
    old_threshold = datetime.now(timezone.utc) - timedelta(days=180)
    old = 0
    for entry in _vault_cache.values():
        pwd = entry.get("password", "")
        _, sc = _password_strength(pwd)
        strengths.append(sc)
        if sc < 40:
            weak += 1
        updated_str = entry.get("updated_at", "")
        if updated_str:
            try:
                updated = datetime.fromisoformat(updated_str)
                if updated < old_threshold:
                    old += 1
            except (ValueError, TypeError):
                pass
    avg = round(sum(strengths) / len(strengths), 1) if strengths else 0
    return {"total": total, "weak": weak, "old": old, "avg_strength": avg}


# ====================================================================
#  VAULT I/O
# ====================================================================

def _load_vault_from_disk(master_password: str) -> Optional[Dict]:
    global _vault_cache, _last_unlock, _master_key
    if not VAULT_FILE.exists():
        _vault_cache = {}
        _master_key = _vault_key_from_master(master_password)
        _last_unlock = time.time()
        return _vault_cache
    try:
        key = _vault_key_from_master(master_password)
        fernet = Fernet(key)
        encrypted = VAULT_FILE.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        data = json.loads(decrypted.decode("utf-8"))
        if not isinstance(data, dict):
            logger.warning("Vault format invalid, resetting")
            data = {}
        _vault_cache = data
        _master_key = key
        _last_unlock = time.time()
        return data
    except (InvalidToken, json.JSONDecodeError, Exception) as e:
        logger.error("Failed to decrypt vault: %s", e)
        return None


def _flush_vault() -> bool:
    global _vault_cache, _master_key
    if _vault_cache is None or _master_key is None:
        return False
    try:
        fernet = Fernet(_master_key)
        plain = json.dumps(_vault_cache, indent=2).encode("utf-8")
        encrypted = fernet.encrypt(plain)
        _ensure_vault_dir()
        VAULT_FILE.write_bytes(encrypted)
        return True
    except Exception as e:
        logger.error("Failed to flush vault: %s", e)
        return False


def _ensure_unlocked(master_password: str) -> bool:
    global _vault_cache, _last_unlock, _master_key
    if _master_hash_exists():
        stored = _get_stored_master_hash()
        if stored != _hash_master(master_password):
            return False
    if _vault_cache is None or _master_key is None:
        vault = _load_vault_from_disk(master_password)
        if vault is None:
            return False
    if time.time() - _last_unlock > _session_timeout:
        _vault_cache = None
        _master_key = None
        vault = _load_vault_from_disk(master_password)
        if vault is None:
            return False
    return True


# ====================================================================
#  TOOL FUNCTIONS
# ====================================================================

def credential_set_master_password(password: str) -> str:
    """Set the master vault password. Call this first before using any credential tools."""
    global _vault_cache, _master_key, _last_unlock
    if _master_hash_exists():
        return "Master password already set. Use credential_verify_master to unlock, or credential_change_master to change it."
    label, score = _password_strength(password)
    if score < 40:
        return (
            f"Your master password is too weak ({label}, {score}/100). "
            f"Use a stronger password with at least 8 characters, mixing upper/lowercase, digits, and symbols."
        )
    _ensure_vault_dir()
    _save_master_hash(password)
    key = _vault_key_from_master(password)
    _vault_cache = {}
    _master_key = key
    _last_unlock = time.time()
    _flush_vault()
    _audit_log("MASTER_SET")
    return f"Master password set and vault initialized (strength: {label}, {score}/100)."


def credential_verify_master(password: str) -> str:
    """Verify the master password and unlock the vault session (valid for configurable timeout)."""
    if _ensure_unlocked(password):
        remaining = max(0, int(_session_timeout - (time.time() - _last_unlock)))
        return f"Vault unlocked. Session expires in {remaining}s."
    return "Incorrect master password."


def credential_change_master(old_password: str, new_password: str) -> str:
    """Change the master vault password. Re-encrypts all stored credentials with new key."""
    global _vault_cache, _master_key, _last_unlock
    if not _ensure_unlocked(old_password):
        return "Cannot unlock vault with old password."
    label, score = _password_strength(new_password)
    if score < 40:
        return f"New password is too weak ({label}, {score}/100). Use a stronger password."
    new_key = _vault_key_from_master(new_password)
    _master_key = new_key
    _save_master_hash(new_password)
    _last_unlock = time.time()
    if _flush_vault():
        _audit_log("MASTER_CHANGED")
        return f"Master password changed (strength: {label}, {score}/100). All credentials re-encrypted."
    return "Failed to change master password."


def credential_set_timeout(seconds: int) -> str:
    """Set the auto-lock timeout in seconds (default 300). Use 0 to disable auto-lock."""
    global _session_timeout
    if seconds < 0:
        seconds = 0
    _session_timeout = seconds
    if seconds == 0:
        return "Auto-lock disabled. Vault stays unlocked until you lock it manually."
    return f"Auto-lock set to {seconds}s ({seconds//60} min)."


def credential_lock() -> str:
    """Lock the vault immediately (clears in-memory decrypted data)."""
    global _vault_cache, _master_key, _last_unlock
    _vault_cache = None
    _master_key = None
    _last_unlock = 0.0
    return "Vault locked."


def credential_save(master_password: str, site: str, username: str, password: str,
                    url: str = "", category: str = "", notes: str = "") -> str:
    """Save a credential to the encrypted vault.

    Args:
        master_password: Your master vault password
        site: Site name (e.g., 'youtube', 'gmail', 'github')
        username: Username or email for login
        password: Password to store
        url: Optional login page URL (auto-generated if empty)
        category: Optional category tag (work, personal, finance, social, other)
        notes: Optional notes about this credential
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    label, ps = _password_strength(password)
    site_key = _normalize_site(site)
    existing = _vault_cache.get(site_key, {})
    entry = {
        "site": site.strip(),
        "username": username,
        "password": password,
        "url": url.strip() if url else f"https://{site_key}/login",
        "category": category.strip() if category else existing.get("category", ""),
        "notes": notes.strip() if notes else existing.get("notes", ""),
        "strength_label": label,
        "strength_score": ps,
        "created_at": existing.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _vault_cache[site_key] = entry
    if _flush_vault():
        _audit_log("SAVE", site, username)
        warning = ""
        if ps < 40:
            warning = f"\nWarning: The password is weak ({label}, {ps}/100). Consider using a stronger one."
        elif ps < 70:
            warning = f"\nNote: Password strength is {label} ({ps}/100)."
        return f"Saved credentials for '{site}'.{warning}"
    return "Failed to save credentials."


def credential_save_generated(master_password: str, site: str, username: str,
                              length: int = 20, include_symbols: bool = True,
                              url: str = "", category: str = "") -> str:
    """Generate a strong random password and save it for a site.

    Args:
        master_password: Master vault password
        site: Site name
        username: Username or email
        length: Password length (8-128, default 20)
        include_symbols: Whether to include special characters
        url: Optional login page URL
        category: Optional category tag
    """
    pwd = _generate_password(length, include_symbols=include_symbols)
    label, ps = _password_strength(pwd)
    result = credential_save(master_password, site, username, pwd, url, category)
    return (
        f"{result}\n"
        f"Generated password ({length} chars, {label}, {ps}/100): {pwd}\n"
        f"Please copy this password now — it won't be shown again after this message."
    )


def credential_get(master_password: str, site: str) -> str:
    """Retrieve a saved credential by site name.

    Args:
        master_password: Your master vault password
        site: Site name to look up
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    site_key = _normalize_site(site)
    entry = _vault_cache.get(site_key)
    if not entry:
        similar = _credential_search(site)
        if similar:
            matches = ", ".join(similar[:5])
            return f"No exact match for '{site}'. Did you mean: {matches}?"
        return f"No saved credentials for '{site}'. Use credential_save to store them first."
    _audit_log("VIEW", site, entry.get("username", ""))
    label = entry.get("strength_label", "?")
    score = entry.get("strength_score", "?")
    cat = entry.get("category", "")
    notes = entry.get("notes", "")
    lines = [
        f"Site: {entry['site']}",
        f"Username: {entry['username']}",
        f"Password: {entry['password']}",
        f"URL: {entry.get('url', 'N/A')}",
        f"Strength: {label} ({score}/100)",
    ]
    if cat:
        lines.append(f"Category: {cat}")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)


def _credential_search(query: str) -> List[str]:
    """Search saved sites by partial name match."""
    if not _vault_cache:
        return []
    q = query.lower()
    matches = []
    for key, entry in _vault_cache.items():
        site_name = entry.get("site", key).lower()
        username = entry.get("username", "").lower()
        if q in site_name or q in key or q in username:
            matches.append(entry.get("site", key))
    return matches


def credential_search(master_password: str, query: str) -> str:
    """Search saved credentials by site name or username keyword.

    Args:
        master_password: Your master vault password
        query: Keyword to search for
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    matches = _credential_search(query)
    if not matches:
        return f"No credentials match '{query}'."
    lines = [f"Found {len(matches)} match(es) for '{query}':"]
    for m in sorted(matches):
        entry = _vault_cache.get(_normalize_site(m), {})
        username = entry.get("username", "?")
        lines.append(f"  - {m} (user: {username})")
    return "\n".join(lines)


def credential_list(master_password: str, category: str = "") -> str:
    """List all sites with saved credentials, optionally filtered by category.

    Args:
        master_password: Your master vault password
        category: Optional category filter (work, personal, finance, social, other)
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not _vault_cache:
        return "No credentials saved yet."
    items = []
    for key, entry in sorted(_vault_cache.items()):
        if category and entry.get("category", "").lower() != category.lower():
            continue
        site = entry.get("site", key)
        username = entry.get("username", "?")
        cat_tag = f" [{entry.get('category', '')}]" if entry.get("category") else ""
        items.append(f"  - {site}{cat_tag} (user: {username})")
    if not items:
        if category:
            return f"No credentials found in category '{category}'."
        return "No credentials saved yet."
    stats = _vault_stats()
    header = f"Saved credentials ({len(items)} shown, {stats['total']} total):"
    return "\n".join([header] + items)


def credential_delete(master_password: str, site: str) -> str:
    """Delete a saved credential by site name.

    Args:
        master_password: Your master vault password
        site: Site name to delete
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    site_key = _normalize_site(site)
    if site_key not in _vault_cache:
        return f"No credentials found for '{site}'."
    del _vault_cache[site_key]
    if _flush_vault():
        _audit_log("DELETE", site)
        return f"Deleted credentials for '{site}'."
    return "Failed to delete credentials."


def credential_update(master_password: str, site: str, username: str = "",
                      password: str = "", url: str = "", category: str = "",
                      notes: str = "") -> str:
    """Update an existing credential. Leave fields blank to keep current values.

    Args:
        master_password: Your master vault password
        site: Site name to update
        username: New username (blank to keep)
        password: New password (blank to keep)
        url: New login URL (blank to keep)
        category: New category tag (blank to keep)
        notes: New notes (blank to keep)
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    site_key = _normalize_site(site)
    if site_key not in _vault_cache:
        return f"No credentials found for '{site}'. Use credential_save instead."
    entry = _vault_cache[site_key]
    if username:
        entry["username"] = username
    if password:
        entry["password"] = password
        label, ps = _password_strength(password)
        entry["strength_label"] = label
        entry["strength_score"] = ps
    if url:
        entry["url"] = url
    if category:
        entry["category"] = category
    if notes:
        entry["notes"] = notes
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _vault_cache[site_key] = entry
    if _flush_vault():
        _audit_log("UPDATE", site, entry.get("username", ""))
        return f"Updated credentials for '{site}'."
    return "Failed to update credentials."


def credential_auto_login(master_password: str, site: str) -> str:
    """Open a website's login page in the browser and display saved credentials.

    The agent calls this when the user says 'log in to <site>' or 'open <site>'.
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    site_key = _normalize_site(site)
    entry = _vault_cache.get(site_key)
    if not entry:
        return (
            f"No saved credentials for '{site}'. "
            f"Use credential_save(master_password, '{site}', 'your_username', 'your_password') first, "
            f"or ask me to generate and save a password."
        )
    login_url = entry.get("url", "")
    if not login_url:
        login_url = f"https://{site_key}/login"
    try:
        webbrowser.open(login_url)
    except Exception as e:
        logger.warning("Failed to open browser: %s", e)
    _audit_log("AUTO_LOGIN", site, entry.get("username", ""))
    label = entry.get("strength_label", "?")
    return (
        f"Opened {login_url} in your browser.\n"
        f"Credentials for {entry['site']}:\n"
        f"  Username: {entry['username']}\n"
        f"  Password: {entry['password']}\n"
        f"  (Strength: {label})\n\n"
        f"Your credentials are displayed above. Use them promptly for security."
    )


def credential_prompt_save(master_password: str, site: str,
                           username: str = "", password: str = "") -> str:
    """Prompt the user to save credentials for a site they just used.

    Call this when the user says 'save my password for <site>'.
    If username/password are omitted, tells the user what is needed.
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not username or not password:
        return (
            f"To save credentials for '{site}', I need:\n"
            f"  - Username or email\n"
            f"  - Password\n\n"
            f"Please provide them and I will store them securely in the encrypted vault."
        )
    return credential_save(master_password, site, username, password)


def credential_health_report(master_password: str) -> str:
    """Generate a password health report: weak passwords, old passwords, duplicates.

    Args:
        master_password: Your master vault password
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not _vault_cache:
        return "No credentials in vault."
    stats = _vault_stats()
    lines = [
        "=" * 40,
        "  PASSWORD HEALTH REPORT",
        "=" * 40,
        f"Total credentials: {stats['total']}",
        f"Weak passwords (< 40/100): {stats['weak']}",
        f"Credentials not updated in 180+ days: {stats['old']}",
        f"Average strength score: {stats['avg_strength']}/100",
        "",
    ]
    if stats["weak"] > 0:
        lines.append("--- Weak passwords ---")
        for key, entry in sorted(_vault_cache.items()):
            ps = entry.get("strength_score", 0)
            if ps < 40:
                lines.append(f"  {entry['site']}: {ps}/100")
        lines.append("")
    reused = _find_reused_passwords()
    if reused:
        lines.append("--- Reused passwords ---")
        for pwd_hash, sites in reused.items():
            if len(sites) > 1:
                lines.append(f"  Password reused across: {', '.join(sites)}")
        lines.append("")
    old_list = _find_old_credentials()
    if old_list:
        lines.append("--- Old credentials (180+ days) ---")
        for item in old_list:
            lines.append(f"  {item['site']} (last updated: {item['updated_at'][:10]})")
        lines.append("")
    lines.append("Tip: Use credential_save_generated to replace weak passwords with strong random ones.")
    return "\n".join(lines)


def _find_reused_passwords() -> Dict[str, List[str]]:
    """Find passwords used on multiple sites (hashed for comparison)."""
    by_hash: Dict[str, List[str]] = {}
    for key, entry in (_vault_cache or {}).items():
        pwd = entry.get("password", "")
        h = hashlib.md5(pwd.encode("utf-8")).hexdigest()
        by_hash.setdefault(h, []).append(entry.get("site", key))
    return by_hash


def _find_old_credentials() -> List[Dict]:
    """Find credentials not updated in the last 180 days."""
    threshold = datetime.now(timezone.utc) - timedelta(days=180)
    old = []
    for key, entry in (_vault_cache or {}).items():
        updated_str = entry.get("updated_at", "")
        if updated_str:
            try:
                updated = datetime.fromisoformat(updated_str)
                if updated < threshold:
                    old.append({"site": entry.get("site", key), "updated_at": updated_str})
            except (ValueError, TypeError):
                pass
    return old


def credential_vault_stats(master_password: str) -> str:
    """Show vault statistics: total credentials, strength distribution, categories.

    Args:
        master_password: Your master vault password
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    stats = _vault_stats()
    cat_counts = {}
    for entry in (_vault_cache or {}).values():
        cat = entry.get("category", "uncategorized") or "uncategorized"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    lines = [
        "=" * 40,
        "  VAULT STATISTICS",
        "=" * 40,
        f"Total sites: {stats['total']}",
        f"Weak passwords: {stats['weak']}",
        f"Old credentials (180d+): {stats['old']}",
        f"Average strength: {stats['avg_strength']}/100",
        "",
        "--- Categories ---",
    ]
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {count}")
    timeout_str = f"{_session_timeout}s ({_session_timeout//60}min)" if _session_timeout else "disabled"
    lines.append(f"\nAuto-lock timeout: {timeout_str}")
    return "\n".join(lines)


def credential_export_csv(master_password: str) -> str:
    """Export all credentials as CSV (for spreadsheets). Excludes actual passwords by default.

    Args:
        master_password: Your master vault password
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not _vault_cache:
        return "No credentials to export."
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Site", "Username", "Strength", "Category", "URL", "Updated"])
    for key, entry in sorted(_vault_cache.items()):
        writer.writerow([
            entry.get("site", key),
            entry.get("username", ""),
            entry.get("strength_label", "?"),
            entry.get("category", ""),
            entry.get("url", ""),
            entry.get("updated_at", "")[:10],
        ])
    return output.getvalue()


def credential_import_csv(master_password: str, csv_data: str) -> str:
    """Import credentials from CSV data. Format: Site, Username, Password, URL, Category.

    Args:
        master_password: Your master vault password
        csv_data: CSV content with header row
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        imported = 0
        errors = []
        for row in reader:
            site = row.get("Site", "").strip()
            username = row.get("Username", "").strip()
            password = row.get("Password", "").strip()
            url = row.get("URL", "").strip()
            category = row.get("Category", "").strip()
            if not site or not username or not password:
                errors.append(f"Row {imported + 2}: missing required fields")
                continue
            credential_save(master_password, site, username, password, url, category)
            imported += 1
        msg = f"Imported {imported} credential(s) from CSV."
        if errors:
            msg += f"\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
        _audit_log("IMPORT_CSV", f"{imported} sites")
        return msg
    except Exception as e:
        return f"CSV import error: {e}"


def credential_export(master_password: str) -> str:
    """Export all credentials as JSON (for personal backup). Includes passwords.

    Args:
        master_password: Your master vault password
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not _vault_cache:
        return "No credentials to export."
    _audit_log("EXPORT_JSON", f"{len(_vault_cache)} sites")
    return json.dumps(_vault_cache, indent=2, default=str)


def credential_audit_log(master_password: str, lines: int = 20) -> str:
    """Show recent audit log entries (login attempts, saves, deletes).

    Args:
        master_password: Your master vault password
        lines: Number of recent log lines to show (default 20)
    """
    if not _ensure_unlocked(master_password):
        return "Cannot unlock vault. Check your master password."
    if not AUDIT_LOG_FILE.exists():
        return "No audit entries yet."
    try:
        all_lines = AUDIT_LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        recent = all_lines[-lines:]
        return "Recent audit log:\n" + "\n".join(recent)
    except Exception as e:
        return f"Failed to read audit log: {e}"


def credential_check_strength(password: str) -> str:
    """Check the strength of a password without saving it. Returns label and score.

    Args:
        password: The password to evaluate
    """
    label, score = _password_strength(password)
    tips = []
    if len(password) < 8:
        tips.append("Use at least 8 characters")
    if not re.search(r"[A-Z]", password):
        tips.append("Add uppercase letters")
    if not re.search(r"[0-9]", password):
        tips.append("Add digits")
    if not re.search(r"[^a-zA-Z0-9]", password):
        tips.append("Add special characters (!@#$%^&*)")
    result = f"Strength: {label} ({score}/100)"
    if tips:
        result += "\nTips to improve:\n" + "\n".join(f"  - {t}" for t in tips)
    return result


def credential_generate_password(length: int = 20, include_symbols: bool = True) -> str:
    """Generate a cryptographically secure random password and show its strength.

    Args:
        length: Password length (8-128, default 20)
        include_symbols: Include special characters
    """
    if length < 4:
        length = 4
    if length > PASSWORD_MAX_LENGTH:
        length = PASSWORD_MAX_LENGTH
    pwd = _generate_password(length, include_symbols=include_symbols)
    label, score = _password_strength(pwd)
    return (
        f"Generated password ({length} chars, {label}, {score}/100):\n"
        f"{pwd}\n\n"
        f"Use credential_save to store this for a specific site, "
        f"or credential_save_generated to generate + save in one step."
    )


# ====================================================================
#  TOOL REGISTRATION
# ====================================================================

def get_credential_tools():
    from backend.tools.autoregister import _make_tool
    return [
        _make_tool("credential_set_master_password",
            "Set the master vault password. Call this first before using any other credential tools.",
            {"type": "object", "properties": {"password": {"type": "string", "description": "Your master vault password"}}, "required": ["password"]},
            credential_set_master_password, "utility"),

        _make_tool("credential_verify_master",
            "Verify master password to unlock vault session. Session stays unlocked for a configurable timeout (default 5 min).",
            {"type": "object", "properties": {"password": {"type": "string", "description": "Your master vault password"}}, "required": ["password"]},
            credential_verify_master, "utility"),

        _make_tool("credential_change_master",
            "Change the master vault password. All stored credentials are re-encrypted with the new key.",
            {"type": "object", "properties": {
                "old_password": {"type": "string", "description": "Current master password"},
                "new_password": {"type": "string", "description": "New master password (min 8 chars, mix upper/lower/digits/symbols)"},
            }, "required": ["old_password", "new_password"]},
            credential_change_master, "utility"),

        _make_tool("credential_set_timeout",
            "Set the vault auto-lock timeout in seconds (default 300). Pass 0 to disable auto-lock.",
            {"type": "object", "properties": {"seconds": {"type": "integer", "description": "Timeout in seconds (0 = no auto-lock)"}}, "required": ["seconds"]},
            credential_set_timeout, "utility"),

        _make_tool("credential_lock",
            "Lock the vault immediately. Clears decrypted credentials from memory.",
            {"type": "object", "properties": {}, "required": []},
            credential_lock, "utility"),

        _make_tool("credential_save",
            "Save a username/password for a website to the encrypted vault. Optionally categorize and add notes.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name (e.g., 'youtube', 'gmail', 'github')"},
                "username": {"type": "string", "description": "Username or email"},
                "password": {"type": "string", "description": "Password to store"},
                "url": {"type": "string", "description": "Optional login page URL"},
                "category": {"type": "string", "description": "Optional: work, personal, finance, social, other"},
                "notes": {"type": "string", "description": "Optional notes about this credential"},
            }, "required": ["master_password", "site", "username", "password"]},
            credential_save, "utility"),

        _make_tool("credential_save_generated",
            "Generate a strong random password AND save it for a site in one step. Best for new signups.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name"},
                "username": {"type": "string", "description": "Username or email"},
                "length": {"type": "integer", "description": "Password length (8-128, default 20)"},
                "include_symbols": {"type": "boolean", "description": "Include special characters (default true)"},
                "url": {"type": "string", "description": "Optional login page URL"},
                "category": {"type": "string", "description": "Optional category tag"},
            }, "required": ["master_password", "site", "username"]},
            credential_save_generated, "utility"),

        _make_tool("credential_get",
            "Retrieve saved username/password for a website from the encrypted vault.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name to look up"},
            }, "required": ["master_password", "site"]},
            credential_get, "utility"),

        _make_tool("credential_search",
            "Search saved credentials by site name or username keyword.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "query": {"type": "string", "description": "Keyword to search for"},
            }, "required": ["master_password", "query"]},
            credential_search, "utility"),

        _make_tool("credential_list",
            "List all saved sites with credentials. Optionally filter by category.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "category": {"type": "string", "description": "Optional: filter by category (work, personal, finance, social, other)"},
            }, "required": ["master_password"]},
            credential_list, "utility"),

        _make_tool("credential_delete",
            "Delete a saved credential by site name.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name to delete"},
            }, "required": ["master_password", "site"]},
            credential_delete, "utility"),

        _make_tool("credential_update",
            "Update an existing credential (username, password, URL, category, or notes). Leave fields blank to keep current.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name to update"},
                "username": {"type": "string", "description": "New username (blank to keep)"},
                "password": {"type": "string", "description": "New password (blank to keep)"},
                "url": {"type": "string", "description": "New login URL (blank to keep)"},
                "category": {"type": "string", "description": "New category (blank to keep)"},
                "notes": {"type": "string", "description": "New notes (blank to keep)"},
            }, "required": ["master_password", "site"]},
            credential_update, "utility"),

        _make_tool("credential_auto_login",
            "Open a website login page in the browser AND show saved credentials. Use when user says 'log in to <site>'.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name or URL to log into"},
            }, "required": ["master_password", "site"]},
            credential_auto_login, "utility"),

        _make_tool("credential_prompt_save",
            "Prompt to save credentials for a site. Use when user says 'save my password for <site>'.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "site": {"type": "string", "description": "Site name"},
                "username": {"type": "string", "description": "Optional username"},
                "password": {"type": "string", "description": "Optional password"},
            }, "required": ["master_password", "site"]},
            credential_prompt_save, "utility"),

        _make_tool("credential_health_report",
            "Generate a password health report: weak passwords, reused passwords, old credentials needing rotation.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
            }, "required": ["master_password"]},
            credential_health_report, "utility"),

        _make_tool("credential_vault_stats",
            "Show vault statistics: total sites, strength distribution, categories breakdown.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
            }, "required": ["master_password"]},
            credential_vault_stats, "utility"),

        _make_tool("credential_export_csv",
            "Export credential list as CSV (site, username, strength, category). Use for spreadsheets.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
            }, "required": ["master_password"]},
            credential_export_csv, "utility"),

        _make_tool("credential_import_csv",
            "Import credentials from CSV. Format header: Site, Username, Password, URL, Category.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "csv_data": {"type": "string", "description": "CSV content with header row"},
            }, "required": ["master_password", "csv_data"]},
            credential_import_csv, "utility"),

        _make_tool("credential_export",
            "Export all credentials as JSON (includes passwords). For personal backup only.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
            }, "required": ["master_password"]},
            credential_export, "utility"),

        _make_tool("credential_audit_log",
            "Show recent audit log: login attempts, saves, deletes, exports. No passwords in log.",
            {"type": "object", "properties": {
                "master_password": {"type": "string", "description": "Master vault password"},
                "lines": {"type": "integer", "description": "Number of recent log lines (default 20)"},
            }, "required": ["master_password"]},
            credential_audit_log, "utility"),

        _make_tool("credential_check_strength",
            "Check password strength without saving. Returns score (0-100) and improvement tips.",
            {"type": "object", "properties": {"password": {"type": "string", "description": "Password to evaluate"}}, "required": ["password"]},
            credential_check_strength, "utility"),

        _make_tool("credential_generate_password",
            "Generate a cryptographically secure random password with strength score. Does NOT save it.",
            {"type": "object", "properties": {
                "length": {"type": "integer", "description": "Password length (default 20)"},
                "include_symbols": {"type": "boolean", "description": "Include special characters (default true)"},
            }, "required": []},
            credential_generate_password, "utility"),
    ]
