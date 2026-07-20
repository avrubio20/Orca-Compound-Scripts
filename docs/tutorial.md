# Tutorial

This walks through generating and running a few common jobs. It assumes ORCA is
installed and you have an `.xyz` in your working folder. Run `preporca.py` with no
flags to launch the guided wizard, or pass `-t <alias>` to skip it and go straight
to a template.

## The interactive wizard

Run from a folder containing your `.xyz`. The wizard asks the functional style
(`native` or `libxc`), then the job type (1–5), collects charge and multiplicity,
and for the constrained-TS and IRC templates prompts for the internal coordinates
to freeze or monitor. It then writes `<name>.inp` (a `%Compound "<template>.cmp"`
wrapper with molecule/charge/multi filled in) alongside a copy of the template
`.cmp`, and prints a summary box. At the job-type prompt, `?` shows the full
template menu and `q` quits.

## Optimization — `opt`

Minimum-energy geometry optimization followed by a frequency check. Use it to
relax a structure and confirm it's a true minimum.

Interactive (`preporca.py` with no flags, run from a folder containing your `.xyz`):

    Which functional style?
      1) native      (! line keyword; ORCA built-in names, e.g. B3LYP D3BJ)
      2) libxc       (%method block; libxc functional names, e.g. hyb_gga_xc_wb97x_v)
    > 1                       # native ! line keywords

    What kind of ORCA job do you want to set up?
      1) Minimum optimization
      2) Transition state (TS)
      3) Conformer search (GOAT)
      4) IRC (post-TS)
      5) Single point only
      -- type alias directly to skip wizard, '?' for full menu, 'q' to quit
    > 1                       # minimum optimization

    Add anything after opt?
      1) Just opt + Freq
      2) + HL-SP
      3) UKS opt + WFS + reopt + SP
    > 1                       # opt + Freq only

    Enter the molecular charge: 0
    Enter the spin multiplicity: 1
    ✅ mol.xyz  →  mol.inp

Or in one line:

    preporca.py -t opt -s native -c 0 -m 1

Choice 2 = `opt-sp` (adds a high-level single point); choice 3 = `opt-wfs`.

Produces `mol.inp` + `orca.01.opt.cmp`. Run it:

    orca mol.inp > mol.out

## Transition state from a guess — `ts`

Optimizes a transition state directly from a good guess geometry (OptTS + Freq),
no constrained pre-opt. Use it when your `.xyz` is already a clean TS-like
structure.

Interactive (`preporca.py` with no flags, run from a folder containing your `.xyz`):

    Which functional style?
      1) native      (! line keyword; ORCA built-in names, e.g. B3LYP D3BJ)
      2) libxc       (%method block; libxc functional names, e.g. hyb_gga_xc_wb97x_v)
    > 1                       # native ! line keywords

    What kind of ORCA job do you want to set up?
      1) Minimum optimization
      2) Transition state (TS)
      3) Conformer search (GOAT)
      4) IRC (post-TS)
      5) Single point only
      -- type alias directly to skip wizard, '?' for full menu, 'q' to quit
    > 2                       # transition state

    Need constrained pre-opt? (recommended unless geometry is clean TS-like)
      1) Yes
      2) No
    > 2                       # clean TS guess, skip pre-opt

    Add HL-SP after TS?
      1) No
      2) Yes
    > 1                       # TS + Freq only

    Enter the molecular charge: 0
    Enter the spin multiplicity: 1

Or in one line:

    preporca.py -t ts -s native -c 0 -m 1

Choosing HL-SP gives `ts-sp`.

Produces `<name>.inp` + `orca.04.ts.cmp`. Run it:

    orca <name>.inp > <name>.out

## Transition state via constrained pre-opt — `ts2-dft`

Freezes the named bonds to build a Hessian, then runs OptTS + Freq. Use it when you don't already have a clean TS guess.

Interactive (`preporca.py` with no flags, run from a folder containing your `.xyz`):

    Which functional style?
      1) native      (! line keyword; ORCA built-in names, e.g. B3LYP D3BJ)
      2) libxc       (%method block; libxc functional names, e.g. hyb_gga_xc_wb97x_v)
    > 1

    What kind of ORCA job do you want to set up?
      1) Minimum optimization
      2) Transition state (TS)
      3) Conformer search (GOAT)
      4) IRC (post-TS)
      5) Single point only
      -- type alias directly to skip wizard, '?' for full menu, 'q' to quit
    > 2

    Need constrained pre-opt? (recommended unless geometry is clean TS-like)
      1) Yes
      2) No
    > 1

    Pre-opt engine?
      1) xTB
      2) DFT
    > 2                                   # engine choice 1 = xTB -> ts2-xtb

    What comes after the TS step?
      1) Just TS + Freq
      2) + HL-SP
      3) + HL-SP + IRC
      4) + WFS + reopt + SP
    > 1

    Enter the molecular charge: 0
    Enter the spin multiplicity: 1

    Constraint mode active for template 'orca.01.co-ts.dft.cmp'.
    Define constraints below (guided entry):

    [1] Type (B/A/D/C, blank to finish): B
    [1] Atom numbers (space-separated): 0 1
    [1] Extra tokens (default = C): 
    [2] Type (B/A/D/C, blank to finish): B
    [2] Atom numbers (space-separated): 0 2
    [2] Extra tokens (default = C): 
    [3] Type (B/A/D/C, blank to finish):    # blank Enter finishes the list

    Added 2 constraint(s).
    🔄 Replaced 2 Constraints block(s).

Or in one line:

    preporca.py -t ts2-dft -s native -c 0 -m 1 --constraints "B 0 1; B 0 2"

Produces `mol.inp` + `orca.01.co-ts.dft.cmp`. Run it:

    orca mol.inp > mol.out

## IRC from a transition state — `irc`

Starts from an already-optimized TS geometry (an `.xyz` of the TS) and follows the reaction coordinate; the monitor internals are the coordinate(s) to track.

Interactive (`preporca.py` with no flags, run from a folder containing your `.xyz`):

    Which functional style?
      1) native      (! line keyword; ORCA built-in names, e.g. B3LYP D3BJ)
      2) libxc       (%method block; libxc functional names, e.g. hyb_gga_xc_wb97x_v)
    > 1

    What kind of ORCA job do you want to set up?
      1) Minimum optimization
      2) Transition state (TS)
      3) Conformer search (GOAT)
      4) IRC (post-TS)
      5) Single point only
      -- type alias directly to skip wizard, '?' for full menu, 'q' to quit
    > 4

    Enter the molecular charge: 0
    Enter the spin multiplicity: 1

    Monitor_Internals block detected in 'orca.06.IRC.cmp'.
    Define monitor internals below (guided entry):

    [1] Type (B/A/D, blank to finish): B
    [1] Atom numbers (space-separated): 0 1
    [2] Type (B/A/D, blank to finish):      # blank Enter finishes the list

    Added 1 monitor(s).
    🔄 Replaced 1 Monitor_Internals block(s).

Or in one line:

    preporca.py -t irc -s native -c 0 -m 1 --monitors "B 0 1"

Produces `mol.inp` + `orca.06.IRC.cmp`. Run it:

    orca mol.inp > mol.out
