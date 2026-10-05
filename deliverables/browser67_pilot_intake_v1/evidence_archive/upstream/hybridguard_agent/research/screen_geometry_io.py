"""Small evidence reader: physical lines, explicit errors, no inferred identities."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import zlib


class EvidenceError(ValueError):
    pass


@dataclass
class ReadResult:
    records: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def issue(path, kind, line=None, detail=None, **extra):
    return {"path": str(Path(path).absolute()), "line": line, "kind": kind,
            "detail": str(detail) if detail is not None else None, **extra}


def reference(path, line=None):
    # Keep historical in-repository references unchanged; allow external roots.
    path = Path(path).absolute()
    root = Path(__file__).resolve().parents[2]
    try: name = str(path.relative_to(root))
    except ValueError: name = str(path)
    return name if line is None else name + ":" + str(line)


def _loads(text):
    def constant(value): raise ValueError("non-finite JSON constant " + value)
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result): raise ValueError("non-finite JSON number " + value)
        return result
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON object key " + key)
            result[key] = value
        return result
    return json.loads(text, parse_constant=constant, parse_float=finite_float, object_pairs_hook=pairs)


def read_jsonl(path):
    """Recover independent good lines. A broken stream stops at known evidence.

    Decode each physical line separately so a bad UTF-8 line cannot swallow the
    next one. Incremental gzip preserves already emitted lines on truncation.
    No recovery past a decompressor error is claimed.
    """
    path = Path(path); result = ReadResult(); pending = b""; number = 0
    def consume(data, final=False):
        nonlocal pending, number
        pending += data
        while b"\n" in pending or (final and pending):
            terminated = b"\n" in pending
            if terminated: line, pending = pending.split(b"\n", 1)
            else: line, pending = pending, b""
            number += 1
            if not line.strip():
                result.errors.append(issue(path, "BLANK_LINE", number)); continue
            try: value = _loads(line.decode("utf-8"))
            except UnicodeDecodeError as error:
                result.errors.append(issue(path, "INVALID_ENCODING", number, error)); continue
            except (ValueError, RecursionError) as error:
                result.errors.append(issue(path, "INVALID_JSON" if terminated else "INVALID_UNTERMINATED_JSON", number, error)); continue
            if not isinstance(value, dict):
                result.errors.append(issue(path, "NON_OBJECT_RECORD", number, type(value).__name__)); continue
            result.records.append({"value": value, "path": str(path.absolute()), "line": number,
                                   "reference": reference(path, number)})
    try:
        with path.open("rb") as source:
            if path.suffix != ".gz":
                for chunk in iter(lambda: source.read(8192), b""): consume(chunk)
                consume(b"", True)
            else:
                inflater = zlib.decompressobj(31)
                try:
                    for chunk in iter(lambda: source.read(4096), b""):
                        # Concatenated gzip members are accepted without renumbering.
                        while chunk:
                            if inflater.eof: inflater = zlib.decompressobj(31)
                            consume(inflater.decompress(chunk))
                            chunk = inflater.unused_data
                    if not inflater.eof:
                        if pending:
                            result.errors.append(issue(path, "UNREADABLE_PARTIAL_LINE", number + 1, "gzip stream ended before its footer"))
                        result.errors.append(issue(path, "GZIP_TRUNCATED", number + 1, "subsequent planned members are not recovered"))
                    else: consume(b"", True)
                except zlib.error as error:
                    result.errors.append(issue(path, "GZIP_ERROR", number + 1, error, unread_remainder=True))
    except OSError as error:
        result.errors.append(issue(path, "FILE_NOT_FOUND" if isinstance(error, FileNotFoundError) else "FILE_UNREADABLE", number + 1 if number else None, error))
    return result


def read_object(path, *, required=False):
    path = Path(path); errors = []; value = {}
    try:
        candidate = _loads(path.read_bytes().decode("utf-8"))
        if not isinstance(candidate, dict): raise ValueError("JSON object required")
        value = candidate
    except (OSError, ValueError, RecursionError) as error:
        errors.append(issue(path, "EVIDENCE_FILE_INVALID", None, error))
    if required and errors: raise EvidenceError(json.dumps(errors, ensure_ascii=False))
    return value, errors


def identifier(value): return isinstance(value, str) and bool(value.strip())


def index_records(read_result, key):
    """Keep all duplicates. Never choose an arbitrary member of a conflict."""
    indexed = {}
    for located in read_result.records:
        value = located["value"].get(key)
        if not identifier(value):
            read_result.errors.append(issue(located["path"], "INVALID_IDENTIFIER", located["line"], key))
            continue
        indexed.setdefault(value, []).append(located)
    for value, group in indexed.items():
        if len(group) > 1:
            read_result.errors.append(issue(group[0]["path"], "DUPLICATE_IDENTIFIER", None, key,
                                            identifier=value, lines=[x["line"] for x in group]))
    return indexed


def archive_path(run):
    plain = Path(run) / "backend/raw_expanded_payloads.jsonl"
    zipped = plain.with_suffix(plain.suffix + ".gz")
    return plain if plain.exists() or not zipped.exists() else zipped
