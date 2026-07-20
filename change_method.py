#!/usr/bin/env python3
"""
change_method.py  --  Batch editor for ORCA .cmp compound-script variables.

Detects and edits Variable lines from these families:
    method_*   basis_*   param_*   solv_*   xtb_*   goat_*   IRC_*

The `solv_*` family carries composite "MODEL(solvent)" strings (e.g.
solv_opt = "CPCM(chloroform)"), replacing the older split form
(solv_model_* + standalone `solvent`). The `xtb_*` family carries
xtb-side flags (xtb_method = "--gxtb", xtb_solv = "--cosmo chloroform").
Note: ALPB/GBSA solvation is GFN2-only; g-xTB only supports COSMO or gas
(set xtb_solv to "" for gas phase).

Only string-valued Variables (quoted values) are matched.

Numeric Variables -- edit by hand:
    gas_geom, gas_sp (phase toggles, 0/1),
    MaxNTries*, Cutoff, scaling, NNegativeTarget*, IRC_MaxIter,
    goat_nworkers, charge, multi.

Per-system Variables (molecule, myFilename) are also not handled here.

Value-scoped edits:
    The same Variable NAME can carry different values in different job types
    (e.g. method_sp = "B3LYP D3BJ" in the DFT single-points but
    method_sp = "DLPNO-CCSD(T)" in orca.08). When a name has more than one
    distinct current value across the scanned files, edits can be TARGETED at
    one current value, leaving the differently-valued occurrences untouched --
    both interactively (you are asked per current value) and via --set
    (NAME:OLDVAL=NEWVAL). When a name has a single current value it behaves
    exactly as before (one value applied everywhere).

Usage:
    python change_method.py somefile.cmp              # single file
    python change_method.py /path/to/folder           # all .cmp in folder
    python change_method.py . --recursive             # include subdirs
    python change_method.py -s libxc                  # scope to libxc/ subtree
    python change_method.py -s native                 # scope to native/ subtree
    python change_method.py --confs                   # mass-edit conformer-folder .cmp (cwd)

    # Non-interactive batch edits (skip the prompt entirely):
    python change_method.py . --set basis_sp="def2-TZVP"
    python change_method.py . --set 'method_sp:B3LYP D3BJ=r2SCAN-3c'   # value-scoped
    python change_method.py . --set method_opt=r2SCAN-3c --set solv_opt="CPCM(water)"

    # File filters (glob on the .cmp basename), composable with any mode:
    python change_method.py . --recursive --exclude '*08*'   # skip the DLPNO SP
    python change_method.py . --recursive --only 'orca.0[12]*.cmp'

Flags:
    -s, --style {libxc,native,both}
                    When the target contains libxc/ and native/ subdirs,
                    restrict the scan to that subtree. 'both' edits both
                    (warning: a single new value will be written into
                    both styles, which usually isn't what you want since
                    libxc names and ORCA-native keywords differ).
    --confs         Conformer mode: edit the .cmp inside conformer folders
                    (*_conf*/) under target (default cwd). One value is applied
                    across all conformers of the same job type. Skips the
                    libxc/native scoping (the conf .cmp are already a fixed style).
    --set NAME=NEWVAL           Non-interactive: change every occurrence of NAME.
    --set NAME:OLDVAL=NEWVAL    Non-interactive, value-scoped: change only the
                    occurrences of NAME whose CURRENT value == OLDVAL. Repeatable.
                    Giving any --set skips the interactive prompt. "blank" is
                    honoured on both sides (NEWVAL and OLDVAL) as the empty
                    string "". Honours --dry-run and --bak.
    --only GLOB     Keep only .cmp whose basename matches GLOB (fnmatch).
    --exclude GLOB  Drop .cmp whose basename matches GLOB (fnmatch). Both are
                    repeatable and applied at file selection, so they compose
                    with -s/--confs/--recursive/multiple targets. --only is
                    applied first, then --exclude.
    --recursive     Scan subdirectories
    --dry-run       Preview changes without writing
    --bak           Write a timestamped .bak copy before editing each file
                    (default: no backup).

Tips:
    Enter "blank" as a new value to set the variable to "" (empty string).
"""

