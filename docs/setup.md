# Setup

## Requirements

- **ORCA 6.1.1** — licensed and installed, with `orca` on your `PATH`.
- **Python 3.11+** — standard library only, no packages to install.

## Get the templates

```bash
git clone <repo-url> orca-compound-scripts
```

`preporca.py` finds the `native/` and `libxc/` trees automatically when it is run
from inside the repository. To call it from anywhere, point it at the tree:

```bash
export ORCA_TEMPLATES=/path/to/orca-compound-scripts    # add to ~/.bashrc to persist
```

Optionally put the generator on your `PATH`:

```bash
ln -s /path/to/orca-compound-scripts/preporca.py ~/bin/preporca.py
```

## Verify the install

```bash
mkdir /tmp/check && cd /tmp/check
printf "1\n\nH 0.0 0.0 0.0\n" > h.xyz
python /path/to/preporca.py -t sp -s native -c 0 -m 1 --no-prompt
# -> writes h.inp
orca h.inp > h.out
```

## How a job runs

For each `.xyz` in the working directory, `preporca.py` copies the chosen template in,
sets `molecule` / `charge` / `multi`, and writes `<name>.inp` — a one-line
`%Compound "<template>.cmp"` wrapper. Run that `.inp` with ORCA like any other input:

```bash
orca <name>.inp > <name>.out
```

Give it several `.xyz` files at once and it builds one job folder per structure.
