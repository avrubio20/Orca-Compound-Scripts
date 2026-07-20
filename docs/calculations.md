# Calculations

The workflow families, when to reach for each, and how results are reported. Pick a
template with `preporca.py -t <alias>` or the interactive wizard; `--help` (or `?` in
the wizard) lists them all.

## Functional style: `native` vs `libxc`

Identical workflows, two ways of naming the functional. `-s native` puts an ORCA
keyword on the `!` line (`B3LYP D3BJ`); `-s libxc` uses a libXC name in a `%method`
block (`hyb_gga_xc_wb97x_v`). Pick whichever names the functional you want.

## Minimum optimization

| alias     | use                                                            |
|-----------|----------------------------------------------------------------|
| `opt`     | optimization + frequency validation                            |
| `opt-sp`  | opt, then a high-level single point for the energy             |
| `opt-wfs` | UKS opt + wavefunction-stability check + re-opt (broken-symmetry / open-shell singlets) |

Reach for `opt-wfs` when the SCF may fall into an unstable (e.g. broken-symmetry)
solution — it re-optimizes on the stabilized wavefunction.

## Transition states

Two routes:

- **From a good guess** — `ts` (OptTS + frequencies) or `ts-sp` (+ high-level single point).
- **Constrained pre-opt (recommended)** — `ts2-*`. A constrained pre-optimization freezes
  the reacting bonds to build a Hessian, then runs OptTS + a frequency check. The pre-opt
  engine is DFT (`ts2-dft`) or GFN2-xTB (`ts2-xtb`, faster). Add-ons:
  - `ts2-sp-*` — high-level single point after the TS
  - `ts2-irc-*` — single point + IRC
  - `ts2-wfs-*` — wavefunction-stability check + re-opt + single point

Name the frozen bonds when generating:

```bash
preporca.py -t ts2-dft -c 0 -m 1 --constraints "B 12 34; B 12 40"
```

Atom indices are 0-based; `B i j` freezes the i–j bond (also `A i j k` angle, `D i j k l` dihedral).

## Conformer search (GOAT)

`goat-opt` / `goat-opt-sp` run a GOAT conformer search, then optimize (and optionally
single-point) the best conformer. `goat-ts2-*` feed the search into a constrained TS
workflow. `opt-goat` optimizes first, then searches, then re-optimizes.

## Single points

| alias      | method                                              |
|------------|-----------------------------------------------------|
| `sp`       | DFT single point                                    |
| `sp-dlpno` | DLPNO-CCSD(T) single point (reads `MDCI_TOTAL_ENERGY`) |
| `freq-sp`  | frequencies on a fixed geometry, then a single point |

## ECD

`ecd` runs a full TD-DFT job (CAM-B3LYP, diffuse basis) and computes rotatory
strengths in both length and velocity gauge. Read `R(velocity)` from the
`CD SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS` block — the velocity form is
origin-independent; agreement with the length form is the usual quality check.

## Thermochemistry

Optimization / TS / frequency templates print a summary block (`E1_el`, `ZPE`, `H1`,
`S1`, `G1`, `Corr`, …). Single-point-bearing templates add the high-level correction:
the DFT total is taken from `JOB_INFO_TOTAL_EN` (dispersion-inclusive), and the
low-level Gibbs correction is carried onto it (`G2 = E2_el + (G1 - E1_el)`).

## Editing method, basis, and solvation

Per job, edit the `Variable` block at the top of the generated `.cmp` (functional,
basis, `param`, `solv_*`). Across many templates at once, use `change_method.py`.
Solvation defaults to CPCM/SMD (diethyl ether); set `gas_* = 1` for gas phase.