import argparse, datetime, fnmatch, re, shutil, sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

# -- Configuration ----------------------------------------------------------

STYLES = ("native", "libxc")

FAMILIES = ["method", "basis", "param", "solv", "xtb", "goat", "IRC"]

# Bare family names that can appear without a _suffix.
# (Previously included `solvent`, removed in the .cmp refactor that folded
# solvent into the composite solv_* values.)
BARE_FAMILIES: List[str] = []

# Preferred display order for step-suffixes in the interactive UI.
# Anything not in this list is appended in alphabetical order after these.
STEP_ORDER = [
    "global",
    "method", "base", "minxyz", "solv",   # goat_* / xtb_* suffixes
    "copt", "opt", "tsopt", "freq",
    "sp",
    "irc", "Direction",                   # IRC_* suffixes
]

# Match:  Variable <n> = "<value>";  with optional trailing # comment
# Accepts family_suffix (method_opt) and, if any are configured, bare names.
_fam_pat  = '|'.join(FAMILIES)
_name_alts = [r'(?:' + _fam_pat + r')_[A-Za-z0-9_]+']
if BARE_FAMILIES:
    _name_alts.append('|'.join(BARE_FAMILIES))
_name_pat = '|'.join(_name_alts)
VAR_RE = re.compile(
    r'^(?P<indent>\s*)'
    r'Variable\s+'
    r'(?P<n>(?:' + _name_pat + r'))'
    r'(?P<eq>\s*=\s*)'
    r'"(?P<value>[^"]*)"'
    r'\s*;'
    r'(?P<tail>.*)$'
)

# -- Data -------------------------------------------------------------------

class Occurrence(NamedTuple):
    path: Path
    line: int          # 0-indexed line number
    name: str
    value: str


class Change(NamedTuple):
    """A single edit request.

    `old is None`  -> change EVERY occurrence of `name` (name-wide).
    `old is a str` -> value-scoped: change only occurrences of `name` whose
                      CURRENT value equals `old`, leaving the rest untouched.
    Value-scoped changes take precedence over a name-wide change for the same
    name, so `--set method_sp=X --set method_sp:DLPNO-CCSD(T)=Y` sends the
    DLPNO occurrences to Y and all others to X.
    """
    name: str
    old: Optional[str]
    new: str


def family_of(name: str) -> str:
    """method_opt -> method, solv_opt -> solv, xtb_method -> xtb"""
    for f in sorted(FAMILIES, key=len, reverse=True):
        if name == f or name.startswith(f + "_"):
            return f
    return name


def step_of(name: str) -> str:
    """method_opt -> opt, solv_sp -> sp, xtb_method -> method, solvent -> global"""
    fam = family_of(name)
    if name == fam:
        return "global"
    return name[len(fam) + 1:]


# -- File discovery & scanning ----------------------------------------------

def resolve_target(target: Path, style: Optional[str]) -> List[Path]:
    """
    Returns one or more roots to scan, after applying the style scope.

    - If `target` is a single file or has no libxc/native subdirs, no scoping.
    - If style == "both", scope to [target/libxc, target/native].
    - If style in STYLES, scope to [target/<style>] when that dir exists.
    - If target has libxc/ + native/ subdirs and style is None, return [] so
      the caller can prompt.
    """
    if target.is_file():
        return [target]
    if not target.is_dir():
        return []

    has_styles = all((target / s).is_dir() for s in STYLES)
    if not has_styles:
        return [target]

    if style == "both":
        return [target / s for s in STYLES]
    if style in STYLES:
        return [target / style]
    return []   # caller must prompt


