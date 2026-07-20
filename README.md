# ORCA Compound Scripts

Templated ORCA 6.1.1 Compound (`.cmp`) workflows for geometry optimization,
transition-state search, conformer sampling (GOAT), IRC, and single-point /
thermochemistry — plus a small generator, `preporca.py`, that turns an `.xyz`
into a ready-to-run job.

## Requirements

- ORCA 6.1.1
- Python 3.11+ (standard library only — no dependencies)

## Layout

```
native/            functional given by ORCA's own keyword on the ! line (e.g. "B3LYP D3BJ")
libxc/             the same scripts, functional given as a libXC name in a %method block
preporca.py        generator: .xyz -> job folder
change_method.py   bulk-edit method / basis / solvation across templates
```

`native/` and `libxc/` are identical except for how the functional is specified.
Pick whichever tree names the functional you want to run.

## Documentation

- [`docs/tutorial.md`](docs/tutorial.md) — step-by-step: the interactive wizard, plus worked opt / TS / constrained-TS / IRC examples.
- [`docs/setup.md`](docs/setup.md) — install, template resolution, and how a job runs.
- [`docs/calculations.md`](docs/calculations.md) — the workflow families, when to use each, and how results are reported.

## Setup

```bash
git clone <repo-url> orca-compound-scripts
cd orca-compound-scripts
```

`preporca.py` finds the templates automatically when it sits beside `native/` and
`libxc/` (as in the repo). To call it from elsewhere, point it at the tree:

```bash
export ORCA_TEMPLATES=/path/to/orca-compound-scripts
```

## Usage

Run `preporca.py` from a directory containing your `.xyz` file. It copies the chosen
template in, sets the molecule / charge / multiplicity, and writes `<name>.inp`
(a `%Compound` wrapper). Run that `.inp` with ORCA as usual.

Guided (interactive) — walks you through job type, functional style, and charge/multiplicity:

```bash
cd my_job/            # contains mol.xyz
python preporca.py
```

Direct (non-interactive):

```bash
python preporca.py -t opt -s native -c 0 -m 1
orca mol.inp > mol.out
```

### Example — transition state with a constrained pre-opt

```bash
mkdir ts_job && cd ts_job
cp /path/to/guess.xyz .
python preporca.py -t ts2-dft -s native -c 0 -m 1 --constraints "B 12 34; B 12 40"
orca guess.inp > guess.out
```

`ts2-dft` freezes the two bonds you name (0-based atom indices), runs a constrained
pre-optimization to build a Hessian, then an OptTS + frequency job.

### Multiple structures

Put several `.xyz` files in one directory; `preporca.py` builds one job folder per file.

## Templates

| alias        | workflow                                             |
|--------------|------------------------------------------------------|
| `opt`        | optimization + frequencies                           |
| `opt-sp`     | opt + high-level single point                        |
| `opt-wfs`    | UKS opt + wavefunction-stability check + re-opt      |
| `ts`         | OptTS + frequencies (from a good guess)              |
| `ts-sp`      | TS + high-level single point                         |
| `ts2-dft`    | constrained pre-opt (DFT) → OptTS                    |
| `ts2-sp-dft` | ts2 + high-level single point                        |
| `ts2-irc-dft`| ts2 + single point + IRC                             |
| `ts2-wfs-dft`| ts2 + stability check + re-opt + single point        |
| `goat-opt`   | GOAT conformer search → opt                          |
| `irc`        | IRC from an existing TS                              |
| `sp`         | high-level single point                              |
| `sp-dlpno`   | DLPNO-CCSD(T) single point                           |
| `freq-sp`    | frequencies + single point (no optimization)         |
| `ecd`        | TD-DFT ECD (rotatory strengths)                      |

`xtb` variants (e.g. `ts2-xtb`) use a GFN2-xTB constrained pre-opt instead of DFT.
For the full list type `?` in the wizard, or run `python preporca.py --help`.

## Notes

- Every optimization/TS template runs a frequency job and reports a clean
  thermochemistry summary; single-point-bearing templates apply the correction at
  the high level.
- Solvation defaults to CPCM/SMD (diethyl ether) and is edited per job in the `.cmp`
  or in bulk with `change_method.py`.
