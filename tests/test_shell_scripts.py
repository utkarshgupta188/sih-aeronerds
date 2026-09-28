"""Structural checks for the deployment shell scripts.

Neither `bash` nor WSL is available on this Windows dev box, so the scripts
cannot be passed through `bash -n` here. This is not a substitute. It catches
the mistakes that actually happen when shell is edited by hand:

  * Windows CRLF endings, which silently break the shebang on Linux
  * a missing ``set -e`` / ``set -u``, so a failed step does not halt a deploy
  * unbalanced braces, parens, or quotes
  * an unterminated heredoc
  * an unclosed ``if`` / ``for`` / ``while`` / ``case`` / function
  * a systemd unit that would run as root or has no writable path

The scanner below understands single quotes, double quotes, backslash escapes,
line continuations, command substitution, parameter expansion and heredocs, so
text inside a quoted string or a heredoc body is never mistaken for shell
syntax. That matters here because ``deploy.sh`` writes nginx configuration to
stdout inside a heredoc, full of braces and quotes that are not shell syntax.

The authoritative check remains ``bash -n`` on the target host.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "deploy").glob("*.sh"))
UNIT = ROOT / "deploy" / "aeronerds.service"
INSTALL = ROOT / "deploy" / "install.sh"

failures: list[str] = []
checks = 0


def check(ok: bool, message: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(message)


# --------------------------------------------------------------------------
# scanning


@dataclass
class Code:
    """A script reduced to shell syntax only.

    Characters inside strings, comments and heredoc bodies are dropped, so what
    remains can be scanned for delimiters and keywords without tripping over
    prose. Nesting is preserved because ``$(`` and ``${`` are kept as-is; their
    own closers are balanced by the scanner.
    """

    text: str = ""
    line_of: list[int] = field(default_factory=list)
    #: (line, delimiter) pairs for a quote or backtick still open at EOF.
    #: Bash lets a quoted string span lines, so a quote at end-of-line is only an
    #: error if it is still open when the script ends.
    unterminated: list[tuple[int, str]] = field(default_factory=list)

    def line_at(self, index: int) -> int:
        return self.line_of[index] if index < len(self.line_of) else -1


HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def skip_nested(raw: str, j: int, opener: str, closer: str) -> int:
    """Return the index just past the matching ``closer`` of a nested construct.

    For ``$(...)``, ``${...}`` and backticks, which nest, so depth is tracked
    rather than stopping at the first closer. ``$((...))`` also nests, and is
    handled by the same routine since its delimiters are ``(`` and ``)``.

    Returns ``len(raw)`` when the construct is never closed.
    """
    depth = 1
    n = len(raw)
    while j < n:
        if raw[j] == "\\":
            j += 2
            continue
        if raw.startswith(opener, j):
            depth += 1
            j += len(opener)
            continue
        if raw.startswith(closer, j):
            depth -= 1
            j += len(closer)
            if depth == 0:
                return j
            continue
        j += 1
    return n


def find_terminator(raw: str, j: int, delim: str, respect_backslash: bool) -> int:
    """Return the index just past the next unescaped ``delim``, or -1.

    Unlike :func:`skip_nested` this does not count nesting: a double quote or a
    backtick is closed by the first unescaped occurrence, and a ``"`` inside a
    string is not an opener of anything.

    When scanning a double-quoted string, ``$(...)`` and backtick substitutions
    are skipped whole. Bash balances quotes inside a substitution independently
    of the surrounding string, so ``"$(dirname "${BASH_SOURCE[0]}")"`` has
    three quote pairs, not two; without this the scan stopped at the first
    quote inside ``$(...)`` and reported the rest of the line as string body.

    -1 rather than ``len(raw)`` matters: a string closed by the final character
    of the line returns ``len(raw)``, which is indistinguishable from "not
    found" and would report every ``die "message"`` line as unterminated.
    """
    n = len(raw)
    in_dquote = respect_backslash  # only double-quoted strings allow expansion
    while j < n:
        c = raw[j]
        if in_dquote and c == "\\":
            j += 2
            continue
        if in_dquote and raw.startswith("$(", j):
            j = skip_nested(raw, j + 2, "(", ")")
            continue
        if in_dquote and raw.startswith("${", j):
            j = skip_nested(raw, j + 2, "{", "}")
            continue
        if in_dquote and c == "`":
            j = skip_nested(raw, j + 1, "`", "`")
            continue
        if c == delim:
            return j + 1
        j += 1
    return -1


#: After one of these, a word followed by ')' is a case-arm pattern delimiter
#: rather than a closing paren: "case $x in", "a) ...", ";;", "esac)".
_ARM_START = re.compile(r"(?:^|;;|;&|&&|\|\||\bin)\s+$")


def _is_case_arm_delim(raw: str, j: int) -> bool:
    """True when the ')' at ``j`` terminates a case-arm pattern.

    ``case $x in a) ... ;; esac)`` contains two ')' characters that are not
    closing parens. Treating them as parens made the balance check report
    "closing ')' with no opener" on valid code.
    """
    if j == 0:
        return False
    prev = raw[j - 1]
    if not (prev.isalnum() or prev in "*?[]\"'"):
        return False
    # walk back over the pattern to see whether it starts a command
    k = j
    while k > 0 and (raw[k - 1].isalnum() or raw[k - 1] in "*?[]\"'_-"):
        k -= 1
    return _ARM_START.match(raw[:k] + " ") is not None


def scan_line(
    raw: str, line: int, out: Code, pending: list[str], carry: str | None = None
) -> str | None:
    """Append the shell syntax of one line to ``out``, dropping strings/comments.

    ``carry`` is the delimiter of a string left open by the previous line. Bash
    allows a quoted string to span lines, so the string is resumed here and the
    remainder of the line scanned as normal.

    Returns the delimiter still open at end of line, or None.
    """
    j = 0
    n = len(raw)

    if carry is not None:
        end = find_terminator(raw, 0, carry, respect_backslash=carry == '"')
        if end == -1:
            return carry  # still open
        j = end

    while j < n:
        ch = raw[j]

        # comment: '#' at the start of a word
        if ch == "#" and (j == 0 or raw[j - 1] in " \t"):
            return

        # a backslash line continuation joins the next physical line
        if ch == "\\" and j + 1 >= n:
            return None

        if ch == "\\":
            nxt = raw[j + 1]
            if nxt in "{}()$`\"'":
                out.text += nxt
                out.line_of.append(line)
            j += 2
            continue

        # A heredoc must be recognised before the quote handlers, because
        # <<'EOF' contains a quote character. Checking quotes first consumed the
        # delimiter as an opening string, so the body was never skipped and was
        # then scanned as shell code.
        m = HEREDOC_START.match(raw, j)
        if m:
            pending.append(m.group(2))
            j = m.end()
            continue

        if ch in "'\"":
            end = find_terminator(raw, j + 1, ch, respect_backslash=ch == '"')
            if end == -1:
                return ch  # the string continues onto the next line
            j = end
            continue

        if ch == "`":
            end = find_terminator(raw, j + 1, "`", respect_backslash=False)
            if end == -1:
                return "`"
            j = end
            continue

        if raw.startswith("$((", j):
            # Start one char in so the syntactic '(' is counted as the opener.
            # $(( expr )) then closes as a matched pair, and an inner '(' in
            # "$(( (a + b) * c ))" raises the depth rather than ending it.
            j = skip_nested(raw, j + 2, "(", ")")
            out.text += "EXP"
            out.line_of.append(line)
            continue

        if raw.startswith("$(", j):
            j = skip_nested(raw, j + 2, "(", ")")
            out.text += "SUB"
            out.line_of.append(line)
            continue

        if raw.startswith("${", j):
            j = skip_nested(raw, j + 2, "{", "}")
            out.text += "EXP"
            out.line_of.append(line)
            continue

        if ch == ")" and _is_case_arm_delim(raw, j):
            j += 1
            continue

        out.text += ch
        out.line_of.append(line)
        j += 1


def scan(src: str, label: str = "?") -> Code:
    global checks

    out = Code()
    lines = src.splitlines()
    n = len(lines)

    carry: str | None = None
    idx = 0
    # An explicit while loop, not enumerate: skipping a heredoc body requires
    # advancing the cursor, and rebinding the loop variable of a for loop does
    # not survive the next iteration. With a for loop the body was rescanned as
    # shell code, so the nginx config printed by install.sh -- full of braces,
    # quotes and an apostrophe in "instance's" -- produced phantom errors.
    while idx < n:
        raw = lines[idx]
        line = idx + 1
        pending: list[str] = []

        carry = scan_line(raw, line, out, pending, carry)
        out.text += "\n"
        out.line_of.append(line)
        idx += 1

        # A heredoc body is not shell syntax and must not reach the balance or
        # keyword checks, so consume it verbatim and blank it out of the text.
        for tag in pending:
            body = idx
            while body < n and lines[body].strip() != tag:
                body += 1
            if body >= n:
                failures.append(f"{label}:{line}: unterminated heredoc <<{tag}")
                checks += 1
                break
            for skipped in range(idx, body + 1):
                out.text += "\n"
                out.line_of.append(skipped + 1)
            idx = body + 1
            carry = None

    if carry is not None:
        out.unterminated.append((n, carry))

    return out


# --------------------------------------------------------------------------
# balance checks on the scanned code

OPEN_CLOSE = {"(": ")", "{": "}", "[": "]"}


def balance(code: Code, label: str = "?") -> None:
    global checks
    stack: list[tuple[str, int]] = []
    # a '}' that closes a ${..} was already consumed as EXP, so a bare '}' here
    # belongs to a function or a block.
    for idx, ch in enumerate(code.text):
        if ch in OPEN_CLOSE:
            stack.append((ch, code.line_at(idx)))
        elif ch in OPEN_CLOSE.values():
            ln = code.line_at(idx)
            if not stack:
                failures.append(f"{label}:{ln}: closing '{ch}' with no opener")
                checks += 1
                continue
            opener, _ = stack.pop()
            if OPEN_CLOSE[opener] != ch:
                failures.append(f"{label}:{ln}: '{ch}' closes '{opener}'")
                checks += 1
    for opener, ln in stack:
        if opener == "[":
            continue  # [ ... ] in a test is often split across lines
        failures.append(f"{label}:{ln}: unclosed '{opener}'")
        checks += 1


# --------------------------------------------------------------------------
# block keywords, evaluated on the scanned code

BLOCK_OPENERS = {"if", "for", "while", "until", "case", "select"}
#: Which closer legitimately ends which opener. Anything else is a real bug,
#: e.g. a `for` closed by `fi`.
BLOCK_PARTNER = {
    "if": "fi",
    "for": "done",
    "while": "done",
    "until": "done",
    "select": "done",
    "case": "esac",
}
BLOCK_CLOSERS = set(BLOCK_PARTNER.values())
#: A closer must be the whole command, not merely the last word of one.
#: "echo done" is a perfectly good command and must not close a loop.
BARE_CLOSER = re.compile(
    r"^(?:[;&|()]|\s)*(fi|done|esac)\s*(?:;|&&|\|\||\)|&)?\s*$"
)
FUNC_DEF = re.compile(r"^[\w.:-]+\s*\(\)\s*\{?\s*$|^function\s+[\w.:-]+")


#: "a)", "* )", "?([a-z]*)", "esac" style arms. An arm is not a block opener or
#: closer, so it must be recognised before the keyword checks.
CASE_ARM = re.compile(
    r"^[\w.*?\[\]!@|-]+\)\s*(;;|;&|&&|&)?\s*$"
)


def blocks(code: Code, label: str = "?") -> None:
    global checks
    depth: list[tuple[str, int]] = []
    for offset, line in enumerate(code.text.split("\n")[:-1]):
        stripped = line.strip()
        if not stripped:
            continue
        tokens = re.findall(r"[\w.:-]+|[{}()]", stripped)
        if not tokens:
            continue

        # a case arm: "pattern)" or "* )" or "pattern) cmd ;;"
        if CASE_ARM.match(stripped):
            continue

        # a case arm continued on the next line, ending in ";;"
        if stripped.endswith(";;"):
            continue

        first = tokens[0]
        last = tokens[-1]

        # one-line function body: "foo() { ... }"
        if FUNC_DEF.match(stripped) and stripped.endswith("}"):
            continue

        # scan() appends exactly one "\n" per source line, so the split index
        # is the source line number. Using text.index() instead would find the
        # first identical line and report the wrong location.
        lineno = offset + 1

        if FUNC_DEF.match(stripped):
            depth.append(("function", lineno))
            continue

        if stripped == "}":
            if depth and depth[-1][0] == "function":
                depth.pop()
            else:
                failures.append(f"{label}:{lineno}: '}}' with no open function")
                checks += 1
            continue

        if first in BLOCK_OPENERS:
            # "if cmd; then" and "for x in y; do" still open a block that is
            # closed by the later fi/done, so push either way. "elif" is not
            # an opener: it continues an existing if.
            depth.append((first, lineno))
            continue

        if first == "elif":
            if not depth or depth[-1][0] != "if":
                failures.append(f"{label}:{lineno}: 'elif' outside an 'if' block")
                checks += 1
            continue

        closer = BARE_CLOSER.match(stripped)
        if closer:
            word = closer.group(1)
            if not depth:
                failures.append(f"{label}:{lineno}: '{word}' with no matching opener")
                checks += 1
                continue
            opener, opened_at = depth[-1]
            if BLOCK_PARTNER.get(opener) != word:
                failures.append(
                    f"{label}:{lineno}: '{word}' cannot close a '{opener}' "
                    f"opened at line {opened_at}"
                )
                checks += 1
            depth.pop()
            continue

    for kind, lineno in depth:
        failures.append(f"{label}:{lineno}: unclosed {kind}")
        checks += 1


# --------------------------------------------------------------------------

for path in SCRIPTS:
    rel = path.relative_to(ROOT).as_posix()
    raw = path.read_bytes()

    check(b"\r\n" not in raw, f"{rel}: CRLF line endings break the shebang on Linux")

    text = raw.decode("utf-8")
    check(text.startswith("#!/usr/bin/env bash"), f"{rel}: missing bash shebang")
    check(
        re.search(r"^set -euo pipefail|^set -eu\b|^set -e\b", text, re.M) is not None,
        f"{rel}: needs 'set -e' so a failed step halts the deploy",
    )
    check(
        re.search(r"set -[a-z]*u", text) is not None,
        f"{rel}: needs 'set -u' so an unset variable is an error",
    )

    code = scan(text, rel)
    balance(code, rel)
    blocks(code, rel)

    for ln, delim in code.unterminated:
        failures.append(f"{rel}:{ln}: {delim} is never closed")
        checks += 1

    if path.name in {"install.sh", "deploy.sh"}:
        check(
            "id -u" in text,
            f"{rel}: must verify it is root before writing to /opt and /etc",
        )

    # Any script can destroy data, so the rm guard applies to all of them.
    for m in re.finditer(r"^\s*rm -rf?\s+(.+)$", text, re.M):
        target = m.group(1).strip()
        guarded = any(
            g in target
            for g in ("$", '"', "app.prev", "/tmp/", "$APP_ROOT/", "$DATA_DIR")
        )
        check(guarded, f"{rel}: unguarded 'rm -rf {target}'")

    # the native scripts must reference paths install.sh actually creates,
    # otherwise the service points at a directory that was never made
    if path.name in {"install.sh", "deploy.sh"}:
        for literal in set(re.findall(r"\"(/opt/aeronerds/[A-Za-z0-9_./-]+)\"", text)):
            top = literal.split("/")[3]
            check(
                top in {"app", "venv", "app.prev"},
                f"{rel}: references {literal}, which install.sh does not create",
            )

# ------------------------------------------------------------- systemd unit ---
if UNIT.exists():
    unit = UNIT.read_text(encoding="utf-8")
    for section in ("[Unit]", "[Service]", "[Install]"):
        check(section in unit, f"aeronerds.service: missing {section}")
    check("ExecStart=" in unit, "aeronerds.service: no ExecStart")
    check(
        re.search(r"^User=\S+", unit, re.M) is not None,
        "aeronerds.service: must set User, not run as root",
    )
    check(
        "multi-user.target" in unit,
        "aeronerds.service: not enabled at boot",
    )
    check(
        "ProtectSystem=strict" in unit,
        "aeronerds.service: expected ProtectSystem=strict",
    )
    check(
        len(re.findall(r"^ReadWritePaths=", unit, re.M)) == 1,
        "aeronerds.service: needs exactly one ReadWritePaths for the auth database",
    )
    check(
        "WantedBy=multi-user.target" in unit,
        "aeronerds.service: missing [Install] WantedBy",
    )

    # the paths in the unit must match what install.sh creates
    install_text = INSTALL.read_text(encoding="utf-8") if INSTALL.exists() else ""
    for literal in re.findall(r"(?:WorkingDirectory|ExecStart|EnvironmentFile)=(\S+)", unit):
        if not literal.startswith(("/opt/aeronerds", "/etc/aeronerds")):
            continue
        root = literal.split("/")[1:4]
        expected = "/" + "/".join(root)
        check(
            expected in install_text,
            f"aeronerds.service: {literal} -> install.sh never creates {expected}",
        )

print(f"ran {checks} structural checks across {len(SCRIPTS)} scripts")
if failures:
    print(f"\n{len(failures)} FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all shell-script structure checks passed")