def find_cmp_files(target: Path, recursive: bool) -> List[Path]:
    if target.is_file() and target.suffix.lower() == ".cmp":
        return [target]
    if target.is_dir():
        glob = target.rglob if recursive else target.glob
        return sorted(p for p in glob("*.cmp") if p.is_file())
    return []


# Conformer-folder layout written by orca_confs.py: {basename}_conf{NN}/<tmpl>.cmp
# The [0-9] guards against stray dirs like `old_conformers/` matching.
CONF_GLOB = "*_conf[0-9]*/*.cmp"


def find_conf_cmp_files(target: Path) -> List[Path]:
    """Find the per-conformer .cmp files under conformer folders (*_conf*/)
    within `target`. All conformers of one job type share the same template,
    so a single new value fans out across every match."""
    base = target if target.is_dir() else Path.cwd()
    return sorted(p for p in base.glob(CONF_GLOB) if p.is_file())


def scan(path: Path) -> List[Occurrence]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)
    except OSError as e:
        print(f"  [warn] {path}: {e}", file=sys.stderr)
        return []
    occs: List[Occurrence] = []
    for i, line in enumerate(lines):
        m = VAR_RE.match(line)
        if m:
            occs.append(Occurrence(path, i, m.group("n"), m.group("value")))
    return occs


# -- Rewriting --------------------------------------------------------------

def rewrite_line(line: str, new_value: str) -> str:
    """Replace only the quoted value, preserving indent, spacing, and trailing comment."""
    m = VAR_RE.match(line)
    if not m:
        return line
    eol = "\n" if line.endswith("\n") else ""
    tail = m.group("tail")
    return f'{m.group("indent")}Variable {m.group("n")}{m.group("eq")}"{new_value}";{tail}{eol}'


# -- Display ----------------------------------------------------------------

def hr(char="-", width=60):
    print(char * width)


def compact_files(paths: List[Path], limit: int = 4) -> str:
    """Compact `parent/name` labels for the files holding a value.

    Uses the parent-dir name so native/ vs libxc/ twins (and conformer
    folders) stay distinguishable even though they share a basename.
    """
    labels = [f"{p.parent.name}/{p.name}" for p in paths]
    if len(labels) <= limit:
        return ", ".join(labels)
    return ", ".join(labels[:limit]) + f", +{len(labels) - limit} more"


def show_summary(files: List[Path], occs: List[Occurrence],
                 values: Dict[str, Set[str]],
                 val_paths: Dict[str, Dict[str, List[Path]]]) -> None:
    touched = {o.path for o in occs}
    hr("=")
    print(f"  ORCA .cmp editor  |  {len(files)} file(s) scanned, "
          f"{len(touched)} with managed variables")
    hr("=")
    if not occs:
        print("  No matching variables found.\n")
        return

    for fam in FAMILIES:
        fam_names = sorted(n for n in values if family_of(n) == fam)
        if not fam_names:
            continue
        print(f"\n  [{fam}_*]")
        for name in fam_names:
            count = sum(1 for o in occs if o.name == name)
            vals  = sorted(values[name])
            if len(vals) == 1:
                print(f'    {name:<28s}  {count:>2}x | "{vals[0]}"')
            else:
                # Ambiguous name: show each current value and where it lives so
                # the value-scoping decision is visible before editing.
                print(f"    {name:<28s}  {count:>2}x | {len(vals)} distinct values:")
                for v in vals:
                    n_v = sum(1 for o in occs if o.name == name and o.value == v)
                    where = compact_files(val_paths[name][v])
                    print(f'        "{v}"  ({n_v}x)  <- {where}')
    print()


# -- Interactive prompts ----------------------------------------------------

def yn(question: str) -> bool:
    while True:
        try:
            a = input(f"  {question} [y/N]: ").strip().lower()
        except EOFError:
            return False   # non-interactive / empty stdin -> treat as "no"
        if a in ("y", "yes"):  return True
        if a in ("", "n", "no"): return False


