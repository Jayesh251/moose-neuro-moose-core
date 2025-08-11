# Installing MOOSE

MOOSE (Multiscale Object-Oriented Simulation Environment) is a neural simulation framework that requires GSL (GNU Scientific Library) and HDF5 libraries as dependencies.

## Installing released version from PyPI using `pip`

MOOSE is available on PyPI. But it depends on GSL (GNU Scientific Library) and HDF5 libraries, which are not easily available on all platforms. If you are using Linux or MacOS, you can install these on your system, and then to install the latest release of MOOSE for your system Python, run:

```bash
pip install pymoose
```

If you are using MS Windows or want to keep things separate from your system Python, it is better to create a separate environment with conda/mamba/micromamba/miniforge. The channel `conda-forge` has these libraries for all three platforms. The commands are:

```bash
conda create -n moose gsl hdf5 numpy vpython matplotlib -c conda-forge
conda activate moose
pip install pymoose
```

**What this does:**
- Creates an isolated environment named "moose" with all required dependencies
- Activates the environment to use it
- Installs MOOSE using pip within this environment

## Installing from a binary wheel using `pip`

Binary wheels for MOOSE are available on the [GitHub releases page](https://github.com/MooseNeuro/moose-core/releases). You can download a wheel suitable for your platform and install it directly with pip. 

### Understanding wheel filenames

The wheel filename indicates platform compatibility:
```
pymoose-{version}-{python-version}-{operating-system}_{architecture}.whl
```

**Example:**
```
pymoose-4.1.0.dev0-cp312-cp312-manylinux_2_28_x86_64.whl
```

This wheel is built for:
- CPython version 3.12 (`cp312`)
- Linux 64-bit Intel CPU (`manylinux_2_28_x86_64`)
- GSL 2.7 (check release notes for exact version)

### Installation steps

1. **Create a matching environment:**
   ```bash
   conda create -n moose python=3.12 gsl=2.7 numpy vpython matplotlib -c conda-forge
   ```
   
   > **Note**: Replace `conda` with `mamba` or `micromamba` if you prefer those tools for faster installation.

2. **Activate the environment:**
   ```bash
   conda activate moose
   ```

3. **Install the downloaded wheel:**
   ```bash
   pip install pymoose-4.1.0.dev0-cp312-cp312-manylinux_2_28_x86_64.whl
   ```

## Installing from source code in GitHub repository

To build MOOSE from source, you need build tools and development libraries. We recommend Python 3.9 or higher.

### Build requirements

Make sure these packages are installed on your system:
- `gsl-1.16` or higher
- `python-numpy`
- `pybind11` (if setup fails, try `pip install pybind11[global]`)
- `python-libsbml`
- `pyneuroml`
- `clang` compiler 18 or newer
- `meson`, `ninja`, `meson-python`
- `python-setuptools`, `pkg-config`

### Platform-specific instructions

For detailed platform instructions, see:
- **Linux**: [UbuntuBuild.md](UbuntuBuild.md)
- **macOS**: [AppleM1Build.md](AppleM1Build.md)
- **Windows**: [WindowsBuild.md](WindowsBuild.md)

### Installation commands

**Install from master branch:**
```bash
pip install git+https://github.com/MooseNeuro/moose-core --user
```

**Install from specific branch/fork:**
```bash
pip install git+https://github.com/subhacom/moose-core@fix495merge --user
```

This installs the `fix495merge` branch from subhacom's fork of moose-core.

## Post-installation verification

Check that MOOSE is installed and working correctly:

```bash
python -c "import moose; ch = moose.HHChannel('ch'); moose.le()"
```

**Expected output:**
```
Elements under /
    /Msgs
    /clock
    /classes
    /postmaster
    /ch
```

Now you can import moose in Python:

```python
import moose
```

## Troubleshooting

### Common issues

**Missing dependencies:**
- Use conda environment installation method
- Install with: `conda create -n moose gsl hdf5 numpy -c conda-forge`

**Permission errors:**
- Add `--user` flag: `pip install pymoose --user`
- Or use conda environment (recommended)

**Python version mismatch:**
- Ensure your Python version matches the wheel requirements
- Create environment with correct Python version

**Build errors (source installation):**
- Install missing build tools: `pip install meson ninja meson-python`
- Install dependencies: `pip install pybind11[global] numpy`

## Uninstall

**Remove MOOSE package:**
```bash
pip uninstall pymoose
```

**Remove conda environment:**
```bash
conda remove -n moose --all
```

> **Important**: When building from source, make sure to exit the source directory before uninstalling, or you may encounter:
> ```
> Found existing installation: pymoose {version}
> Can't uninstall 'pymoose'. No files were found to uninstall.
> ```
