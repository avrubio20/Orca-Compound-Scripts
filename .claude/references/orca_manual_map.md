# ORCA 6.1.1 Manual — section map (pipeline-relevant)

Navigation aid for `orca-manual-rag`. The **section numbers** below are the
authoritative anchor — find the body in the live online manual at
`https://orca-manual.mpi-muelheim.mpg.de`. The local PDF
(`~/Documents/Manuals/ORCA 6.1.1 Manual — ORCA 6.1.1 Manual.pdf`, 112 pp)
is the **table of contents + quickstart only** — use it to resolve a topic
to its section number, not to read section bodies.

`[TOC p.N]` = page in the local PDF where that section is listed.
Grep the dumped TOC text with: `pdftotext "<pdf>" /tmp/orca_manual.txt`.

## Compound scripts (the .cmp language) — PRIMARY
  Online body: `contents/workflowsautomatization/compounddetails.html`
  (under host `https://orca-manual.mpi-muelheim.mpg.de`; the chapter index is
  `.../workflowsautomatization/index_workflowsautomatization.html`).
  NOTE: WebFetch fails on this host's TLS cert ("unable to verify the first
  certificate") — fetch with `curl -sk` instead, then strip tags.
- §8.2  Compound — block syntax, `New_Step`/`Step_End`, `Variable`, `&{}`   [TOC p.~]
- §8.3  More Details on Compound — `Read_Geom`, `ReadMOs`, control flow, `readProperty`
- §8.3.1.51 **ReadProperty** — `compounddetails.html#readproperty`   [TOC p.40]
  syntax: `[res=] readProperty(propertyName=, [stepID=], [filename=], [baseProperty=])`;
  res = property index or -1 if not found.
- §8.3.2 **List of known Properties** (Table 8.2) — `compounddetails.html#list-of-known-properties`
  Energy props + dispersion semantics (verified vs real .property.txt fields):
    • `DFT_TOTAL_EN` = `$DFT_Energy/&finalEn`, "DFT Total energy" — bare KS-DFT,
      field annotated "No Van der Waals correction" → **EXCLUDES** D3/D4 dispersion.
    • `VDW_CORRECTION` = the D3/D4 dispersion term itself (additive post-SCF).
    • `SCF_ENERGY` = bare SCF; `DFT_NON_LOC_EN` = VV10/NL term (`eCNL`).
    • dispersion-inclusive total for a DFT SP = `DFT_TOTAL_EN + VDW_CORRECTION`
      ( == FINAL SINGLE POINT ENERGY, per §3.4 "automatically included in the FSPE").
    • `MP2_TOTAL_ENERGY` = SCF+MP2; `MDCI_TOTAL_ENERGY` = SCF+Corr (add VDW_CORRECTION
      separately if D3/D4 on — UNVERIFIED whether these "totals" already include disp).
    • `THERMO_ELEC_ENERGY` (Freq only) = electronic energy = FSPE → INCLUDES dispersion.
- §8.4  Compound Examples — worked multi-step scripts
- §1.3.1.18 / §1.3.2.5  Compound (quickstart cross-refs)

## Functionals & libXC
- §3.3.6    LibXC Functional Library
- §3.3.6.2  Modifying LibXC Functional Parameters
- §3.3.6.3  **Simple Input of LibXC Functionals** ← key to native/libxc unification
- §3.4      Dispersion Corrections; §3.4.1 D3/D4; §3.4.2 VV10 / DFT-NL (non-local)
            — `contents/modelchemistries/dispersioncorrections.html`. Eq.(3.9):
            E_DFT-D = E_KS-DFT + E_disp; "automatically included in the FINAL
            SINGLE POINT ENERGY". (TOC lines 416-429)

## Basis & RI
- §2.7.2.3  Karlsruhe def2 Basis Sets
- §2.7.4.1  Coulomb-fitting aux (AuxJ → `def2/J`)
- §2.7.4.2  Coulomb+exchange aux (AuxJK → `def2/JK`)
- §2.7.4.3  Correlation aux (AuxC → `def2-TZVPP/C`)
- §2.7.4.5  AutoAux
- §2.7.11   Which Methods Need Which Basis Sets?
- §2.8.4    RIJCOSX; §2.8.4.3 COSX grids; §2.8.4.7 COSX convergence; §2.8.6 RIJCOSX vs RI-JK

## SCF, grids, initial guess
- §2.6.1    SCF Convergence Tolerances (TightSCF etc.)
- §2.6.9    Tips & Tricks: Converging SCF
- §1.7.13.1 Converging DFT for Open-Shell Transition Metals  ← Fe catalysts
- §2.10.3   The DEFGRIDs (DEFGRID3 etc.); §2.10.5 SCF grid keyword list
- §2.20     Choice of Initial Guess and Restart of SCF (PModel / PAtom / Hueckel)
- §2.20.8   Automatically Breaking Initial-Guess Symmetry (broken-symmetry start)

## Solvation
- §2.13.1.4 CPCM term options
- §2.13.2   COSMO
- §2.13.3   **The SMD Solvation Model** ← bang-line `SMD(...)` vs `%cpcm SMD true` block
- §2.13.7   Complete keyword list for the `%cpcm` block

## Geometry opt / TS / Hessian / freq / IRC
- §4.1      Geometry Optimizations; §4.1.1.1 thresholds; §4.1.13 keyword list
- §4.1.2    Initial Hessian for Minimization; §4.1.8 Model Hessian from previous calc
- §4.3.2.1  Hessians for Transition State Calculations (InHess Read)
- §4.3.4    Hybrid Hessian; §4.3.5 Partial Hessian
- §4.5      Nudged Elastic Band (NEB)
- §4.8      Conical Intersections (excited-state CI; gradient projection / branching plane)   [TOC p.21]
- §4.9      **Minimum Energy Crossing Points (MECP)** — spin-crossing optimizer; `! SurfCrossOpt`,
            `%mecp` block (`Mult`=PES2 multiplicity, `brokenSym`, `moinp`, casscf_*), Harvey penalty
            scheme g_SC=g+f, two SCF/step; `! SurfCrossNumFreq` effective Hessian. §4.9.1 Keywords   [TOC p.21]
- §4.6      Vibrational Frequencies; §4.6.4 keyword list
- §4.7      Thermochemistry (the THERMO_* properties)
- §1.7.14.1 Imaginary Frequencies after Optimization
- (IRC) keyword block `%irc` — confirm exact subkeywords (MaxIter, Direction,
  Monitor_Internals) against the live manual; section number TBD, add when found.

## GOAT (conformer/ensemble)
- §4.10     GOAT: global optimization & ensemble generator; §4.10.1 usage example
- §4.10.7   GOAT-REACT (reaction pathway); §4.10.8 GOAT-DIVERSITY; §4.10.9 GOAT-COARSE
- §4.10.10.2 Parallelization of GOAT (goat_nworkers)

## DLPNO coupled cluster
- §3.10     Coupled Cluster and CI (MDCI)
- §3.10.10  Local correlation (DLPNO) — DLPNO-CCSD(T), (T0)/(T1), TightPNO
- §3.10.3   Coupled-Cluster densities

## xtb module
- §1.2.4    How do I install the xtb module?
- (`%xtb XTBINPUTSTRING`, GFN2 vs g-xTB capabilities) — confirm against live
  manual / xtb docs; add section number when found.

## Troubleshooting
- §1.7.13   SCF Convergence Problems
- §1.7.14   Troublesome Geometry Optimizations; §1.7.14.3 convergence issues

---
*Grow this map: when `orca-manual-rag` resolves a section not listed here,
add it (number, title, and online anchor) and note the addition in the reply.*
