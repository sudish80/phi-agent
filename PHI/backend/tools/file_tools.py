"""File tools — search, hash, diff, compress, decompress, type detection."""

import os
import hashlib
import difflib
import zipfile
import tarfile
import mimetypes
import logging

logger = logging.getLogger(__name__)


def file_search(root_dir: str, pattern: str = "*", max_results: int = 50) -> str:
    import fnmatch
    if not os.path.isdir(root_dir):
        return f"Error: directory not found: {root_dir}"
    matches = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if fnmatch.fnmatch(f, pattern):
                matches.append(os.path.join(dirpath, f))
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    if not matches:
        return f"No files matching '{pattern}' in {root_dir}"
    lines = [f"Found {len(matches)} file(s):"] + [m for m in matches]
    return "\n".join(lines)


def file_hash(file_path: str, algorithm: str = "sha256") -> str:
    if not os.path.isfile(file_path):
        return f"Error: file not found: {file_path}"
    algo = algorithm.lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        return f"Error: unsupported algorithm: {algorithm}. Use md5, sha1, sha256, sha512"
    h = hashlib.new(algo)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"{algo.upper()}: {h.hexdigest()}"


def file_diff(file_a: str, file_b: str, context_lines: int = 3) -> str:
    if not os.path.isfile(file_a):
        return f"Error: file not found: {file_a}"
    if not os.path.isfile(file_b):
        return f"Error: file not found: {file_b}"
    try:
        with open(file_a) as f:
            lines_a = f.readlines()
        with open(file_b) as f:
            lines_b = f.readlines()
    except Exception as e:
        return f"Error reading files: {e}"
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=file_a, tofile=file_b, n=context_lines)
    result = "".join(diff)
    return result if result else "Files are identical"


def file_compress(paths: list, output_path: str = "", format: str = "zip") -> str:
    import os
    valid = [p for p in paths if os.path.exists(p)]
    if not valid:
        return "Error: no valid paths to compress"
    out = output_path or (f"archive.{format}")
    fmt = format.lower()
    try:
        if fmt == "zip":
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in valid:
                    if os.path.isdir(p):
                        for dirpath, _, files in os.walk(p):
                            for f in files:
                                fp = os.path.join(dirpath, f)
                                zf.write(fp, os.path.relpath(fp, os.path.dirname(p)))
                    else:
                        zf.write(p, os.path.basename(p))
            return f"Created {out} with {len(valid)} items ({fmt})"
        elif fmt == "tar":
            mode = "w:gz" if out.endswith(".gz") else "w"
            with tarfile.open(out, mode) as tf:
                for p in valid:
                    tf.add(p)
            return f"Created {out} with {len(valid)} items ({fmt})"
        else:
            return f"Error: unsupported format: {fmt}. Use zip or tar"
    except Exception as e:
        return f"Error compressing: {e}"


def file_decompress(archive_path: str, output_dir: str = "") -> str:
    if not os.path.isfile(archive_path):
        return f"Error: archive not found: {archive_path}"
    out = output_dir or os.path.splitext(os.path.basename(archive_path))[0]
    os.makedirs(out, exist_ok=True)
    try:
        if archive_path.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(out)
            return f"Extracted {archive_path} to {out}"
        elif archive_path.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2")):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(out)
            return f"Extracted {archive_path} to {out}"
        else:
            return "Error: unsupported archive format. Use .zip or .tar/.tar.gz"
    except Exception as e:
        return f"Error extracting: {e}"


def file_type_detect(file_path: str) -> str:
    if not os.path.isfile(file_path):
        return f"Error: file not found: {file_path}"
    mime_type, _ = mimetypes.guess_type(file_path)
    size = os.path.getsize(file_path)
    ext = os.path.splitext(file_path)[1].lower() or "none"
    size_str = f"{size} bytes"
    if size > 1024**3:
        size_str = f"{size/1024**3:.1f} GB"
    elif size > 1024**2:
        size_str = f"{size/1024**2:.1f} MB"
    elif size > 1024:
        size_str = f"{size/1024:.1f} KB"
    return f"Extension: {ext}\nMIME: {mime_type or 'unknown'}\nSize: {size_str}"
