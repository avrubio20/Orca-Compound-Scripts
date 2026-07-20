# ORCA `.cmp` compound-script conventions (the standard)

The standardization spec for every `.cmp` file under `~/bin/orca`. Both the
`orca-cmp-engineer` agent and `change_method.py` assume these. When a file
deviates, conform it — or change this spec deliberately and note it.

Goal: **every file is editable by `change_method.py` with no surprises, and
a `native/` file differs from its `libxc/` twin in exactly one place — the
method specification.**

---

## 1. Header block (identical everywhere except the Jobs list)

```
# =============================================================
# ORCA Compound Script
#
# Author:      Aris V. Rubio
# Affiliation: UCLA Dept. of Chemistry and Biochemistry
# Groups:      Houk Group / Athavale Group
# Email:       avrubio@g.ucla.edu
# =============================================================
# Jobs:
#   01  <role, no functional names>
#   02  <role, no functional names>
# =============================================================
```

- **Job numbering starts at 01 and is contiguous** (01, 02, 03 …). There is
  no Job 00. Single-job files are just "Job 01".

- **No version string** ("ORCA 6.1.0") and **no style tag**
  ("(NATIVE-KEYWORD STYLE)") in the header. The directory (`native/` vs
  `libxc/`) encodes the style; the version drifts and adds nothing.
- **Job descriptions name the role, never the functional.** "Opt + Freq
  loop", "High-level single point", "Constrained pre-opt loop", "TS
  optimization loop", "Wavefunction-stability check", "IRC". Never
  "(wB97X-D3BJ)". The scripts are generalizable; the functional lives in
  a Variable, not a comment.

## 2. Section banners

- Full-width `# ===…===` (61 `=`) separates the header, the Internals
  block, and each numbered Job.
- `# --- Section ---` for config sub-blocks (System, Solvation, Methods,
  Loop controls, IRC/GOAT controls, Files).

## 3. Config-variable block — fixed order

```
# --- System ---
Variable molecule = "mol.xyz";
Variable charge   = 0;
Variable multi    = 1;

# --- Solvation (gas_* = 1 forces gas phase) ---
Variable gas_geom  = 0;          # blanks geom-stage solvation
Variable gas_sp    = 0;          # blanks solv_sp        (sp-bearing files only)
Variable xtb_solv   = "...";     # xtb-side solvation flag (seed/xtb-opt files)
Variable solv_<stage> = "...";   # DFT-side, composite "MODEL(solvent)"

# --- Methods ---
Variable method_seed = "...";    # seed engine (files with a seed)
Variable method_<stage> = "...";
Variable basis_<stage>  = "...";
Variable param_<stage>  = "...";

# --- Loop controls ---       (files with Opt/TS follow-loops)
# --- IRC controls ---        (IRC files)
# --- GOAT controls ---       (GOAT files)

# --- Files ---
Variable myFilename = "geom.xyz";
```

Order is fixed so `change_method.py`'s step-ordered UI lines up and so
diffs between files are minimal.

## 4. Naming families (must match `change_method.py`)

Editable string families: `method_* basis_* param_* solv_* xtb_* goat_* IRC_*`.
Stage suffixes, in canonical order: `seed`, `copt`, `opt`, `tsopt`, `ts`,
`sp`, `irc`. (`change_method.py` `STEP_ORDER` mirrors this.)

- **No bare `solvent` variable.** Retired. Solvation is the composite
  `solv_<stage> = "MODEL(solvent)"` on the DFT side and `xtb_solv =
  "--<model> <solvent>"` on the xtb side. (`sp-dlpno.cmp` is the lone
  holdout still using bare `solvent` — conform it.)
- Numeric Variables are hand-edited, never by the tool: `charge`, `multi`,
  `gas_geom`, `gas_sp`, `MaxNTries*`, `Cutoff`, `scaling`,
  `NNegativeTarget*`, `IRC_MaxIter`, `goat_nworkers`.

## 5. Spacing & alignment

- One statement per line; `;` terminates every ORCA statement.
- Within a config sub-block, **align the `=`** to the longest variable
  name in that block (single space minimum after the name). Do not align
  across blocks.
- Inline comments start with `# ` and, within a block, align to a common
  column where practical.
- Two-space indent inside `New_Step … Step_End`, `%block … end`,
  `For … EndFor`, `If … EndIf`.
- `Print(...)` summary tables: align the `=` column across the table.