def parse_new_value(raw: str) -> str:
    """
    Interpret user input as a variable value.
    Entering the word 'blank' (case-insensitive) produces an empty string "".
    """
    if raw.strip().lower() == "blank":
        return ""
    return raw


def parse_set(spec: str) -> Change:
    """Parse a --set argument into a Change.

        NAME=NEWVAL           -> Change(NAME, None, NEWVAL)     (name-wide)
        NAME:OLDVAL=NEWVAL    -> Change(NAME, OLDVAL, NEWVAL)   (value-scoped)

    Splits on the FIRST '=' (values may contain '='), and the name/oldval
    split is on the FIRST ':'. "blank" (case-insensitive) is honoured on both
    the new and the old side as the empty string "". Raises ValueError on a
    malformed spec.
    """
    if "=" not in spec:
        raise ValueError(f"--set expects NAME=NEWVAL or NAME:OLDVAL=NEWVAL, got: {spec!r}")
    key, new_raw = spec.split("=", 1)
    if ":" in key:
        name_raw, old_raw = key.split(":", 1)
        name = name_raw.strip()
        old: Optional[str] = parse_new_value(old_raw.strip())
    else:
        name, old = key.strip(), None
    if not name:
        raise ValueError(f"--set is missing a variable name: {spec!r}")
    return Change(name, old, parse_new_value(new_raw.strip()))


def choose_changes(values: Dict[str, Set[str]],
                   counts: Dict[str, Dict[str, int]]) -> List[Change]:
    changes: List[Change] = []
    hr()
    print("  Interactive edit -- press Enter to skip any variable")
    print('  Tip: enter "blank" to set a value to "" (empty string)\n')

    # Step order: preferred order first, then anything else alphabetically
    all_steps = {step_of(name) for name in values}
    steps = [s for s in STEP_ORDER if s in all_steps]
    steps += sorted(all_steps - set(STEP_ORDER))

    prompt = "    -> New value for {} (empty = skip, \"blank\" = \"\"): "

    for step in steps:
        group = sorted(n for n in values if step_of(n) == step)
        if not group:
            continue

        print(f"  [ step: {step} ]")
        for name in group:
            vals = sorted(values[name])
            if len(vals) == 1:
                # Single value: unchanged one-shot behaviour (name-wide edit).
                print(f'    {name} = "{vals[0]}"')
                if yn(f"Change {name}?"):
                    new = input(prompt.format(name)).strip()
                    if new:
                        changes.append(Change(name, None, parse_new_value(new)))
            else:
                # Multiple current values: target each one separately so a
                # change to one value doesn't clobber the others.
                print(f"    {name} has {len(vals)} distinct current values:")
                for v in vals:
                    print(f'        "{v}"  ({counts[name][v]}x)')
                print("    (target each value separately; Enter to skip)")
                for v in vals:
                    if yn(f'Change {name} where it is "{v}"?'):
                        new = input(prompt.format(name)).strip()
                        if new:
                            changes.append(Change(name, v, parse_new_value(new)))
        print()

    return changes


# -- Apply changes ----------------------------------------------------------

