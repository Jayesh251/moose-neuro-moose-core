# -*- coding: utf-8 -*-
# test_function.py ---
# Filename: test_function.py
# Description:
# Author: subha
# Updated for exprtk based reimplementation of Function by: Dilawar Singh <diawars@ncbs.res.in>
# Created: Sat Mar 28 19:34:20 2015 (-0400)


from __future__ import print_function
import numpy as np
import moose


print(f"[INFO ] Using moose {moose.version()} from {moose.__file__}")


def create_func(funcname, expr):
    """Create a function element `funcname` and set its expression to `expr`.

    This also creates a table and connects it to the function to
    record its output value.

    Additionally, both the function clock and the table clock are set
    to dt=1.0.

    Returns
    -------
    (f, t): tuple
       f is the created Function object
       t is the Table object recording Function's evaluated value
    """
    f = moose.Function(funcname)
    f.expr = expr
    t = moose.Table(funcname + 'tab')
    moose.connect(t, 'requestOut', f, 'getValue')
    moose.setClock(f.tick, 0.1)
    moose.setClock(t.tick, 0.1)
    return f, t


def test_eval():
    """Test user invoked evaluation of the function.

    Also checks `xindex`, `allowUnknownVariable`, and named constants
    """
    f = moose.Function('/f_test_eval')
    f.c['A'] = 6.022e23
    assert f.allowUnknownVariable is True
    f.expr = '(mass / mw) * A'  # number of molecules
    i_mass = f.xindex['mass']
    i_mw = f.xindex['mw']
    f.x[i_mass].value = 1.0
    f.x[i_mw] = 180.156  # glucose
    expected = 3.343e21  # approx no. of molecules in 1 g glucose
    result = f.evalResult
    assert np.isclose(result, 3.343e21), f'Expected {expected}, got {result}'
    assert (
        f.doEvalAtReinit is False
    ), 'Expected default value of `doEvalAtReinit` to be False.'
    moose.reinit()
    assert np.isclose(
        f.value, 0.0
    ), f'Expected value to be set to 0 upon reinit, but got {f.value}'

def testAllowUnknownVariable():
    f = moose.Function('/f_testAllowUnknownVariable')
    f.allowUnknownVariable = False
    f.expr = '(mass / mw) * A'
    assert f.expr == ''

def test_var_order():
    """The y values are one step behind the x values because of
    scheduling sequences.
    
    """
    nsteps = 5
    simtime = nsteps
    dt = 1.0
    # fn0 = moose.Function('/fn0')
    fn1 = moose.Function('/fn1')
    fn1.expr = 'y1+y0+x1+x0'
    fn1.mode = 1
    inputs = np.arange(0, nsteps + 1, 1.0)
    x0 = moose.StimulusTable('/x0')
    x0.vector = inputs
    x0.startTime = 0.0
    x0.stopTime = simtime
    x0.stepPosition = 0.0
    print('x0', x0.vector)
    inputs /= 10
    x1 = moose.StimulusTable('/x1')
    x1.vector = inputs
    x1.startTime = 0.0
    x1.stopTime = simtime
    x1.stepPosition = 0.0
    print('x1', x1.vector)
    inputs /= 10
    y0 = moose.StimulusTable('/y0')
    y0.vector = inputs
    y0.startTime = 0.0
    y0.stopTime = simtime
    y0.stepPosition = 0.0
    print('y0', y0.vector)
    inputs /= 10
    y1 = moose.StimulusTable('/y1')
    y1.vector = inputs
    print('y1', y1.vector)
    y1.startTime = 0.0
    y1.startTime = 0.0
    y1.stopTime = simtime
    y1.stepPosition = 0.0
    #  print( fn1, type(fn1) )
    #  print( moose.showmsg(fn1.x) )
    moose.connect(x0, 'output', fn1.x[0], 'input')
    moose.connect(x1, 'output', fn1.x[1], 'input')
    moose.connect(fn1, 'requestOut', y0, 'getOutputValue')
    moose.connect(fn1, 'requestOut', y1, 'getOutputValue')
    z1 = moose.Table('/z1')
    moose.connect(z1, 'requestOut', fn1, 'getValue')
    for ii in range(32):
        moose.setClock(ii, dt)
    moose.reinit()
    moose.start(simtime)
    expected = [0, 0, 1.1, 2.211, 3.322, 4.433]  # first 0 is from eval at reinit, second is first process
    # print('sum: ', x0.vector + x1.vector + y0.vector + y1.vector)
    # print('got', z1.vector)
    assert np.allclose(z1.vector, expected), f"Expected {expected}, got {z1.vector}"
    print('Passed order vars')


def test_t():
    """Test the use of time `t` as a variable"""
    fn, tab = create_func('funct', 't/2.0')
    # fn.doEvalAtReinit = True
    moose.reinit()
    simtime = 1.0
    moose.start(simtime)
    # it should be [0, 0, 0.1/2, 0.2/2, 0.3/2, ..]
    expected = np.r_[0.0, np.arange(0, simtime, fn.dt)/2.0]
    assert np.allclose(tab.vector, expected), f'Expected {expected}, got {tab.vector}'
    print('Passed t/2')


def test_trigonometric():
    f, t = create_func('func2', '(sin(t)^2+cos(t)^2)-1')
    moose.reinit()
    moose.start(1)
    y = t.vector
    assert np.isclose(np.mean(y), 0.0), np.mean(y)
    assert np.isclose(np.std(y), 0.0), np.std(y)
    print('Passed sin^2 x + cos^x=1')


def test_rand():
    moose.seed(10)
    f, t = create_func('random', 'rnd()')
    f.doEvalAtReinit = True
    moose.reinit()
    moose.start(1000)
    assert (
        abs(np.mean(t.vector) - 0.5) < 0.01
    ), 'Mean is not close enough to 0.5'
    assert np.std(t.vector) < 0.3, 'Std is too high'
    # This is a pointless test - must have been explicitly listed by
    # using Function itself, because these skip intermediate values
    # which were getting generated by duplicate evaluation of Expr.
    
    # expected = [
    #     0,  # this is because table pulls one value before the function clock ticked 
    #     0.29876116,
    #     0.49458993,
    #     0.83191136,
    #     0.02517173,
    #     0.26556613,
    #     0.15037787,
    #     0.81660184,
    #     0.89081653,
    #     0.03061665,
    #     0.72743551,
    #     0.13145815,
    # ]
    # assert np.isclose(
    #     t.vector[: len(expected)], expected
    # ).all(), f"Expected {expected}, got {t.vector[:len(expected)]}"
    print('Passed test random')


def test_fmod():
    f, t = create_func('fmod', 'fmod(t, 2)')
    moose.reinit()
    moose.start(20)
    y = t.vector
    print(y)
    assert (np.fmod(y, 2) == y).all()
    assert np.isclose(np.max(y), 1.9), "Expected 1.9 got %s" % np.max(y)
    assert np.isclose(np.min(y), 0.0), "Expected 0.0 got %s" % np.min(y)
    print('Passed fmod(t,2)')


if __name__ == '__main__':
    test_var_order()
    test_t()
    test_trigonometric()
    test_rand()
    test_fmod()
