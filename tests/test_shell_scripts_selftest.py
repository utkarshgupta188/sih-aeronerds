"""Meta-test: prove test_shell_scripts.py actually catches the bugs it claims.

A checker that cannot fail is worse than no checker, because it reports
"all checks passed" about a file it never really examined. This feeds it
deliberately broken scripts and asserts each one is reported.

    python tests/test_shell_scripts_selftest.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tests" / "test_shell_scripts.py"

# (filename, content, substring expected in the failure output)
CASES = [
    (
        "unterminated_heredoc.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\ncat <<EOF\nbody line\n",
        "unterminated heredoc",
    ),
    (
        "missing_fi.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nif [ -f x ]; then\n  echo a\n",
        "unclosed",
    ),
    (
        "stray_done.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nfor i in a; do\n  echo $i\ndone\ndone\n",
        "no matching opener",
    ),
    (
        "unbalanced_brace.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nfoo() {\n  echo hi\n",
        "unclosed",
    ),
    (
        "no_shebang.sh",
        "set -euo pipefail\necho ok\n",
        "shebang",
    ),
    (
        "no_set_e.sh",
        "#!/usr/bin/env bash\necho ok\n",
        "set -e",
    ),
    (
        "no_set_u.sh",
        "#!/usr/bin/env bash\nset -e\necho ok\n",
        "set -u",
    ),
    (
        "unguarded_rm.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nrm -rf /\n",
        "unguarded",
    ),
    (
        "unterminated_quote.sh",
        '#!/usr/bin/env bash\nset -euo pipefail\necho "never closed\n',
        "never closed",
    ),
]

# Constructs that are valid but tripped earlier versions of the scanner. These
# are regression guards, not defect seeds: if the checker flags any of them it
# has produced a false positive, which is worse than a missed defect because it
# trains you to ignore its output.
ACCEPT = [
    (
        "quote_at_eol.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\ndie \"message\"\n",
    ),
    (
        "multiline_string.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "if ! cmd -c \"\nimport sys\nprint(sys.argv)\n\"; then\n"
        "  die \"failed\"\nfi\n",
    ),
    (
        "heredoc_with_apostrophe.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\ncat <<'EOF'\n"
        "point DNS at the instance's Elastic IP\n{ not shell: syntax }\nEOF\n"
        "echo done\n",
    ),
    (
        "heredoc_unquoted.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\ncat <<EOF\nvalue is $HOME\nEOF\n",
    ),
    (
        "nesting.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'v="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'x=$(( 1 + 2 ))\n'
        'y="${v}/sub"\n'
        "echo \"$v $x $y\"\n",
    ),
    (
        "case_and_elif.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "for i in a b; do\n"
        '  case "$i" in\n'
        "    a) echo one ;;\n"
        "    b) echo two ;;\n"
        "  esac\n"
        "done\n"
        'if [ -n "$i" ]; then\n  echo set\n'
        'elif [ -z "$i" ]; then\n  echo empty\nelse\n  echo other\nfi\n',
    ),
    (
        "function_and_subshell.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'log() { printf "%s\\n" "$*"; }\n'
        "die() { log \"ERROR: $*\"; exit 1; }\n"
        "log ok\n",
    ),
    (
        "case_glob_arms.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "case \"$x\" in\n"
        "  *.*) ;;\n"
        "  1.2.3.4) die \"bare IP\" ;;\n"
        "  *) die \"bare\" ;;\n"
        "esac\n"
        "echo ok\n",
    ),
]


def run_checker(deploy_dir: Path) -> tuple[int, str]:
    """Run the checker against a deploy/ directory holding the bad scripts."""
    # The checker resolves paths relative to its own location, so point it at a
    # copy of the real tree with deploy/ replaced by the fixture.
    import shutil

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        root.mkdir()
        shutil.copytree(ROOT / "tests", root / "tests")
        shutil.copytree(ROOT / "backend", root / "backend")
        (root / "deploy").mkdir()
        for item in deploy_dir.iterdir():
            (root / "deploy" / item.name).write_bytes(item.read_bytes())

        proc = subprocess.run(
            [sys.executable, str(root / "tests" / "test_shell_scripts.py")],
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    # A correct script must pass.
    with tempfile.TemporaryDirectory() as good_dir:
        good = Path(good_dir) / "ok.sh"
        good.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            'log() { printf "%s\\n" "$*"; }\n'
            "\n"
            "cat <<'EOF'\n"
            "text with { braces } and ( parens )\n"
            "EOF\n"
            "\n"
            "for i in 1 2; do\n"
            '  if [ "$i" = 1 ]; then\n'
            "    log one\n"
            "  else\n"
            "    log other\n"
            "  fi\n"
            "done\n",
            encoding="utf-8",
            # newline="" is required: on Windows, text mode otherwise converts
            # \n to \r\n and the fixture would trip the very check we are
            # trying to exercise.
            newline="",
        )
        code, out = run_checker(Path(good_dir))
        if code != 0:
            print("self-test FAILED: a valid script was rejected")
            print(out)
            return 1
        print("ok  valid script accepted")

    # CRLF needs a separate run because it is a byte-level check.
    with tempfile.TemporaryDirectory() as crlf_dir:
        p = Path(crlf_dir) / "crlf.sh"
        p.write_bytes(b"#!/usr/bin/env bash\nset -euo pipefail\necho ok\n".replace(b"\n", b"\r\n"))
        code, out = run_checker(Path(crlf_dir))
        if code == 0 or "CRLF" not in out:
            print("self-test FAILED: CRLF not detected")
            print(out)
            return 1
        print("ok  CRLF detected")

    for name, body, expect in CASES:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / name).write_text(body, encoding="utf-8", newline="")
            code, out = run_checker(Path(d))
            detected = code != 0
            if expect and expect not in out:
                detected = False
            if not detected:
                print(f"self-test FAILED: {name} not reported")
                print(out)
                return 1
            print(f"ok  {name} detected")

    for name, body in ACCEPT:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / name).write_text(body, encoding="utf-8", newline="")
            code, out = run_checker(Path(d))
            if code != 0:
                print(f"self-test FAILED: {name} is valid but was rejected")
                print(out)
                return 1
            print(f"ok  {name} accepted (no false positive)")

    print(
        "\nchecker self-test passed: "
        f"{len(CASES)} defects detected, {len(ACCEPT)} valid scripts accepted"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