def apply_changes(occs: List[Occurrence], changes: List[Change],
                  dry_run: bool, make_backup: bool) -> None:
    hr()
    print("  Changes to apply:")

    # Split into value-scoped and name-wide lookups. Scoped wins when both
    # match a given occurrence.
    scoped: Dict[Tuple[str, str], str] = {}
    wildcard: Dict[str, str] = {}
    for c in changes:
        if c.old is None:
            wildcard[c.name] = c.new
            print(f'    {c.name} (all)  ->  "{c.new}"')
        else:
            scoped[(c.name, c.old)] = c.new
            print(f'    {c.name}  ["{c.old}"]  ->  "{c.new}"')
    print()

    def new_value_for(o: Occurrence) -> Optional[str]:
        if (o.name, o.value) in scoped:
            return scoped[(o.name, o.value)]
        if o.name in wildcard:
            return wildcard[o.name]
        return None

    by_file: Dict[Path, List[Occurrence]] = {}
    for o in occs:
        by_file.setdefault(o.path, []).append(o)

    n_files = n_lines = 0
    for fp in sorted(by_file):
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines(True)
        new_lines = list(lines)
        changed = 0
        for o in by_file[fp]:
            nv = new_value_for(o)
            if nv is None:
                continue
            replacement = rewrite_line(lines[o.line], nv)
            if replacement != lines[o.line]:
                new_lines[o.line] = replacement
                changed += 1
        if not changed:
            continue

        n_files += 1
        n_lines += changed

        if dry_run:
            print(f"  [dry-run] {fp.name}  ({changed} line(s))")
            continue

        if make_backup:
            ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = fp.with_suffix(fp.suffix + f".bak_{ts}")
            shutil.copy2(fp, bak)
            print(f"  [backup]  {bak.name}")

        fp.write_text("".join(new_lines), encoding="utf-8")
        print(f"  [written] {fp.name}  ({changed} line(s))")

    hr()
    tag = "DRY-RUN" if dry_run else "DONE"
    print(f"  {tag}  |  {n_files} file(s), {n_lines} line(s) changed\n")


