![image](https://github.com/user-attachments/assets/11ac314c-7c55-4f2b-8bc9-652954aea65c)[![Python package](https://github.com/BhallaLab/moose-core/actions/workflows/pymoose.yml/badge.svg)](https://github.com/BhallaLab/moose-core/actions/workflows/pymoose.yml)

# MOOSE

MOOSE is the Multiscale Object-Oriented Simulation Environment. It is designed
to simulate neural systems ranging from subcellular components and biochemical
reactions to complex models of single neurons, circuits, and large networks. 
MOOSE can operate at many levels of detail, from stochastic chemical 
computations, to multicompartment single-neuron models, to spiking neuron
network models.

MOOSE is multiscale: It can do all these calculations together. For example
it handles interactions seamlessly between electrical and chemical signaling.
MOOSE is object-oriented. Biological concepts are mapped into classes, and
a model is built by creating instances of these classes and connecting them
by messages. MOOSE also has classes whose job is to take over difficult
computations in a certain domain, and do them fast. There are such solver
classes for stochastic and deterministic chemistry, for diffusion, and for 
multicompartment neuronal models.

MOOSE is a simulation environment, not just a numerical engine: It provides
data representations and solvers (of course!), but also a scripting interface
with Python, graphical displays with Matplotlib, PyQt, and VPython, and 
support for many model formats. These include SBML, NeuroML, GENESIS kkit 
and cell.p formats, HDF5 and NSDF for data writing.

This is the core computational engine of [MOOSE
simulator](https://github.com/BhallaLab/moose). This repository
contains C++ codebase and python interface called `pymoose`. For more
details about MOOSE simulator, visit https://moose.ncbs.res.in .


----------
# Installation

See [INSTALL.md](INSTALL.md) for instructions on installation.

Have a look at examples, tutorials and demo here
https://github.com/BhallaLab/moose-examples.

# Build 

To build `pymoose`, follow instructions given in
[INSTALL.md](INSTALL.md) and for platform specific
information see:
- Linux: [UbuntuBuild.md](UbuntuBuild.md)
- MacOSX: [AppleM1Build.md](AppleM1Build.md)
- Windows: [WindowsBuild.md](WindowsBuild.md)

# ABOUT VERSION 4.1.1, `Jhangri`

[`Jhangri`](https://en.wikipedia.org/wiki/Imarti) is an Indian sweet
in the shape of a flower. It is made of white-lentil (*Vigna mungo*)
batter, deep-fried in ornamental shape to form the crunchy, golden
body, which is then soaked in sugar syrup lightly flavoured with
spices.

This release has the following changes:

# New Features
1.  Formula-based versions of HH-type channels 
     - Added `HHChannelF` and `HHGateF` for formula-based evaluation of Hodgkin-Huxley type gating parameters
     - Added a formula interface for `HHGate`: Users can now assign string formula in `exprtk` syntax to `alphaExpr`, `betaExpr`, `tauExpr` and `infExpr` to fill up the               tables. These can take either `v` for voltage or `c` for concentration as independent variable names in the formula.
2. Added `moose.sysfields` to display system fields like `fieldIndex`, `numData` etc. 
3. Reintroduced `moose.neighbors()` function to retrieve neighbors on a particular field. This allows more flexibility than `element.neighbors[fieldName]` by allowing the user to specify the message type ("Single", "OneToOne", etc.) and direction (1 for incoming 0 for outgoing, otherwise both directions).

# API Updates
1. API changes in  `moose.vec` and `moose.element,` including updated documentation.
2. `moose.showfields` updated to 
 - skip system fields like `fieldIndex`, `numData` etc. These can now be printed using `sysfields` function.
 -  print common but informative fields like `name`, className`, `tick` and `dt` at the top.
 - return `None` instead of the output string to avoid cluttering the interactive session.
3. `moose.pwe()` returns `None` to avoid output clutter. Use `moose.getCwe()` for retrieving the current working element.
4. `children` field of moose elements (ObjId) now return a list of elements instead of vecs (Id). This brings consistency between `parent` and `children` fields.
5. `moose.le()` returns `None` to avoid output clutter. Use `element.children` field to access the list of children.
6. `path` field for elements (ObjId) now includes the index in brackets, as in the core C++. This avoids confusion with vec (Id) objects.
7. `moose.copy()` now accepts either `str` path or `element` or `vec` for `src` and `dest` parameters.
8. Attempt to access paths with non-existent element now consistently raises RuntimeError.
9. `moose.delete` now accepts vec (Id) as argument.



# Documentation
1. Updated `Ubuntu` build instructions for better clarity.
2. Enhanced documentation for `HHGate`, including additional warnings.
3. Updated documentation for `Stoich,` with improved code comments and clarifications.

# Bug Fixes
1. `bool` attribute handling added to `moose.vec`
2. More informative error message for unhandled attributes in `moose.vec`
3. Fixed issue #505
4. `moose.setCwe()` now handles str, element (ObjId) and vec (Id) parameters correctly
5. fixed `moose.showmsg()` mixing up incoming and outgoing messages.


   
# LICENSE

MOOSE is released under GPLv3.


