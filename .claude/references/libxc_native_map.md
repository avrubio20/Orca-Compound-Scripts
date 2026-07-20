# native vs libXC functional specification — verified facts & the unification question

Why two script trees exist, what ORCA 6.1.1 actually accepts, and whether
they can be merged. All syntax below is verified against the ORCA 6.1.1
manual (FACCTS 6.1 mirror, byte-identical text). Citations at the end.

---

## The two trees today

| | functional token | bang line | extra block |
|---|---|---|---|
| `native/` | ORCA keyword, e.g. `wB97X-D3BJ` | `! Opt Freq &{method_opt} &{basis_opt} …` | none |
| `libxc/`  | libXC registry name, e.g. `hyb_gga_xc_wb97x_v` | `! Opt Freq &{basis_opt} …` (no functional) | `%method`/`Method DFT`/`Functional &{method_opt}`/`end` |

## What ORCA 6.1.1 actually accepts (verified)

1. **Raw libXC names require the block form.** `%method Functional
   <libxc_name> end` accepts the combined name directly (no extra "LibXC"
   sub-keyword). Naming: `_x_` exchange, `_c_` correlation, `_xc_`
   combined. Separate parts via `Exchange <…_x_…>` + `Correlation
   <…_c_…>`. Discover names with `orca -libxcfunctionals` /
   `orca -libxcinfo <name>`.   (§3.3.6, §3.3.6.3)

2. **Simple-input `!LibXC(Keyword)` does NOT help unify.** It exists
   (`! LibXC(TPSS)`) but only exposes the subset of libXC functionals
   that *already have native ORCA keywords*, and the keyword matches the
   native one. The whole reason to use the libXC tree is to reach
   functionals that have **no** native keyword — those only work via the
   `%method` block. So `!LibXC(...)` is not a route to a single tree.

3. **The block form also accepts native functionals.** `%method
   Functional wB97X end` works for ORCA-native functionals too — BUT the
   token is the bare functional enum; the dispersion suffix (`-D3BJ`,
   `-D4`) is NOT part of the `Functional` token and must be requested
   separately (a `D3BJ`/`D4` keyword on the bang line or in `param_*`).

4. **libXC `_v` / VV10 functionals carry their own non-local
   correlation.** Do NOT add a D3/D4 dispersion keyword on top — that
   double-counts. (e.g. `hyb_gga_xc_wb97x_v` already includes VV10.)

## The unification option (one tree instead of two)

A single tree is technically possible by standardizing on the **block
form for both styles**:

```
! Opt Freq &{basis_opt} &{param_opt} &{solv_opt} PModel
%method
  Method     DFT
  Functional &{method_opt}      # native enum OR libXC name — change_method.py swaps it
end
```

- `change_method.py` would flip `method_opt` between, e.g., `"wB97X"`
  (native) and `"hyb_gga_xc_wb97x_v"` (libXC) with no structural edit.
- **Cost of unifying:** dispersion must leave the functional token. Today
  native uses the composite `wB97X-D3BJ`; under one tree that becomes
  `method_opt="wB97X"` + a `D3BJ` token in `param_opt`. For libXC `_v`
  functionals, no dispersion token (VV10 built in). So `param_*` becomes
  style-dependent — which partly relocates the divergence rather than
  removing it.
- **Verdict:** not strictly simpler. It trades "two trees, one method
  block differs" for "one tree, but dispersion handling differs per
  functional and lives in param_*". Recommend keeping two trees with the
  single documented divergence (cmp_conventions §6) UNLESS the
  maintenance of mirrored trees becomes the bigger pain. This is a
  judgment call for the user; `orca-dft-specialist` should weigh in on
  the dispersion-token ergonomics before committing.

## Solvation syntax (verified) — resolves the repo's open item

- **`! CPCM(solvent)`** — valid bang-line. (§2.13.1)
- **`! SMD(solvent)`** — valid bang-line, standalone. *"invoked in the
  input file via `! SMD(solvent)`."* (§2.13.3)
  → So `solv_* = "SMD(chloroform)"` on the bang line is **correct**, not a
  bug. The `sp.cmp` / `opt-WFS-reopt-sp.cmp` usage is fine.
  → `sp-dlpno.cmp`'s explicit `! CPCM(s)` + `%cpcm smd true SMDsolvent
  "s" end` block is the equivalent long form; it can be conformed to the
  composite `solv_sp = "SMD(diethylether)"` (confirm SMD-on-CC behavior
  with `orca-dft-specialist`; SMD applies to the SCF/HF reference —
  §2.13.6 Implicit Solvation in Coupled-Cluster).
- Solvent tokens are shared across CPCM/SMD/ALPB: `water` (`h2o`),
  `chloroform` (`chcl3`), `diethylether` (one word).

## Initial guess (verified) — resolves the PModel question

- ORCA's **default guess is `PAtom`** (STO-3G atomic densities), not
  PModel.
- `PModel` = superposition of precomputed spherical neutral-atom
  densities; HF & DFT; most of the periodic table; overhead *"usually
  less than one SCF iteration"*; *"the method of choice (particularly for
  molecules containing heavy elements) unless you have more accurate
  starting orbitals."*
- → Keep `PModel` on the **first DFT step after an xtb seed** (no
  transferable MOs, and we have an Fe heavy element). Its cost is
  negligible; removing it saves ~nothing and is mildly worse for Fe.
  Later iterations correctly `ReadMOs`. (§2.20)

## xtb engines (verified) — resolves the seed/TS engine question

- **GFNn-xTB** runs through the native `%xtb` / otool_xtb interface
  (keywords `XTB2`/`GFN2-xTB`, etc.; `XTBINPUTSTRING` only forwards extra
  args). Supports SP, gradient, **Opt**, numerical **Freq**, NEB, IRC,
  MD. Solvation: ALPB / ddCOSMO / CPCM-X (`DOALPB` etc.). (§3.5.2)
- **g-xTB** is a SEPARATE mechanism — the generic external-tools wrapper
  (`! ExtOpt` + ORCA-External-Tools script), **numerical gradients**,
  *"slowing down applications that compute gradients often like GOAT"*,
  preliminary, Linux-only, **no documented solvation**.
- → For a coordinate-capture **seed SP**, g-xTB is fine (energy only) but
  the solvent model is wasted (and undocumented for g-xTB anyway) — drop
  seed solvation. For **TS / opt / pre-opt**, use **GFN2-xTB** (analytic
  gradients, real Opt+Freq); g-xTB's numerical gradients make it slow and
  noisy there. Matches the user's guidance.
- ⚠ Latent check: the seed uses `! XTB2` + `%xtb XTBINPUTSTRING
  "--gxtb …"`. Per the manual, `--gxtb` is not an otool_xtb flag — g-xTB
  is a different driver. Confirm the seed is actually invoking g-xTB on
  this workstation (a custom otool_xtb wrapper may accept `--gxtb`); if
  not, the seed has been silently running GFN2 the whole time. Route to
  the user / `orca-cmp-engineer` to verify locally.

---

### Citations (ORCA 6.1.1, FACCTS 6.1 mirror — same text)
- LibXC: §3.3.6 / §3.3.6.3 — modelchemistries/DensityFunctionalTheory.html
- Solvation: §2.13.1 / §2.13.3 / §2.13.6 — essentialelements/solvationmodels.html
- Initial guess: §2.20 — essentialelements/initialguess.html
- xtb / semiempirical: §3.5.2 — modelchemistries/semiempirical.html
- g-xTB external tools: tutorials/workflows/extopt.html
- CPCMX gradient limitation: detailed change log appendix
