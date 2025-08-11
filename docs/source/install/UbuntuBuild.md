# Building MOOSE on Ubuntu (possibly in WSL)
0. Install GNU build tools

```
sudo apt install build-essential
```

## Building with system Python

1. Install the dependencies
```
sudo apt-get install ninja meson pkg-config python-pip python-numpy libgsl-dev g++ pybind11 libz-dev
pip install meson-python
pip install python-libsbml
pip install pyneuroml
pip install vpython
```

2. Now use `pip` to download and install `pymoose` from the [github repository](https://github.com/MooseNeuro/moose-core).

```
$ pip install git+https://github.com/MooseNeuro/moose-core --user
```

## Building with conda or variants
1. Install conda/mamba/micromamba (in all the commands below `conda` can be replaced by `mamba` or `micromamba` respectively). See https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html to find how to install conda or its variants. 

2. Create an environment with required packages

```
conda create -n moose ninja meson meson-python gsl hdf5 numpy matplotlib vpython doxygen pybind11[global] pkg-config -c conda-forge
```

3. Activate the environment

```
conda activate moose
```

## After the above steps, for both system Python and conda environment
4. Clone `moose-core` source code using git
```
    $ git clone https://github.com/MooseNeuro/moose-core --depth 50 
```
5. Build moose
```
cd moose-core

meson setup --wipe _build -Duse_mpi=false -Dbuildtype=release
meson compile -v -C _build 
meson install -C _build
```

This will install `moose` module inside your environment's default module installation (usually `site-packages`) directory. This  requires write permission on the target directory. See below for local installation.

For standard installation you can also simply run `pip install .` (for system-wide installation if you have the permission) or `pip install . --user` (for local installation) in the `moose-core` directory.

Meson provides many builtin options: https://mesonbuild.com/Builtin-options.html. Meson options are supplied in the command line to `meson setup` in the format `-Doption=value`.

  - **Installation prefix**
    To install MOOSE in a custom location, you can pass the `--prefix` argument to `meson setup`. For example, if you are in the `moose-core` directory, and want to have it installed in `_build_install` subdirectory, you can use
	```
    meson setup --wipe _build --prefix=`pwd`/_build_install -Duse_mpi=false -Dbuildtype=release
	```
	But then to let Python find this custom location, you must add the directory containing `moose` under `_build_install` in your `PYTHONPATH` environment variable. In `bash` shell, this would be:
	```
	export PYTHONPATH="$PYTHONPATH:`pwd`/_buid_install/Lib/site-packages"
	```
	
  - **Buildtype**

	If you want a developement build with debug enabled, pass `-Dbuildtype=debug` in the `meson setup ...` command line.


	```
	meson setup --wipe _build --prefix=`pwd`/_build_install -Duse_mpi=false -Dbuildtype=debug -Ddebug=true
	```

	You can either use `buildtype` option alone or use the two options `debug` and `optimization` for finer grained control over the build. According to `meson` documentation `-Dbuildtype=debug` will create a debug build with optimization level 0 (i.e., no optimization, passing `-O0 -g` to GCC), `-Dbuildtype=debugoptimized`  will create a debug build with optimization level 2 (equivalent to `-Ddebug=true -Doptimization=2`), `-Dbuildtype=release` will create a release build with optimization level 3 (equivalent to `-Ddebug=false -Doptimization=3`), and `-Dbuildtype=minsize` will create a release build with space optimization (passing `-Os` to GCC).
	
  - **Optimization level**
	
	To set optimization level, pass `-Doptimization=level`, where level can be `plain`, `0`, `g`, `1`, `2`, `3`, `s`.

6. For a Python development build so that your edits to the Python source code are included, run:

```
python -m pip install --no-build-isolation --editable .
```

7. To build a wheel (for distribution), run `pip wheel` command in the `moose-core` directory:
```
 pip wheel -w dist .
 ```
This weel create the `pymoose-{version}-{python}-{abi}-{os}_{arch}.whl` wheel file in the `moose-core/dist` directory. This can installed with 
```
pip install dist/pymoose-{version}-{python}-{abi}-{os}_{arch}.whl
```

## Development build with `meson` and `ninja`

`pip`  builds `pymoose` with default options, it runs `meson` behind the scene.
If you are developing moose, want to build it with different options, or need to test
and profile it, `meson` and `ninja` based flow is recommended.

Install the required dependencies and download the latest source code of moose
from github.

```
    $ git clone https://github.com/MooseNeuro/moose-core --depth 50 
    $ cd moose-core
    $ meson setup --wipe _build --prefix=`pwd`/_build_install -Duse_mpi=false -Dbuildtype=release
    $ ninja -v -C _build 
	$ meson install -C _build
```

This will build moose in `moose-core/_build` directory and install it as a Python package in the `moose-core/_build_install` directory.

To do a clean rebuild, delete the `_build` directory and the generated `_build_install/` directory and continue the steps above starting with `meson setup ...`.

To make in debug mode replace the option `-Dbuildtype=release` with `-Dbuildtype=debug`

