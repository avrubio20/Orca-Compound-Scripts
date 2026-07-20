# Editing methods in bulk

`change_method.py` batch-edits the quoted-string Variables in the ORCA `.cmp` templates across many
files at once — the `method_*`, `basis_*`, `param_*`, `solv_*`, `xtb_*`, `goat_*`, and `IRC_*`
families. It preserves indentation and trailing comments and only touches the quoted value, so it is
safe to sweep the whole tree.

It edits **string values only**. Numeric knobs (`charge`, `multi`, `gas_geom`, `gas_sp`, `Cutoff`,
`scaling`, `MaxNTries*`, `IRC_MaxIter`, `goat_nworkers`) and per-system Variables (`molecule`,
`myFilename`) are edited by hand.

## See what's there

Run it against a target to get a scan summary — no flags needed to look. Scope with
`-s native|libxc|both` when the target holds both trees:

```
change_method.py -s native
```

```
  Scoped to: native
============================================================
  ORCA .cmp editor  |  26 file(s) scanned, 26 with managed variables
============================================================

  [method_*]
    method_copt                   12x | 3 distinct values:
        "B3LYP D3BJ"  (6x)  <- TS/orca.01.co-ts.dft.cmp, TS/orca.02.co-ts-sp.dft.cmp, +4 more
        "XTB"  (1x)  <- TS/orca.01.co-ts.xtb.cmp
        "XTB2"  (5x)  <- TS/orca.02.co-ts-sp.xtb.cmp, +4 more
    method_opt                     7x | 2 distinct values:
        "B3LYP D3BJ"  (6x)  <- native/orca.01.opt.cmp, +5 more
        "r2SCAN-3c"  (1x)  <- native/orca.11.mecp.cmp
    method_sp                     17x | 3 distinct values:
        "B3LYP D3BJ"  (15x)  <- ... +11 more
        "DLPNO-CCSD(T)"  (1x)  <- native/orca.08.sp-dlpno.cmp
    method_tsopt                  14x | "B3LYP D3BJ"

  [basis_*]
    basis_sp                      17x | 2 distinct values:
        "def2-TZVPP def2-TZVPP/C def2/J"  (1x)  <- native/orca.08.sp-dlpno.cmp
        "def2-TZVPP def2/J"  (16x)  <- ... +15 more
    basis_tsopt                   14x | "def2-SVP def2/J"
  ...
```

The summary lists each managed Variable, how many times it occurs, and its distinct current values.
A single value prints inline; a Variable with more than one value lists each value, its count, and
where it lives. That listing is what tells you when a name-wide edit would be unsafe.

## Interactive edit

Run with no `--set` and it walks the Variables grouped by step, prompting per Variable:

```
change_method.py -s native
```

Press Enter to skip any Variable. When a name has several current values, it asks about each value
separately so you can retarget one without touching the others. Enter `blank` to set a value to `""`.

## Batch edit with --set (preview first)

`--set NAME=NEWVAL` is the non-interactive path (repeatable; any `--set` skips the prompt). **Always
`--dry-run` first** to see exactly which files would change:

```
change_method.py -s native --set basis_sp="def2-TZVP" --dry-run
```

```
------------------------------------------------------------
  Changes to apply:
    basis_sp (all)  ->  "def2-TZVP"

  [dry-run] orca.02.opt-sp.cmp  (1 line(s))
  [dry-run] orca.05.ts-sp.cmp  (1 line(s))
  [dry-run] orca.08.sp-dlpno.cmp  (1 line(s))
  ...
------------------------------------------------------------
  DRY-RUN  |  17 file(s), 17 line(s) changed
```

Drop `--dry-run` to apply. But look at the preview above: `orca.08.sp-dlpno.cmp` is in the list — a
name-wide `basis_sp` edit overwrites its DLPNO basis too. That is exactly the case the next section
handles.

## Value-scoped edits

The same NAME can carry different values in different job types. `basis_sp` is `"def2-TZVPP def2/J"`
in the ordinary single points but `"def2-TZVPP def2-TZVPP/C def2/J"` in the DLPNO `orca.08` (the `/C`
correlation-fitting basis DLPNO needs). A name-wide `--set basis_sp=...` hits both.

Scope the edit to one current value with `NAME:OLDVAL=NEWVAL` — only occurrences whose current value
equals `OLDVAL` change:

```
change_method.py -s native --set 'basis_sp:def2-TZVPP def2/J=def2-QZVPP def2/J' --dry-run
```

The DLPNO occurrence keeps its `def2-TZVPP/C` value. Same guard applies to `method_sp` (B3LYP in the
DFT single points vs `DLPNO-CCSD(T)` in `orca.08`):

```
change_method.py -s native --set 'method_sp:B3LYP D3BJ=r2SCAN-3c' --dry-run
```

Quote the whole spec when a value contains spaces. `blank` is honoured on either side of the `=`.

## Scope and filters

- `-s native|libxc|both` — restrict to a subtree when the target contains both. `both` writes the
  same value into both styles, which usually isn't what you want (libXC names and native keywords
  differ).
- `--only GLOB` / `--exclude GLOB` — filter by `.cmp` basename (fnmatch, repeatable; `--only` applied
  first). Skip the DLPNO SP with:

  ```
  change_method.py -s native --set basis_sp="def2-TZVP" --exclude '*08*' --dry-run
  ```

- `--recursive` — scan subdirectories (style scoping implies this automatically).
- `--bak` — write a timestamped `.bak` copy before editing each file (default: no backup).

## Tips

- `--dry-run` before every real batch edit — read the file list, confirm nothing unintended is in it.
- Prefer `NAME:OLDVAL=NEWVAL` whenever a name shows more than one value in the scan; it is the only
  way to avoid clobbering a differently-valued occurrence like the `orca.08` DLPNO basis.
- Pass `--bak` if you want a rollback point.
- `blank` (interactive or in `--set`) sets a value to `""` — e.g. gas-phase `xtb_solv`.