# -- Entry point ------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("target", nargs="*", default=["."],
                    help="One or more .cmp files or directories (default: .). "
                         "Passing several explicit paths edits exactly those, in "
                         "one shared prompt (used to target specific reset "
                         "revisions without touching siblings).")
    ap.add_argument("-s", "--style", choices=(*STYLES, "both"),
                    help="Scope edit to libxc/, native/, or both subtrees "
                         "(only applies when target contains both subdirs).")
    ap.add_argument("--confs", action="store_true",
                    help="Conformer mode: edit the .cmp inside conformer folders "
                         "(*_conf*/) under target (default: cwd). One value is "
                         "applied across all conformers of the same job type.")
    ap.add_argument("--set", dest="sets", action="append", metavar="NAME[:OLDVAL]=NEWVAL",
                    help="Non-interactive edit (repeatable; any --set skips the "
                         "prompt). NAME=NEWVAL changes every occurrence of NAME; "
                         "NAME:OLDVAL=NEWVAL changes only occurrences whose current "
                         'value == OLDVAL. "blank" means "" on either side.')
    ap.add_argument("--only", dest="only", action="append", metavar="GLOB",
                    help="Keep only .cmp whose basename matches GLOB (fnmatch; "
                         "repeatable; applied before --exclude).")
    ap.add_argument("--exclude", dest="exclude", action="append", metavar="GLOB",
                    help="Drop .cmp whose basename matches GLOB (fnmatch; "
                         "repeatable).")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--dry-run",   action="store_true")
    ap.add_argument("--bak", action="store_true",
                    help="Write a timestamped .bak copy before editing each "
                         "file (default: no backup).")
    args = ap.parse_args(argv)

    # Parse --set specs up front so a malformed one fails before any scanning.
    set_changes: List[Change] = []
    if args.sets:
        try:
            set_changes = [parse_set(s) for s in args.sets]
        except ValueError as e:
            print(f"[error] {e}", file=sys.stderr)
            return 2

    targets: List[Path] = []
    for t in (args.target or ["."]):
        p = Path(t).expanduser().resolve()
        if not p.exists():
            print(f"[error] Not found: {p}", file=sys.stderr)
            return 2
        targets.append(p)

    files: List[Path] = []

    if args.confs:
        # Conformer mode: glob the per-conformer .cmp; skip libxc/native scoping
        # (the conformer .cmp are already a fixed style — whatever was prepped).
        for t in targets:
            files.extend(find_conf_cmp_files(t))
        if not files:
            print(f"No conformer .cmp files found (looked for {CONF_GLOB} under "
                  f"{', '.join(str(t) for t in targets)}).")
            return 0
        n_folders = len({f.parent for f in files})
        print(f"\n  Conformer mode: {len(files)} .cmp file(s) across "
              f"{n_folders} folder(s).")
    elif len(targets) == 1:
        # Single target: resolve style scope. If it's the split layout root and
        # no --style was given, prompt the user.
        target = targets[0]
        roots = resolve_target(target, args.style)
        if not roots and set_changes:
            # Non-interactive: never block on the style prompt.
            print("[error] Target contains both libxc/ and native/ subdirs; "
                  "pass -s native|libxc|both with --set.", file=sys.stderr)
            return 2
        if not roots:
            print("\n  Target contains both libxc/ and native/ subdirs.")
            print("  Which subtree do you want to edit?")
            print("    1) native")
            print("    2) libxc")
            print("    3) both  (warning: same value gets written into both styles)")
            while True:
                sel = input("  > ").strip().lower()
                if sel in ("1", "native"):
                    roots = [target / "native"]; break
                if sel in ("2", "libxc"):
                    roots = [target / "libxc"]; break
                if sel in ("3", "both"):
                    roots = [target / s for s in STYLES]; break
                print("  Please enter 1, 2, or 3.")

        if len(roots) > 1 or (len(roots) == 1 and roots[0] != target):
            print(f"\n  Scoped to: {', '.join(str(r.relative_to(target)) for r in roots)}")
            # Style scoping implies recursive scan (subtrees have TS/, GOAT/ subdirs).
            args.recursive = True

        for r in roots:
            files.extend(find_cmp_files(r, args.recursive))
        if not files:
            print("No .cmp files found.")
            return 0
    else:
        # Multiple explicit targets (e.g. orca_confs --reset --cm passing the
        # exact revision folders): edit precisely those, no style scoping.
        for t in targets:
            if t.is_file() and t.suffix.lower() == ".cmp":
                files.append(t)
            else:
                files.extend(find_cmp_files(t, args.recursive))
        if not files:
            print("No .cmp files found in the given targets.")
            return 0

    # De-dup while preserving order (a target could overlap another).
    seen: Set[Path] = set()
    files = [f for f in files if not (f in seen or seen.add(f))]

    # File filters on the .cmp basename (fnmatch). --only first, then --exclude.
    # Applied at selection so they compose with every mode above.
    if args.only:
        files = [f for f in files
                 if any(fnmatch.fnmatch(f.name, pat) for pat in args.only)]
    if args.exclude:
        files = [f for f in files
                 if not any(fnmatch.fnmatch(f.name, pat) for pat in args.exclude)]
    if not files:
        print("No .cmp files left after --only/--exclude filtering.")
        return 0

    # Scan all files
    all_occs: List[Occurrence] = []
    for fp in files:
        all_occs.extend(scan(fp))

    # Index: distinct values, per-value occurrence counts, and per-value files.
    values: Dict[str, Set[str]] = {}
    counts: Dict[str, Dict[str, int]] = {}
    val_paths: Dict[str, Dict[str, List[Path]]] = {}
    for o in all_occs:
        values.setdefault(o.name, set()).add(o.value)
        cn = counts.setdefault(o.name, {})
        cn[o.value] = cn.get(o.value, 0) + 1
        vp = val_paths.setdefault(o.name, {}).setdefault(o.value, [])
        if o.path not in vp:
            vp.append(o.path)

    show_summary(files, all_occs, values, val_paths)
    if not all_occs:
        return 0

    if set_changes:
        # Non-interactive batch: warn on any --set that matches nothing, then
        # apply deterministically without prompting.
        for c in set_changes:
            hit = any(o.name == c.name and (c.old is None or o.value == c.old)
                      for o in all_occs)
            if not hit:
                desc = c.name if c.old is None else f'{c.name}:"{c.old}"'
                print(f'  [warn] --set {desc}=... matched no occurrences.',
                      file=sys.stderr)
        changes = set_changes
    else:
        changes = choose_changes(values, counts)

    if not changes:
        print("  Nothing to change. Exiting.")
        return 0

    apply_changes(all_occs, changes, args.dry_run, args.bak)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())