## 6. The native vs libxc method specification — the ONE difference

`native/` — functional token on the bang line:
```
! Opt Freq &{method_opt} &{basis_opt} &{param_opt} &{solv_opt} PModel
```

`libxc/` — bang line omits the functional; a `%method` block carries it:
```
! Opt Freq &{basis_opt} &{param_opt} &{solv_opt} PModel
%method
  Method     DFT
  Functional &{method_opt}
end
```

This is the **only** allowed divergence between twin files. After editing
one tree, mirror to the other and diff to prove nothing else changed.
(If the manual confirms libXC functionals are accepted on the bang line —
§3.3.6.3 — a single-tree unification may be possible; see
`libxc_native_map.md`. Until then, two trees, one difference.)

## 7. Method-value comments

Keep them neutral and generalizable — describe the *slot*, not the
functional:
- native:  `method_opt = "..."   # functional keyword`
- libxc:   `method_opt = "..."   # libXC functional name`

Never write the functional's name in a comment. A seed line that is not
DFT (`method_copt = "XTB"`) must NOT carry a "DFT functional" comment —
fix copy-paste drift.

## 8. Restart / step bookkeeping idioms

- **No xtb seed.** The first job reads the input geometry directly —
  `*xyzfile &{charge} &{multi} &{molecule}` inside its `itry=1` New_Step.
  A throwaway xtb single point was removed because it never moved atoms
  (SP) and its MOs were discarded (the next step uses PModel) — pure
  overhead. (GOAT files start with the GOAT search, which reads molecule
  on its own.)
- `StepNo` starts at 0, `+1` after every `New_Step`.
- First DFT step uses **ORCA's default initial guess (PAtom)** — it reads a
  fresh geometry, so no explicit guess keyword is needed. Later iterations:
  `ReadMOs(StepNo)` to inherit converged MOs. (`PModel` was only there as a
  workaround for the old xtb-seed handoff; removed with the seed. If a metal
  SCF ever struggles to converge, `PModel` — or a `BrokenSym` guess for
  open-shell singlets — is the fallback to add back on that step.)
- WFS-stabilized MOs tracked in `StepNo_WFS`; accepted TS in `StepNo_TS`.
- Hessian hand-off: `Sys_cmd("cp *_Compound_%d.hess <name>.hess", StepNo)`
  + `%geom InHess Read InHessName "<name>.hess" end`.

## 9. Imaginary-mode follow loop (minima & TS)

Read `THERMO_FREQS` → count modes `< Cutoff` → if count == target, accept;
else `FollowNormalMode(vibrationSN=minIndex+1, scalingFactor=scaling)` and
retry. `NNegativeTarget` = 0 (minimum), 1 (TS), 2 (constrained pre-opt).
The `minIndex+1` (1-indexed modes) is load-bearing — do not "simplify" it.

## 10. Timing

`timer jobtimer;` once. `jobtimer.start()` opens a job, `jobtimer.stop()`
+ a `[TIMING]` Print closes it. **Do not leave a trailing
`jobtimer.start();` after the final job** — it opens a timer nothing
stops (dead code; currently present in several files — remove).

## 11. Termination

`EndRun` is the last line. Early exits via `goto <Label>` + a bare
`<Label>:` line (`OptDone`, `ReOptDone`, `COPT_Done`, `TS_Done`,
`AbortRun`). `AbortRun:` sits just before `EndRun`.

---

## Resolved against the manual (see `libxc_native_map.md` for citations)

1. **SMD invocation — RESOLVED.** Bang-line `! SMD(solvent)` is valid
   standalone in 6.1.1 (§2.13.3). So the composite `solv_* =
   "SMD(chloroform)"` form is **correct, not a bug**. Standard: SMD and
   CPCM both ride the composite `solv_*` string on the bang line.
   `sp-dlpno.cmp`'s explicit `%cpcm SMD true … end` block is the
   equivalent long form and should be conformed to `solv_sp =
   "SMD(diethylether)"` (confirm SMD-on-coupled-cluster with the
   specialist — §2.13.6).
2. **libXC on the bang line — RESOLVED.** `!LibXC(Keyword)` only reaches
   functionals that already have native keywords, so it does NOT let the
   two trees collapse. Raw libXC names still need the `%method` block.
   Keep two trees with the single §6 divergence; a one-tree option exists
   (block form for both) but relocates dispersion handling — see
   `libxc_native_map.md` before adopting it.
