#!/usr/bin/env python3
"""
preporca.py — prepare ORCA job folders from XYZ files.

Author:  Aris V. Rubio
Date  :  July 2026
Target:  ORCA 6.1.1 compound scripts

- Scans cwd for .xyz files, makes one job folder per xyz (or works in place
  when there is a single xyz).
- Guided wizard with alias-based menu keys; quick-pick at the first prompt
  accepts a known alias to skip the wizard.
- '?' shows a flat grouped menu of all aliases.
- CLI flags allow batch / non-interactive invocation.
- Copies the chosen .cmp into each folder, rewrites molecule/charge/multi.
- Detects and replaces Constraints and Monitor_Internals blocks cleanly.
- Writes a `<base>.inp` containing `%Compound "<template>.cmp"`.
- Prints a summary table of method/basis/param/solv per step.
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Template directory resolution
# ---------------------------------------------------------------------------
STYLES = ("native", "libxc")
DEFAULT_STYLE = "native"


def _resolve_orca_dir() -> Path:
    """Locate the template tree. In order: $ORCA_TEMPLATES, then the script's
    own directory (the repo layout, where preporca.py sits beside native/ and
    libxc/), then a few per-system default locations. Whichever path contains a
    native/ or libxc/ subdir wins."""
    env = os.environ.get("ORCA_TEMPLATES")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
    # Repo layout: preporca.py shipped alongside the native/ and libxc/ trees.
    here = Path(__file__).resolve().parent
    if any((here / s).is_dir() for s in STYLES):
        return here
    for cand in [
        Path.home() / "project-houk" / "Scripts" / "orca",           # Hoffman2
        Path.home() / "bin" / "orca",                                # Local + Expanse
        Path.home() / "Calculations" / "test" / "orca_jobs" / "latest",  # dev
    ]:
        if cand.is_dir() and any((cand / s).is_dir() for s in STYLES):
            return cand
        # Backward compatibility: pre-split layout with .cmp files at the root.
        if cand.is_dir() and any(cand.glob("*.cmp")):
            return cand
    # Last-resort fallback for first-time install
    return Path.home() / "bin" / "orca"


ORCA_DIR = _resolve_orca_dir()

# ---------------------------------------------------------------------------
# Canonical alias table (alias -> relative path under ORCA_DIR)
# ---------------------------------------------------------------------------
ALIASES: Dict[str, str] = {
    "opt":             "orca.01.opt.cmp",
    "opt-sp":          "orca.02.opt-sp.cmp",
    "opt-wfs":         "orca.03.opt-WFS-reopt-sp.cmp",
    "ts":              "orca.04.ts.cmp",
    "ts-sp":           "orca.05.ts-sp.cmp",
    "irc":             "orca.06.IRC.cmp",
    "sp":              "orca.07.sp.cmp",
    "sp-dlpno":        "orca.08.sp-dlpno.cmp",
    "ts2-xtb":         "TS/orca.01.co-ts.xtb.cmp",
    "ts2-dft":         "TS/orca.01.co-ts.dft.cmp",
    "ts2-sp-xtb":      "TS/orca.02.co-ts-sp.xtb.cmp",
    "ts2-sp-dft":      "TS/orca.02.co-ts-sp.dft.cmp",
    "ts2-irc-xtb":     "TS/orca.03.co-ts-sp-IRC.xtb.cmp",
    "ts2-irc-dft":     "TS/orca.03.co-ts-sp-IRC.dft.cmp",
    "ts2-wfs-xtb":     "TS/orca.04.co-ts-WFS-reopt-sp.xtb.cmp",
    "ts2-wfs-dft":     "TS/orca.04.co-ts-WFS-reopt-sp.dft.cmp",
    "goat-opt":        "GOAT/orca.01.GOAT-opt.cmp",
    "goat-opt-sp":     "GOAT/orca.02.GOAT-opt-sp.cmp",
    "goat-ts2-xtb":    "GOAT/orca.03.GOAT-co-ts.xtb.cmp",
    "goat-ts2-dft":    "GOAT/orca.03.GOAT-co-ts.dft.cmp",
    "goat-ts2-sp-xtb": "GOAT/orca.04.GOAT-co-ts-sp.xtb.cmp",
    "goat-ts2-sp-dft": "GOAT/orca.04.GOAT-co-ts-sp.dft.cmp",
    "opt-goat":        "GOAT/orca.05.opt-GOAT-reopt-sp.cmp",
    "ecd":             "orca.09.ecd.cmp",
    "freq-sp":         "orca.10.freq-sp.cmp",
}

DESCRIPTIONS: Dict[str, str] = {
    "opt":             "Opt + Freq",
    "opt-sp":          "+ HL-SP",
    "opt-wfs":         "UKS opt + WFS stability + reopt",
    "ts":              "TS opt + Freq",
    "ts-sp":           "TS + HL-SP",
    "ts2-xtb":         "constrained pre-opt (xTB) -> TS",
    "ts2-dft":         "constrained pre-opt (DFT) -> TS",
    "ts2-sp-xtb":      "ts2 + HL-SP (xTB pre-opt)",
    "ts2-sp-dft":      "ts2 + HL-SP (DFT pre-opt)",
    "ts2-irc-xtb":     "ts2 + HL-SP + IRC (xTB)",
    "ts2-irc-dft":     "ts2 + HL-SP + IRC (DFT)",
    "ts2-wfs-xtb":     "ts2 + WFS + reopt + SP (xTB)",
    "ts2-wfs-dft":     "ts2 + WFS + reopt + SP (DFT)",
    "goat-opt":        "GOAT -> opt",
    "goat-opt-sp":     "GOAT -> opt + HL-SP",
    "goat-ts2-xtb":    "GOAT -> ts2 (xTB)",
    "goat-ts2-dft":    "GOAT -> ts2 (DFT)",
    "goat-ts2-sp-xtb": "GOAT -> ts2 + HL-SP (xTB)",
    "goat-ts2-sp-dft": "GOAT -> ts2 + HL-SP (DFT)",
    "opt-goat":        "opt -> GOAT -> reopt -> SP",
    "irc":             "IRC from existing TS",
    "sp":              "HL-SP only",
    "sp-dlpno":        "DLPNO-CCSD(T) single point",
    "ecd":             "TD-DFT ECD (rotatory strengths)",
    "freq-sp":         "Freq + HL-SP (no opt)",
}


# ---------------------------------------------------------------------------
# Full-menu printer (when user types '?')
# ---------------------------------------------------------------------------
def print_full_menu() -> None:
    print("\n=== All templates ===\n")

    print("Minimum opt:")
    for a in ("opt", "opt-sp", "opt-wfs"):
        print(f"   {a:<16} {DESCRIPTIONS[a]}")

    print("\nTS (have a guess):")
    for a in ("ts", "ts-sp"):
        print(f"   {a:<16} {DESCRIPTIONS[a]}")

    print("\nTS (constrained pre-opt):")
    for a in ("ts2-xtb", "ts2-dft", "ts2-sp-xtb", "ts2-sp-dft",
              "ts2-irc-xtb", "ts2-irc-dft", "ts2-wfs-xtb", "ts2-wfs-dft"):
        print(f"   {a:<16} {DESCRIPTIONS[a]}")

    print("\nGOAT (conformer search):")
    for a in ("goat-opt", "goat-opt-sp",
              "goat-ts2-xtb", "goat-ts2-dft",
              "goat-ts2-sp-xtb", "goat-ts2-sp-dft",
              "opt-goat"):
        print(f"   {a:<16} {DESCRIPTIONS[a]}")

    print("\nStandalone / single point:")
    for a in ("irc", "sp", "sp-dlpno", "freq-sp", "ecd"):
        print(f"   {a:<16} {DESCRIPTIONS[a]}")
    print()


# ---------------------------------------------------------------------------
# Wizard helpers
# ---------------------------------------------------------------------------
def _ask_choice(prompt: str, n: int) -> int:
    """Repeatedly prompt until user picks an integer in [1, n]. Accepts 'q' to quit."""
    while True:
        s = input(prompt).strip().lower()
        if s in ("q", "quit", "exit"):
            print("Aborted.")
            sys.exit(0)
        try:
            i = int(s)
            if 1 <= i <= n:
                return i
        except ValueError:
            pass
        print(f"  Please enter a number 1-{n} (or 'q' to quit).")


def _resolve_quickpick(token: str) -> Optional[str]:
    """
    Resolve a free-form quick-pick token at the first prompt.
      - exact alias match  -> return that alias
      - unique substring   -> return that alias
      - multiple matches   -> disambiguate via a follow-up menu
      - no match           -> return None
    """
    token = token.strip().lower()
    if not token:
        return None
    if token in ALIASES:
        return token
    matches = [a for a in ALIASES if token in a]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    print(f"\n'{token}' matches multiple aliases. Pick:")
    for i, a in enumerate(matches, 1):
        print(f"  {i}) {a:<16} {DESCRIPTIONS.get(a, '')}")
    pick = _ask_choice("> ", len(matches))
    return matches[pick - 1]


def _wizard_pick_style() -> str:
    """Ask the user which functional-style template tree to use."""
    print("\nWhich functional style?")
    print("  1) native      (! line keyword; ORCA built-in names, e.g. B3LYP D3BJ)")
    print("  2) libxc       (%method block; libxc functional names, e.g. hyb_gga_xc_wb97x_v)")
    pick = _ask_choice("> ", 2)
    return STYLES[pick - 1]


def _wizard_pick_alias() -> str:
    """Top-level wizard. Returns the chosen alias."""
    while True:
        print("\nWhat kind of ORCA job do you want to set up?")
        print("  1) Minimum optimization")
        print("  2) Transition state (TS)")
        print("  3) Conformer search (GOAT)")
        print("  4) IRC (post-TS)")
        print("  5) Single point only")
        print("  -- type alias directly to skip wizard, '?' for full menu, 'q' to quit")
        raw = input("> ").strip().lower()

        if raw in ("q", "quit", "exit"):
            print("Aborted.")
            sys.exit(0)
        if raw == "?":
            print_full_menu()
            continue
        if raw in ("1", "2", "3", "4", "5"):
            top = int(raw)
        else:
            # quick-pick / substring match
            if not raw:
                continue
            alias = _resolve_quickpick(raw)
            if alias is None:
                print(f"  '{raw}' is not a recognized alias and not 1-5.")
                continue
            return alias

        # ---- Branch 1: minimum opt ----
        if top == 1:
            print("\nAdd anything after opt?")
            print("  1) Just opt + Freq")
            print("  2) + HL-SP")
            print("  3) UKS opt + WFS + reopt + SP")
            sub = _ask_choice("> ", 3)
            return {1: "opt", 2: "opt-sp", 3: "opt-wfs"}[sub]

        # ---- Branch 2: TS ----
        if top == 2:
            print("\nNeed constrained pre-opt? (recommended unless geometry is clean TS-like)")
            print("  1) Yes")
            print("  2) No")
            need = _ask_choice("> ", 2)
            if need == 2:
                print("\nAdd HL-SP after TS?")
                print("  1) No")
                print("  2) Yes")
                sp = _ask_choice("> ", 2)
                return "ts" if sp == 1 else "ts-sp"
            # constrained pre-opt
            print("\nPre-opt engine?")
            print("  1) xTB")
            print("  2) DFT")
            engc = _ask_choice("> ", 2)
            eng = "xtb" if engc == 1 else "dft"
            print("\nWhat comes after the TS step?")
            print("  1) Just TS + Freq")
            print("  2) + HL-SP")
            print("  3) + HL-SP + IRC")
            print("  4) + WFS + reopt + SP")
            after = _ask_choice("> ", 4)
            base = {1: "ts2", 2: "ts2-sp", 3: "ts2-irc", 4: "ts2-wfs"}[after]
            return f"{base}-{eng}"

        # ---- Branch 3: GOAT ----
        if top == 3:
            print("\nWhat comes after GOAT?")
            print("  1) opt + Freq")
            print("  2) opt + Freq + HL-SP")
            print("  3) constrained pre-opt -> TS")
            print("  4) constrained pre-opt -> TS + HL-SP")
            print("  5) (different order) opt -> GOAT -> reopt -> SP")
            sub = _ask_choice("> ", 5)
            if sub == 1:
                return "goat-opt"
            if sub == 2:
                return "goat-opt-sp"
            if sub == 5:
                return "opt-goat"
            # 3 or 4: pre-opt engine needed
            print("\nPre-opt engine?")
            print("  1) xTB")
            print("  2) DFT")
            engc = _ask_choice("> ", 2)
            eng = "xtb" if engc == 1 else "dft"
            base = "goat-ts2" if sub == 3 else "goat-ts2-sp"
            return f"{base}-{eng}"

        # ---- Branch 4: IRC ----
        if top == 4:
            return "irc"

        # ---- Branch 5: SP ----
        if top == 5:
            print("\nSingle-point method?")
            print("  1) DFT single point")
            print("  2) DLPNO-CCSD(T)")
            return "sp" if _ask_choice("> ", 2) == 1 else "sp-dlpno"


# ---------------------------------------------------------------------------
# Constraint / monitor helpers (shared by guided & CLI paths)
# ---------------------------------------------------------------------------
ATOM_COUNT = {"B": 2, "A": 3, "D": 4, "C": 1}
MON_COUNT  = {"B": 2, "A": 3, "D": 4}


def norm_kind(s: str, allowed) -> str:
    s = s.strip().upper()
    if s not in allowed:
        raise ValueError(f"unknown type '{s}' (allowed: {', '.join(allowed)})")
    return s


def _parse_constraint_string(spec: str, allowed: Dict[str, int],
                             default_extra: Optional[str] = "C") -> List[str]:
    """
    Parse a semicolon-separated constraint/monitor string, e.g.:
      "B 0 1; B 0 5; A 0 1 2"
    into ORCA-style "{B 0 1 C}" tokens.

    For monitors (default_extra=None), no trailing token is appended.
    """
    out: List[str] = []
    for raw in spec.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        toks = raw.split()
        kind = norm_kind(toks[0], allowed)
        atoms_needed = allowed[kind]
        if len(toks) - 1 < atoms_needed:
            raise ValueError(f"constraint '{raw}': need {atoms_needed} atom indices")
        atoms = toks[1:1 + atoms_needed]
        extras = toks[1 + atoms_needed:]
        if default_extra is not None and not extras:
            extras = [default_extra]
        body = [kind] + atoms + extras
        out.append("{" + " ".join(body) + "}")
    return out


def _guided_constraints(label: str, allowed: Dict[str, int],
                        with_extra: bool) -> List[str]:
    out: List[str] = []
    i = 1
    while True:
        kind = input(f"[{i}] Type ({'/'.join(allowed.keys())}, blank to finish): ").strip()
        if not kind:
            break
        try:
            kind = norm_kind(kind, allowed)
        except ValueError:
            print("⚠️  Invalid type; try again.")
            continue
        atoms = input(f"[{i}] Atom numbers (space-separated): ").split()
        if len(atoms) != allowed[kind]:
            print("⚠️  Atom count does not match type; skipping.")
            continue
        if with_extra:
            extra = input(f"[{i}] Extra tokens (default = C): ").strip() or "C"
            out.append("{" + " ".join([kind] + atoms + extra.split()) + "}")
        else:
            out.append("{" + " ".join([kind] + atoms) + "}")
        i += 1
    print(f"\nAdded {len(out)} {label}(s).\n")
    return out


# ---------------------------------------------------------------------------
# Header / block rewriters
# ---------------------------------------------------------------------------
def replace_header_vars(text, molecule_name, charge_val, multi_val):
    # alignment matches the standardized System block (`=` one space past `molecule`)
    text = re.sub(r'Variable\s+molecule\s*=.*?;',
                  f'Variable molecule = "{molecule_name}";', text)
    text = re.sub(r'Variable\s+charge\s*=.*?;',
                  f'Variable charge   = {charge_val};', text)
    text = re.sub(r'Variable\s+multi\s*=.*?;',
                  f'Variable multi    = {multi_val};', text)
    return text


def replace_block_all(text, block_name, lines):
    if not lines:
        return text
    pattern = re.compile(
        rf'^(\s*){block_name}\b\s*\n([\s\S]*?)^\1end\s*$',
        re.MULTILINE
    )
    def repl(match):
        indent = match.group(1)
        block  = [f"{indent}{block_name}"]
        for c in lines:
            block.append(f"{indent}  {c}")
        block.append(f"{indent}end")
        return "\n".join(block)
    new_text, n = re.subn(pattern, repl, text)
    tag = "⚠️  No" if n == 0 else f"🔄 Replaced {n}"
    print(f"{tag} {block_name} block(s).")
    return new_text


# ---------------------------------------------------------------------------
# Variable extraction
#
# Uses a single unambiguous regex with three named groups:
#   fam  — the variable family  (method | basis | param | solv | xtb | goat | IRC)
#   suf  — the job-step suffix  (opt, sp, seed, …)
#   val  — the quoted value
# ---------------------------------------------------------------------------
_VAR_RE = re.compile(
    r'^\s*Variable\s+'
    r'(?P<fam>solv|xtb|method|basis|param|goat|IRC)'   # longest prefix first
    r'(?:_(?P<suf>[A-Za-z0-9_]+))?'                              # optional _suffix
    r'\s*=\s*"(?P<val>[^"]*)"',
    re.MULTILINE,
)


def extract_vars(text: str) -> Dict[str, str]:
    """Return {variable_name: value} for all managed family variables."""
    out: Dict[str, str] = {}
    for m in _VAR_RE.finditer(text):
        fam = m.group("fam")
        suf = m.group("suf")
        val = m.group("val")
        key = f"{fam}_{suf}" if suf else fam
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# Summary logic
# ---------------------------------------------------------------------------
_STEP_ORDER = ["seed", "goat", "copt", "opt", "tsopt", "ts", "sp", "irc"]
_ROW_FAMILIES = ["method", "basis", "param", "solv"]


def _discover_steps(vars_: Dict[str, str]) -> List[str]:
    seen:  Set[str]  = set()
    steps: List[str] = []
    for key in vars_:
        if "_" not in key:
            continue
        fam = next(
            (f for f in ["solv", "method", "basis", "param"]
             if key.startswith(f + "_")),
            None,
        )
        if fam is None:
            continue
        suf = key[len(fam) + 1:]
        if suf and suf not in seen:
            seen.add(suf)
            steps.append(suf)
    ordered  = [s for s in _STEP_ORDER if s in seen]
    ordered += sorted(s for s in seen if s not in _STEP_ORDER)
    return ordered


def _build_row(vars_: Dict[str, str], step: str) -> str:
    parts = []
    for fam in _ROW_FAMILIES:
        val = vars_.get(f"{fam}_{step}", "").strip()
        if val:
            parts.append(val)
    return "  │  ".join(parts) if parts else "(no variables)"


def _extract_solvent(vars_: Dict[str, str]) -> str:
    for key, val in vars_.items():
        if not key.startswith("solv_") or key.startswith("solv_model_"):
            continue
        m = re.match(r'\s*[A-Za-z0-9_]+\(([^)]+)\)\s*$', val)
        if m:
            return m.group(1).strip()
    xtb_solv = vars_.get("xtb_solv", "").strip()
    if xtb_solv:
        toks = xtb_solv.split()
        if len(toks) >= 2:
            return toks[1]
    return "—"


def print_summary(
    job_name_val: str,
    style_val: str,
    charge_val: int,
    multi_val: int,
    constraint_mode_val: bool,
    monitor_mode_val: bool,
    constraints_val: List[str],
    monitors_val: List[str],
    vars_: Dict[str, str],
) -> None:
    W = 18
    solvent_val = _extract_solvent(vars_)

    print("=" * 62)
    print(f"  {'Template':<{W}}: {job_name_val}  [{style_val}]")
    print(f"  {'Charge / Mult':<{W}}: {charge_val} / {multi_val}")
    print(f"  {'Solvent':<{W}}: {solvent_val}")
    print(f"  {'Constraints':<{W}}: {'ON (' + str(len(constraints_val)) + ')' if constraint_mode_val else 'OFF'}")
    if monitor_mode_val:
        print(f"  {'Monitor internals':<{W}}: ON ({len(monitors_val)})")

    steps = _discover_steps(vars_)
    if steps:
        print(f"  {'─' * 58}")
        for step in steps:
            row = _build_row(vars_, step)
            print(f"  {('[' + step + ']'):<{W}}: {row}")
    print("=" * 62 + "\n")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Prepare ORCA job folders from XYZ files. "
                    "Run with no flags for the guided wizard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Aliases (use with -t):\n  " + ", ".join(sorted(ALIASES)),
    )
    p.add_argument("-t", "--template", metavar="ALIAS",
                   help="template alias (skips wizard)")
    p.add_argument("-s", "--style", choices=STYLES,
                   help=f"functional-style tree under ORCA_DIR "
                        f"(libxc = %%method block, native = ! line keyword). "
                        f"Default with --no-prompt: {DEFAULT_STYLE}.")
    p.add_argument("-c", "--charge", type=int,
                   help="molecular charge (skips charge prompt)")
    p.add_argument("-m", "--multi", type=int,
                   help="spin multiplicity (skips multi prompt)")
    p.add_argument("--constraints", metavar="\"B 0 1; B 0 5; ...\"",
                   help="semicolon-separated constraint specs "
                        "(skips constraint guided entry)")
    p.add_argument("--monitors", metavar="\"B 0 1; ...\"",
                   help="semicolon-separated monitor specs "
                        "(skips monitor guided entry)")
    p.add_argument("--no-prompt", action="store_true",
                   help="fail fast if any required value is missing "
                        "(no interactive fallback)")
    return p


# ---------------------------------------------------------------------------
# Alias resolution + sanity checks
# ---------------------------------------------------------------------------
def _alias_to_path(alias: str, style: str) -> Path:
    if alias not in ALIASES:
        raise SystemExit(f"❌ Unknown template alias: '{alias}'. "
                         f"Use --help or run interactively and type '?' for the menu.")
    if style not in STYLES:
        raise SystemExit(f"❌ Unknown style: '{style}'. Choose from {STYLES}.")
    style_dir = ORCA_DIR / style
    candidate = style_dir / ALIASES[alias]
    # Fallback for pre-split layouts (no libxc/ or native/ subdir).
    if not candidate.exists() and not style_dir.is_dir():
        candidate = ORCA_DIR / ALIASES[alias]
    return candidate


def _need(value, label: str, no_prompt: bool):
    if value is None and no_prompt:
        raise SystemExit(f"❌ --no-prompt set but '{label}' is missing on CLI.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if not ORCA_DIR.exists():
        print(f"❌ Template tree not found (looked in: {ORCA_DIR}).\n"
              "   Point $ORCA_TEMPLATES at a folder containing native/ and libxc/, "
              "or run from inside the repo.", file=sys.stderr)
        return 1

    # --- Detect .xyz files in cwd ---
    xyz_files = sorted(Path.cwd().glob("*.xyz"))
    if not xyz_files:
        print("❌ No .xyz files found in this directory.")
        return 1
    single_mode = len(xyz_files) == 1

    # --- Pick functional style ---
    if args.style:
        style = args.style
    elif args.no_prompt:
        style = DEFAULT_STYLE
    else:
        style = _wizard_pick_style()

    # --- Pick template alias ---
    if args.template:
        alias = args.template.strip().lower()
        if alias not in ALIASES:
            # try substring resolution non-interactively too
            matches = [a for a in ALIASES if alias in a]
            if len(matches) == 1:
                alias = matches[0]
            else:
                raise SystemExit(
                    f"❌ Unknown / ambiguous template alias: '{args.template}'. "
                    f"Run without -t to see the wizard, or use --help."
                )
    else:
        _need(None, "template", args.no_prompt)
        alias = _wizard_pick_alias()

    chosen_job = _alias_to_path(alias, style)
    if not chosen_job.exists():
        raise SystemExit(f"❌ Template file not found: {chosen_job}")

    job_name = chosen_job.name
    cmp_ref  = job_name

    # --- Charge & multi ---
    if args.charge is not None:
        charge = args.charge
    else:
        _need(args.charge, "charge", args.no_prompt)
        while True:
            s = input("\nEnter the molecular charge: ").strip().lower()
            if s in ("q", "quit", "exit"):
                print("Aborted.")
                sys.exit(0)
            try:
                charge = int(s)
                break
            except ValueError:
                print("❌ Charge must be an integer (or 'q' to quit).")

    if args.multi is not None:
        multi = args.multi
    else:
        _need(args.multi, "multi", args.no_prompt)
        while True:
            s = input("Enter the spin multiplicity: ").strip().lower()
            if s in ("q", "quit", "exit"):
                print("Aborted.")
                sys.exit(0)
            try:
                multi = int(s)
                break
            except ValueError:
                print("❌ Multiplicity must be an integer (or 'q' to quit).")

    # --- Constraint / monitor mode detection ---
    cmp_text_preview = chosen_job.read_text(encoding="utf-8", errors="ignore")
    constraint_mode = bool(
        re.search(r'\borca\.\d{2}\.co', job_name)
        or re.search(r'^\s*Constraints\b', cmp_text_preview, re.MULTILINE)
    )
    monitor_mode = bool(
        re.search(r'^\s*Monitor_Internals\b', cmp_text_preview, re.MULTILINE)
    )

    constraints: List[str] = []
    monitors:    List[str] = []

    if constraint_mode:
        if args.constraints is not None:
            try:
                constraints = _parse_constraint_string(
                    args.constraints, ATOM_COUNT, default_extra="C")
            except ValueError as e:
                raise SystemExit(f"❌ Bad --constraints: {e}")
            print(f"\nUsing {len(constraints)} constraint(s) from --constraints.\n")
        else:
            _need(args.constraints, "constraints", args.no_prompt)
            print(f"\nConstraint mode active for template '{job_name}'.")
            print("Define constraints below (guided entry):\n")
            constraints = _guided_constraints("constraint", ATOM_COUNT, with_extra=True)

    if monitor_mode:
        if args.monitors is not None:
            try:
                monitors = _parse_constraint_string(
                    args.monitors, MON_COUNT, default_extra=None)
            except ValueError as e:
                raise SystemExit(f"❌ Bad --monitors: {e}")
            print(f"\nUsing {len(monitors)} monitor(s) from --monitors.\n")
        else:
            _need(args.monitors, "monitors", args.no_prompt)
            print(f"\nMonitor_Internals block detected in '{job_name}'.")
            print("Define monitor internals below (guided entry):\n")
            monitors = _guided_constraints("monitor", MON_COUNT, with_extra=False)

    # Fail loudly instead of shipping the template's placeholder block: a constrained or
    # monitored template with zero entries would otherwise run with the shipped
    # {B 0 1 ...} placeholder atoms (wrong indices) with no warning.
    for mode_on, items, flag in ((constraint_mode, constraints, "constraints"),
                                 (monitor_mode, monitors, "monitors")):
        if mode_on and not items:
            raise SystemExit(
                f"❌ '{job_name}' has a {flag[:-1]} block but none were provided — refusing to "
                f"ship the template's placeholder atoms. Pass --{flag} \"B i j; ...\" or add at "
                "least one at the guided prompt.")

    # --- Process each .xyz file ---
    final_vars: Dict[str, str] = {}

    for xyz_file in xyz_files:
        base   = xyz_file.stem
        folder = Path.cwd() if single_mode else Path(base)
        folder.mkdir(exist_ok=True)
        if not single_mode:
            shutil.move(str(xyz_file), folder / xyz_file.name)
        xyz_path = folder / xyz_file.name

        dest_cmp = folder / job_name
        shutil.copy2(chosen_job, dest_cmp)

        cmp_text = dest_cmp.read_text(encoding="utf-8", errors="ignore")
        cmp_text = replace_header_vars(cmp_text, xyz_path.name, charge, multi)

        if constraint_mode:
            cmp_text = replace_block_all(cmp_text, "Constraints", constraints)
        if monitor_mode:
            cmp_text = replace_block_all(cmp_text, "Monitor_Internals", monitors)

        dest_cmp.write_text(cmp_text, encoding="utf-8")

        inp_path = folder / f"{base}.inp"
        inp_path.write_text(f'%Compound "{cmp_ref}"\n', encoding="utf-8")

        final_vars = extract_vars(cmp_text)   # same across all files; use last
        print(f"✅ {xyz_file.name}  →  {inp_path.name}")

    print("\n✅ All .xyz files processed successfully.\n")

    print_summary(
        job_name,
        style,
        charge,
        multi,
        constraint_mode,
        monitor_mode,
        constraints,
        monitors,
        final_vars,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
