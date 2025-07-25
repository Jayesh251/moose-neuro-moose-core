# -*- coding: utf-8 -*-
#########################################################################
## rdesigneur0_5.py ---
## This program is part of 'MOOSE', the
## Messaging Object Oriented Simulation Environment.
##           Copyright (C) 2014 Upinder S. Bhalla. and NCBS
## It is made available under the terms of the
## GNU General Public License version 2 or later.
## See the file COPYING.LIB for the full notice.
#########################################################################

##########################################################################
## This class builds models of
## Reaction-Diffusion and Electrical SIGnaling in NEURons.
## It loads in neuronal and chemical signaling models and embeds the
## latter in the former, including mapping entities like calcium and
## channel conductances, between them.
##########################################################################

import importlib
import os
import moose
import numpy as np
import math
import sys
import time
import matplotlib.pyplot as plt

class DummyRmoogli():
    def __init__(self):
        pass

    def makeMoogli( self, mooObj, args, fieldInfo ):
        return "Dummy"

    def displayMoogli( rd, _dt, _runtime, rotation = 0.0, fullscreen = False, azim = 0.0, elev = 0.0, mergeDisplays = False, center = [0.0, 0.0, 0.0], colormap = 'jet', bg = 'default' ):
        pass

    def notifySimulationEnd():
        pass

class AnimationEvent():
    def __init__(self, key, time):
        self.key = key
        self.time = time

try:
    import rdesigneur.rmoogli as rmoogli
except (ImportError, ModuleNotFoundError):
    rmoogli = DummyRmoogli()

from rdesigneur.rdesigneurProtos import *
import moose.fixXreacs as fixXreacs

from moose.neuroml.NeuroML import NeuroML
from moose.neuroml.ChannelML import ChannelML

# In python3, cElementTree is deprecated. We do not plan to support python <2.7
# in future, so other imports have been removed.
try:
  from lxml import etree
except ImportError:
  import xml.etree.ElementTree as etree

import csv

meshOrder = ['soma', 'dend', 'spine', 'psd', 'psd_dend', 'presyn_dend', 'presyn_spine', 'endo']

knownFieldsDefault = {
    'Vm':('CompartmentBase', 'getVm', 1000, 'Memb. Potential (mV)', -80.0, 40.0 ),
    'initVm':('CompartmentBase', 'getInitVm', 1000, 'Init. Memb. Potl (mV)', -80.0, 40.0 ),
    'Im':('CompartmentBase', 'getIm', 1e9, 'Memb. current (nA)', -10.0, 10.0 ),
    'inject':('CompartmentBase', 'getInject', 1e9, 'inject current (nA)', -10.0, 10.0 ),
    'Gbar':('ChanBase', 'getGbar', 1e9, 'chan max conductance (nS)', 0.0, 1.0 ),
    'Gk':('ChanBase', 'getGk', 1e9, 'chan conductance (nS)', 0.0, 1.0 ),
    'Ik':('ChanBase', 'getIk', 1e9, 'chan current (nA)', -10.0, 10.0 ),
    'ICa':('NMDAChan', 'getICa', 1e9, 'Ca current (nA)', -10.0, 10.0 ),
    'Ca':('CaConcBase', 'getCa', 1e3, 'Ca conc (uM)', 0.0, 10.0 ),
    'n':('PoolBase', 'getN', 1, '# of molecules', 0.0, 200.0 ),
    'conc':('PoolBase', 'getConc', 1000, 'Concentration (uM)', 0.0, 2.0 ),
    'volume':('PoolBase', 'getVolume', 1e18, 'Volume (um^3)' )
}

#EREST_ACT = -70e-3

def _profile(func):
    """
    Can be used to profile a function. Useful in debugging and profiling.
    Author: Dilawar Singh
    """
    def wrap(self=None, *args, **kwargs):
        t0 = time.time()
        result = func(self, *args, **kwargs)
        print("[INFO ] Took %s sec" % (time.time()-t0))
        return result
    return wrap
        

class BuildError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

#######################################################################
def dummyBuildFunction( rdes ):
    # Dummy function to be replaced by custom function to build something
    # within the rdes ambit, so that it can be used for plotting and for
    # dumping to file. Example could be a complex stimulus object
    # or a network layer for input.
    return

class rdesigneur:
    """The rdesigneur class is used to build models incorporating
    reaction-diffusion and electrical signaling in neurons.
    Params:
        useGssa: True/False               for GSSA in spine and PSD
        combineSegments: True/False       for NeuroML models
        diffusionLength: default 2e-6
        adaptCa: [( Ca_wildcard_string, chem_wildcard_string, offset, scale ),...]
        adaptChem: [( Chem_wildcard_string, elec_wildcard_string, offset, scale ),...]

    I need to put the extra channels now into the NeuroML definition.
    """
    ################################################################
    def __init__(self,
            modelPath = '/model',
            turnOffElec = False,
            useGssa = False,
            combineSegments = True,
            stealCellFromLibrary = False,
            verbose = True,
            benchmark = False,
            addSomaChemCompt = False,  # Put a soma chemCompt on neuroMesh
            addEndoChemCompt = False,  # Put an endo compartment, typically for ER, on each of the NeuroMesh compartments.
            diffusionLength= 2e-6,
            meshLambda = -1.0,    #This is a backward compatibility hack
            temperature = 32,
            chemDt= 0.1,            # Much finer than MOOSE, for multiscale
            diffDt= 0.01,           # 10x finer than MOOSE, for multiscale
            elecDt= 50e-6,          # Same default as from MOOSE
            chemPlotDt = 1.0,       # Same default as from MOOSE
            elecPlotDt = 0.1e-3,    # Same default as from MOOSE
            funcDt = 0.1e-3,        # Used when turnOffElec is False.
                                    # Otherwise system uses chemDt.
            statusDt = 0.0,         # Dt to print out status. 0 = no print
            numWaveFrames = 100,    # Number of frames to use for waveplots
            extraBuildFunction = dummyBuildFunction,
            cellProto = [],
            spineProto = [],
            chanProto = [],
            chemProto = [],
            passiveDistrib= [],
            spineDistrib= [],
            chanDistrib = [],
            chemDistrib = [],
            adaptorList= [],
            stimList = [],
            plotList = [],  # elecpath, geom_expr, object, field, title ['wave' [min max]]
            moogList = [], 
            outputFileList = [], # List of all file save specifications.
            modelFileNameList = [], # List of any files used to build.
            ode_method = "lsoda",  # gsl, lsoda, gssa, gillespie
            isLegacyMethod = False,
            params = None
        ):
        """ Constructor of the rdesigner. This just sets up internal fields
            for the model building, it doesn't actually create any objects.
        """

        self.modelPath = modelPath
        self.turnOffElec = turnOffElec
        self.useGssa = useGssa
        self.ode_method = ode_method
        self.combineSegments = combineSegments
        self.stealCellFromLibrary = stealCellFromLibrary
        self.verbose = verbose
        self.benchmark = benchmark
        self.addSomaChemCompt = addSomaChemCompt
        self.addEndoChemCompt = addEndoChemCompt
        self.diffusionLength= diffusionLength
        if meshLambda > 0.0:
            print("Warning: meshLambda argument is deprecated. Please use "
                    "'diffusionLength' instead.\nFor now rdesigneur will "
                    "accept this argument.")
            self.diffusionLength = meshLambda
        self.temperature = temperature
        self.chemDt= chemDt
        self.diffDt= diffDt
        self.elecDt= elecDt
        self.elecPlotDt= elecPlotDt
        self.funcDt= funcDt
        self.statusDt= statusDt
        self.chemPlotDt= chemPlotDt
        self.numWaveFrames = numWaveFrames
        self.isLegacyMethod = isLegacyMethod
        self.extraBuildFunction = extraBuildFunction

        self.cellProtoList = cellProto
        self.spineProtoList = spineProto
        self.chanProtoList = chanProto
        self.chemProtoList = chemProto

        self.passiveDistrib = passiveDistrib
        self.spineDistrib = spineDistrib
        self.chanDistrib = chanDistrib
        self.chemDistrib = chemDistrib
        self.modelFileNameList = modelFileNameList

        self.params = params

        self.adaptorList = adaptorList
        try:
            self.stimList = [ rstim.convertArg(i) for i in stimList ]
            self.plotList = [ rplot.convertArg(i) for i in plotList ]
            self.moogList = [ rmoog.convertArg(i) for i in moogList ]
            self.outputFileList = [ rfile.convertArg(i) for i in outputFileList ]
        except BuildError as msg:
            print("Error: rdesigneur: " + msg)
            quit()

        self.saveAs = []
        self.plotNames = []
        self.wavePlotNames = []
        self.saveNames = []
        self.moogNames = []
        self.fileDumpNames = []
        self.cellPortionElist = []
        self.spineComptElist = []
        self.tabForXML = []
        self._endos = []
        self.nsdfPathList = [] # List of paths of nsdf objects.
        self._finishedSaving = False

        if not moose.exists( '/library' ):
            library = moose.Neutral( '/library' )
        try:
            self.buildCellProto()
            self.buildChanProto()
            self.buildSpineProto()
            self.buildChemProto()
        except BuildError as msg:
            print("Error: rdesigneur: Prototype build failed:", msg)
            quit()


    ################################################################
    def _printModelStats( self ):
        if not self.verbose:
            return
        print("Rdesigneur: Elec model has",
            self.elecid.numCompartments, "compartments and",
            self.elecid.numSpines, "spines on",
            len( self.cellPortionElist ), "compartments.")
        if hasattr( self , 'chemid') and len( self.chemDistrib ) > 0:
            #  dmstoich = moose.element( self.dendCompt.path + '/stoich' )
            print("    Chem part of model has the following compartments: ")
            for j in moose.wildcardFind( '/model/chem/##[ISA=ChemCompt]'):
                s = moose.element( j.path + '/stoich' )
                print( "    | In {}, {} voxels X {} pools".format( j.name, j.mesh.num, s.numAllPools ) )

    def buildModel( self, modelPath = '/model' ):
        if moose.exists( modelPath ):
            print("rdesigneur::buildModel: Build failed. Model '",
                modelPath, "' already exists.")
            return
        self.model = moose.Neutral( modelPath )
        self.modelPath = modelPath
        funcs = [self.installCellFromProtos, self.buildPassiveDistrib
            , self.buildChanDistrib, self.buildSpineDistrib
            , self.buildChemDistrib
            , self._configureSolvers, self.buildAdaptors, self._buildStims
            , self._buildExtras
            , self._buildPlots, self._buildMoogli, self._buildFileOutput
            , self._configureHSolve
            , self._configureClocks, self._printModelStats]

        for i, _func in enumerate(funcs):
            if self.benchmark:
                print("- (%02d/%d) Executing %25s"%(i+1, len(funcs), _func.__name__), end=' ' )
            t0 = time.time()
            try:
                _func()
            except BuildError as msg:
                print("Error: rdesigneur: model build failed:", msg)
                moose.delete(self.model)
                return
            t = time.time() - t0
            if self.benchmark:
                msg = r'    ... DONE'
                if t > 0.01:
                    msg += ' %.3f sec' % t
                print(msg)
            sys.stdout.flush()
        if self.statusDt > min( self.elecDt, self.chemDt, self.diffDt ):
            pr = moose.PyRun( modelPath + '/updateStatus' )
            pr.initString = "_status_t0 = time.time()"
            pr.runString = '''
print( "Wall Clock Time = {:8.2f}, simtime = {:8.3f}".format( time.time() - _status_t0, moose.element( '/clock' ).currentTime ), flush=True )
'''
            moose.setClock( pr.tick, self.statusDt )

    def installCellFromProtos( self ):
        if self.stealCellFromLibrary:
            moose.move( self.elecid, self.model )
            if self.elecid.name != 'elec':
                self.elecid.name = 'elec'
        else:
            moose.copy( self.elecid, self.model, 'elec' )
            self.elecid = moose.element( self.model.path + '/elec' )
            self.elecid.buildSegmentTree() # rebuild: copy has happened.
        if hasattr( self, 'chemid' ):
            self.validateChem()
            if self.stealCellFromLibrary:
                moose.move( self.chemid, self.model )
                if self.chemid.name != 'chem':
                    self.chemid.name = 'chem'
            else:
                moose.copy( self.chemid, self.model, 'chem' )
                self.chemid = moose.element( self.model.path + '/chem' )

        ep = self.elecid.path
        somaList = moose.wildcardFind( ep + '/#oma#[ISA=CompartmentBase]' )
        if len( somaList ) == 0:
            somaList = moose.wildcardFind( ep + '/#[ISA=CompartmentBase]' )
        if len( somaList ) == 0:
            raise BuildError( "installCellFromProto: No soma found" )
        maxdia = 0.0
        for i in somaList:
            if ( i.diameter > maxdia ):
                self.soma = i

    ################################################################
    # Some utility functions for building prototypes.
    ################################################################
    # Return true if it is a function.
    def buildProtoFromFunction( self, func, protoName ):
        if callable( func ):
            func( protoName )
            return True
        bracePos = func.find( '()' )
        if bracePos == -1:
            return False

        # . can be in path name as well. Find the last dot which is most likely
        # to be the function name.
        modPos = func.rfind( "." )
        if ( modPos != -1 ): # Function is in a file, load and check
            resolvedPath = os.path.realpath( func[0:modPos] )
            pathTokens = resolvedPath.split('/')
            pathTokens = ['/'] + pathTokens
            modulePath = os.path.realpath(os.path.join(*pathTokens[:-1]))
            moduleName = pathTokens[-1]
            funcName = func[modPos+1:bracePos]
            # moduleFile, pathName, description = imp.find_module(moduleName, [modulePath])
            # `imp` has been deprecated and throws error in Python 3.12
            spec = importlib.machinery.PathFinder().find_spec(moduleName, [modulePath])
            try:
                # module = imp.load_module(moduleName, moduleFile, pathName, description)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                funcObj = getattr(module, funcName)
                funcObj(protoName)
                return True
            finally:
              pass
                # moduleFile.close()
            return False
        if not func[0:bracePos] in globals():
            raise BuildError( \
                protoName + " Proto: global function '" +func+"' not known.")
        globals().get( func[0:bracePos] )( protoName )
        return True

    # Class or file options. True if extension is found in
    def isKnownClassOrFile( self, name, suffices ):
        for i in suffices:
            if name.rfind( '.'+i ) >= 0 :
                return True
        return False



    # Checks all protos, builds them and return true. If it was a file
    # then it has to return false and invite the calling function to build
    # If it fails then the exception takes over.
    def checkAndBuildProto( self, protoType, protoVec, knownClasses, knownFileTypes ):
        if len(protoVec) != 2:
            raise BuildError( \
                protoType + "Proto: nargs should be 2, is " + \
                    str( len(protoVec)  ))
        if moose.exists( '/library/' + protoVec[1] ):
            # Assume the job is already done, just skip it.
            return True
            '''
            raise BuildError( \
                protoType + "Proto: object /library/" + \
                    protoVec[1] + " already exists." )
            '''
        # Check if the proto function is already a callable
        if callable( protoVec[0] ):
            return self.buildProtoFromFunction( protoVec[0], protoVec[1] )

        # Check and build the proto from a class name
        if protoVec[0][:5] == 'moose':
            protoName = protoVec[0][6:]
            if self.isKnownClassOrFile( protoName, knownClasses ):
                try:
                    getattr( moose, protoName )( '/library/' + protoVec[1] )
                except AttributeError:
                    raise BuildError( protoType + "Proto: Moose class '" \
                            + protoVec[0] + "' not found." )
                return True

        if self.buildProtoFromFunction( protoVec[0], protoVec[1] ):
            return True
        # Maybe the proto is already in memory
        # Avoid relative file paths going toward root
        if protoVec[0][:3] != "../":
            if moose.exists( protoVec[0] ):
                moose.copy( protoVec[0], '/library/' + protoVec[1] )
                return True
            if moose.exists( '/library/' + protoVec[0] ):
                #moose.copy('/library/' + protoVec[0], '/library/', protoVec[1])
                if self.verbose:
                    print('renaming /library/' + protoVec[0] + ' to ' + protoVec[1])
                moose.element( '/library/' + protoVec[0]).name = protoVec[1]
                return True
        # Check if there is a matching suffix for file type.
        if self.isKnownClassOrFile( protoVec[0], knownFileTypes ):
            return False
        else:
            raise BuildError( \
                protoType + "Proto: File type '" + protoVec[0] + \
                "' not known." )
        return True

    ################################################################
    # Here are the functions to build the type-specific prototypes.
    ################################################################
    def buildCellProto( self ):
        # cellProtoList args:
        # Option 1: zero args: make standard soma, len and dia 500 um.
        # Option 2: [name, library_proto_name]: uses library proto
        # Option 3: [fname.suffix, cellname ]: Loads cell from file
        # Option 4: [moose<Classname>, cellname]: Makes proto of class
        # Option 5: [funcname, cellname]: Calls named function with specified name of cell to be made.
        # Option 6: [path, cellname]: Copies path to library as proto
        # Option 7: [libraryName, cellname]: Renames library entry as proto
        # Below two options only need the first two args, rest are optional
        # Defailt values are given.
        # Option 8: [somaProto, name, somaDia=5e-4, somaLen=5e-4]
        # Option 9: [ballAndStick, name, somaDia=10e-6, somaLen=10e-6, 
        #       dendDia=4e-6, dendLen=200e-6, numDendSeg=1]
        # Option 10: [ 'branchedCell', name, somaDia=10e-6, somaLen=10e-6, dendDia=4e-6, dendLen=200e-6, dendNumSeg = 1, branchDia=2.5e-6, branchLen=200e-6, branchNumSeg=1 ]
        if len( self.cellProtoList ) == 0:
            ''' Make HH squid model sized compartment:
            len and dia 500 microns. CM = 0.01 F/m^2, RA =
            '''
            self.elecid = makePassiveHHsoma( name = 'cell' )
            assert( moose.exists( '/library/cell/soma' ) )
            self.soma = moose.element( '/library/cell/soma' )
            return

            '''
            self.elecid = moose.Neuron( '/library/cell' )
            dia = 500e-6
            self.soma = buildCompt( self.elecid, 'soma', dia, dia, 0.0,
                0.33333333, 3000, 0.01 )
            self.soma.initVm = -65e-3 # Resting of -65, from HH
            self.soma.Em = -54.4e-3 # 10.6 mV above resting of -65, from HH
            '''

        for i in self.cellProtoList:
            if i[0] == 'somaProto':
                self._buildElecSoma( i )
            elif i[0] == 'ballAndStick':
                self._buildElecBallAndStick( i )
            elif i[0] == 'branchedCell':
                self._buildElecBranchedCell( i )
            elif self.checkAndBuildProto( "cell", i, \
                ["Compartment", "SymCompartment"], ["swc", "p", "nml", "xml"] ):
                self.elecid = moose.element( '/library/' + i[1] )
            else:
                self._loadElec( i[0], i[1] )
            self.elecid.buildSegmentTree()

    def buildSpineProto( self ):
        for i in self.spineProtoList:
            if not self.checkAndBuildProto( "spine", i, \
                ["Compartment", "SymCompartment"], ["swc", "p", "nml", "xml"] ):
                self._loadElec( i[0], i[1] )

    def parseChanName( self, name ):
        if name[-4:] == ".xml":
            period = name.rfind( '.' )
            slash = name.rfind( '/' )
            if ( slash >= period ):
                raise BuildError( "chanProto: bad filename:" + name )
            if ( slash < 0 ):
                return name[:period]
            else:
                return name[slash+1:period]

    def buildChanProto( self ):
        for i in self.chanProtoList:
            if len(i) == 1:
                chanName = self.parseChanName( i[0] )
            else:
                chanName = i[1]
            j = [i[0], chanName]
            if not self.checkAndBuildProto( "chan", j, [], ["xml"] ):
                cm = ChannelML( {'temperature': self.temperature} )
                cm.readChannelMLFromFile( i[0] )
                if ( len( i ) == 2 ):
                    chan = moose.element( '/library/' + chanName )
                    chan.name = i[1]

    def buildChemProto( self ):
        for i in self.chemProtoList:
            if not self.checkAndBuildProto( "chem", i, \
                ["Pool"], ["g", "sbml", "xml" ] ):
                self._loadChem( i[0], i[1] )
            self.chemid = moose.element( '/library/' + i[1] )

    ################################################################
    def _buildElecSoma( self, args ):
        parms = [ 'somaProto', 'soma', 5e-4, 5e-4 ] # somaDia, somaLen
        for i in range( len(args) ):
            parms[i] = args[i]
        cell = moose.Neuron( '/library/' + parms[1] )
        buildCompt( cell, 'soma', dia = parms[2], dx = parms[3] )
        self.elecid = cell
        return cell
        
    ################################################################
    def _buildElecBallAndStick( self, args ):
        parms = [ 'ballAndStick', 'cell', 10e-6, 10e-6, 4e-6, 200e-6, 1 ] # somaDia, somaLen, dendDia, dendLen, dendNumSeg
        for i in range( len(args) ):
            parms[i] = args[i]
        if parms[6] <= 0:
            return self.buildElecSoma( parms[:4] )
        cell = moose.Neuron( '/library/' + parms[1] )
        prev = buildCompt( cell, 'soma', dia = args[2], dx = args[3] )
        dx = parms[5]/parms[6]
        x = prev.x
        for i in range( parms[6] ):
            compt = buildCompt( cell, 'dend' + str(i), x = x, dx = dx, dia = args[4] )
            moose.connect( prev, 'axial', compt, 'raxial' )
            prev = compt
            x += dx
        self.elecid = cell
        return cell

    ################################################################
    def _buildElecBranchedCell( self, args ):
        parms = [ 'branchedCell', 'cell', 10e-6, 10e-6, 4e-6, 200e-6, 1, 2.5e-6, 200e-6, 1 ] # somaDia, somaLen, dendDia, dendLen, dendNumSeg, branchDia, branchLen, branchNumSeg
        for i in range( len(args) ):
            parms[i] = args[i]
        if parms[9] <= 0:
            return self.buildElecSoma( parms[:4] )
        cell = moose.Neuron( '/library/' + parms[1] )
        prev = buildCompt( cell, 'soma', dia = args[2], dx = args[3] )
        dx = parms[5]/parms[6]
        x = prev.x
        for i in range( parms[6] ):
            compt = buildCompt( cell, 'dend' + str(i), x = x, dx = dx, dia = args[4] )
            moose.connect( prev, 'axial', compt, 'raxial' )
            prev = compt
            x += dx
        primaryBranchEnd = prev
        x = prev.x
        y = prev.y
        dxy = (parms[8]/float(parms[9])) * np.sqrt( 1.0/2.0 )
        for i in range( parms[9] ):
            compt = buildCompt( cell, 'branch1_' + str(i), 
                    x = x, dx = dxy, y = y, dy = dxy, 
                    dia = args[7] )
            moose.connect( prev, 'axial', compt, 'raxial' )
            prev = compt
            x += dxy
            y += dxy

        x = primaryBranchEnd.x
        y = primaryBranchEnd.y
        prev = primaryBranchEnd
        for i in range( parms[9] ):
            compt = buildCompt( cell, 'branch2_' + str(i), 
                    x = x, dx = dxy, y = y, dy = -dxy, 
                    dia = args[7] )
            moose.connect( prev, 'axial', compt, 'raxial' )
            prev = compt
            x += dxy
            y -= dxy

        self.elecid = cell
        return cell

    ################################################################
    def _buildVclampOnCompt( self, dendCompts, spineCompts, stimInfo ):
        # stimInfo = [path, geomExpr, relPath, field, expr_string]
        stimObj = []
        for i in dendCompts + spineCompts:
            vclamp = make_vclamp( name = 'vclamp', parent = i.path )

            # Assume SI units. Scale by Cm to get reasonable gain.
            vclamp.gain = i.Cm * 1e4 
            moose.connect( i, 'VmOut', vclamp, 'sensedIn' )
            moose.connect( vclamp, 'currentOut', i, 'injectMsg' )
            stimObj.append( vclamp )

        return stimObj

    def _buildSynInputOnCompt( self, dendCompts, spineCompts, stimInfo, doPeriodic = False ):
        # stimInfo = [path, geomExpr, relPath, field, expr_string]
        # Here we hack geomExpr to use it for the syn weight. We assume it
        # is just a number. In due course
        # it should be possible to actually evaluate it according to geom.
        synWeight = float( stimInfo.geom_expr )
        stimObj = []
        for i in dendCompts + spineCompts:
            path = i.path + '/' + stimInfo.relpath + '/sh/synapse[0]'
            if moose.exists( path ):
                synInput = make_synInput( name='synInput', parent=path )
                synInput.doPeriodic = doPeriodic
                moose.element(path).weight = synWeight
                moose.connect( synInput, 'spikeOut', path, 'addSpike' )
                stimObj.append( synInput )
        return stimObj
        
    ################################################################
    # Here we set up the distributions
    ################################################################
    def buildPassiveDistrib( self ):
	# [path field expr [field expr]...]
        # RM, RA, CM set specific values, per unit area etc.
        # Rm, Ra, Cm set absolute values.
        # Also does Em, Ek, initVm
	# Expression can use p, g, L, len, dia, maxP, maxG, maxL.
        temp = []
        for i in self.passiveDistrib:
            # Handle legacy format of ['.', path, field, expr [field expr]]
            if (len( i ) < 3) or (i[0] != '.' and len(i) %2 != 1):
                raise BuildError( "buildPassiveDistrib: Need 3 + N*2 arguments as (path field expr [field expr]...), have {}".format( len(i) ) )

            if not(( len(i) % 2 ) != 1 and i[0] == '.' ):
                temp.append( '.' )
            temp.extend( i )
            temp.extend( [""] )
        self.elecid.passiveDistribution = temp

    def buildChanDistrib( self ):
        temp = []
        for i in self.chanDistrib:
            temp.extend( i )
            temp.extend( [""] )
        self.elecid.channelDistribution = temp

    def buildSpineDistrib( self ):
        # For uniformity and conciseness, we don't use a dictionary.
        # ordering of spine distrib is
        # name, path, spacing, spacingDistrib, size, sizeDistrib, angle, angleDistrib
        # [i for i in L1 if i in L2]
        # The first two args are compulsory, and don't need arg keys.
        usageStr = 'Usage: name, path, [spacing, spacingDistrib, size, sizeDistrib, angle, angleDistrib]'
        temp = []
        defaults = ['spine', '#dend#,#apical#', '10e-6', '1e-6', '1', '0.5', '0', '6.2831853' ]
        argKeys = ['spacing', 'spacingDistrib', 'size', 'sizeDistrib', 'angle', 'angleDistrib' ]
        for i in self.spineDistrib:
            if len(i) >= 2 :
                arg = i[:2]
                # Backward compat hack here
                bcKeys = [ j for j in i[2:] if j in argKeys ]
                if len( bcKeys ) > 0: # Looks like we have an old arg str
                    print('Rdesigneur::buildSpineDistrib: Warning: Deprecated argument format.\nWill accept for now.')
                    print(usageStr)
                    temp.extend( i + [''] )
                elif len( i ) > len( defaults ):
                    print('Rdesigneur::buildSpineDistrib: Warning: too many arguments in spine definition')
                    print(usageStr)
                else:
                    optArg = i[2:] + defaults[ len(i):]
                    assert( len( optArg ) == len( argKeys ) )
                    for j in zip( argKeys, optArg ):
                        arg.extend( [j[0], j[1]] )
                    temp.extend( arg + [''] )

        self.elecid.spineDistribution = temp

    def newChemDistrib( self, argList, newChemId ):
        # meshOrder = ['soma', 'dend', 'spine', 'psd', 'psd_dend', 'presyn_dend', 'presyn_spine', 'endo', 'endo_axial']
        chemSrc, elecPath, meshType, geom = argList[:4]
        chemSrcObj = self.comptDict.get( chemSrc )
        if not chemSrcObj:
            raise BuildError( "newChemDistrib: Could not find chemSrcObj: " + chemSrc )
        if meshType in ['soma', 'endo_soma', 'psd_dend']:
            raise BuildError( "newChemDistrib: Can't yet handle meshType: " + meshType )
        if meshType == 'dend':
            #diffLength = float( argList[4] )
            mesh = moose.NeuroMesh( newChemId.path + '/' + chemSrc )
            mesh.geometryPolicy = 'cylinder'
            mesh.separateSpines = 0
            #mesh.diffLength = diffLength
            # This is done above in buildChemDistrib
            #self.cellPortionElist = self.elecid.compartmentsFromExpression[ elecPath + " " + geom ]
            #mesh.subTree = self.cellPortionElist
        elif meshType == 'spine':
            mesh = self.buildSpineMesh( argList, newChemId )
        elif meshType == 'psd':
            mesh = self.buildPsdMesh( argList, newChemId )
        elif meshType == 'presyn_dend' or meshType == 'presyn_spine':
            mesh = self.buildPresynMesh( argList, newChemId )
        elif meshType == 'endo' or meshType == 'endo_axial':
            return
        #elif meshType == 'endo' or meshType == 'endo_axial':
        #   mesh = self.buildEndoMesh( argList, newChemId )
        else:
            raise BuildError( "newChemDistrib: ERROR: No mesh of specified type found: " + meshType )

        self._moveCompt( chemSrcObj, mesh )
        #if meshType == 'dend': # has to be done after moveCompt
        #    mesh.diffLength = diffLength
        self.comptDict[chemSrc] = mesh

    def buildSpineMesh( self, argList, newChemId ):
        chemSrc, elecPath, meshType, geom = argList[:4]
        dendMeshName = argList[4]
        dendMesh = self.comptDict.get( dendMeshName )
        if not dendMesh:
            raise( "Error: newChemDistrib: Missing parent NeuroMesh '{}' for spine '{}'".format( dendMeshName, chemSrc ) )
        dendMesh.separateSpines = 1
        mesh = moose.SpineMesh( newChemId.path + '/' + chemSrc )
        moose.connect( dendMesh, 'spineListOut', mesh, 'spineList' )
        return mesh

    def buildPsdMesh( self, argList, newChemId ):
        chemSrc, elecPath, meshType, geom = argList[:4]
        dendMeshName = argList[4]
        dendMesh = self.comptDict.get( dendMeshName )
        if not dendMesh:
            raise( "Error: newChemDistrib: Missing parent NeuroMesh '{}' for psd '{}'".format( dendMeshName, chemSrc ) )
        mesh = moose.PsdMesh( newChemId.path + '/' + chemSrc )
        moose.connect( dendMesh, 'psdListOut', mesh, 'psdList','OneToOne')
        return mesh
            
    def buildPresynMesh( self, argList, newChemId ):
        chemSrc, elecPath, meshType, geom = argList[:4]
        mesh = moose.PresynMesh( newChemId.path + '/' + chemSrc )
        presynRadius = float( argList[4] )
        presynRadiusSdev = float( argList[5] )
        pair = elecPath + " " + geom
        if meshType == 'presyn_dend':
            presynSpacing = float( argList[6] )
            elecList = self.elecid.compartmentsFromExpression[ pair ]
            mesh.buildOnDendrites( elecList, presynSpacing )
        else:
            #elecList = self.elecid.spinesFromExpression[ pair ]
            elecList = self.elecid.compartmentsFromExpression[ pair ]
            mesh.buildOnSpineHeads( elecList )
        mesh.setRadiusStats( presynRadius, presynRadiusSdev )
        return mesh

    def buildEndoMesh( self, argList, newChemId ):
        chemSrc, elecPath, meshType, geom = argList[:4]
        mesh = moose.EndoMesh( newChemId.path + '/' + chemSrc )
        surroundName = argList[4]
        radiusRatio = float( argList[5] )
        surroundMesh = self.comptDict.get( surroundName )
        if not surroundMesh:
            raise( "Error: newChemDistrib: Could not find surround '{}' for endo '{}'".format( surroundName, chemSrc ) )
        #mesh.surround = moose.element( newChemId.path+'/'+surroundName )
        mesh.surround = surroundMesh
        mesh.isMembraneBound = True
        mesh.rScale = radiusRatio
        if meshType == 'endo_axial':
            mesh.doAxialDiffusion = 1
            mesh.rPower = 0.5
            mesh.aPower = 0.5
            mesh.aScale = radiusRatio * radiusRatio
        self._endos.append( [mesh, surroundMesh] )
        return mesh




    def buildChemDistrib( self ):
        # Format [chemLibPath, elecPath, meshType, expr, ...]
        # chemLibPath is name of a chemCompt on library. It can contain
        # further nested compts within it, typically intended to 
        # become endoMeshes, scaled as per original.

        if len( self.chemDistrib ) == 0:
            return
        # Hack to include PSD if spine is there but no PSD.
        # Needed because solvers expect it. May complain because no mol
        spineLine = [ii for ii in self.chemDistrib if ii[2] == 'spine']
        numPsd = len([ii for ii in self.chemDistrib if ii[2] == 'psd'])
        if len( spineLine ) > 0 and numPsd == 0:
            #print( "Error: spine compartment '{}' specified, also need psd compartment.".format( spineLine[0][0] )  )
            #quit()
            if moose.exists(self.chemid.path + '/' + spineLine[0][0]):
                dummyParent = self.chemid.path
            elif moose.exists(self.chemid.path + '/kinetics/' + spineLine[0][0]):
                dummyParent = self.chemid.path + '/kinetics'
            else:
                print( "Error: spine compartment '{}' specified, also need psd compartment.".format( spineLine[0][0] )  )
                quit()
            psdLine = list( spineLine[0] )
            dummyPSD = moose.CubeMesh( dummyParent + "/dummyPSD" )
            #dummyMol = moose.Pool( dummyPSD.path + "/Ca" )
            #dummyMol.diffConst = 20e-12
            psdLine[0] = 'dummyPSD'
            psdLine[2] = 'psd'
            #print( "PSDLINE = ", psdLine )
            self.chemDistrib.append( psdLine )

        sortedChemDistrib = sorted( self.chemDistrib, key = lambda c: meshOrder.index( c[2] ) )
        self.chemid.name = 'temp_chem'
        newChemId = moose.Neutral( self.model.path + '/chem' )
        comptlist = self._assignComptNamesFromKkit_SBML()
        self.comptDict = { i.name:i for i in comptlist }
        #print( "COMPTDICT =================\n", self.comptDict )
        for i in sortedChemDistrib:
            self.newChemDistrib( i, newChemId )
        # We have to assign the compartments to neuromesh and
        # spine mesh only after they have all been connected up.
        for i in sortedChemDistrib:
            chemSrc, elecPath, meshType, geom = i[:4]
            if meshType == 'dend':
                dendMesh = self.comptDict[chemSrc]
                pair = elecPath + " " + geom
                dendMesh.diffLength = float( i[4] )
                dendMesh.subTree = self.elecid.compartmentsFromExpression[ pair ]
            if meshType == 'endo' or meshType == 'endo_axial': 
                # Should come after dend
                mesh = self.buildEndoMesh( i, newChemId )
                chemSrcObj = self.comptDict.get( chemSrc )
                self._moveCompt( chemSrcObj, mesh )
                self.comptDict[chemSrc] = mesh

        moose.delete( self.chemid )
        self.chemid = newChemId

    ################################################################
    # Here we call any extra building function supplied by user.
    # It has to take rdes as an argument.
    ################################################################

    def _buildExtras( self ):
        self.extraBuildFunction( self )


    ################################################################
    # Here we set up the adaptors
    ################################################################
    def findMeshOnName( self, name ):
        pos = name.find( '/' )
        if ( pos != -1 ):
            temp = name[:pos]
            if temp == 'psd' or temp == 'spine' or temp == 'dend':
                return ( temp, name[pos+1:] )
            elif temp in self.comptDict:
                return ( temp, name[pos+1:] )
        return ("","")


    def buildAdaptors( self ):
        for i in self.adaptorList:
            mesh, name = self.findMeshOnName( i[0] )
            if mesh == "":
                mesh, name = self.findMeshOnName( i[2] )
                if  mesh == "":
                    raise BuildError( "buildAdaptors: Failed for " + i[2] )
                self._buildAdaptor( mesh, i[0], i[1], name, i[3], True, i[4], i[5] )
            else:
                self._buildAdaptor( mesh, i[2], i[3], name, i[1], False, i[4], i[5] )

    ################################################################
    # Here we set up the plots. Dummy for cases that don't match conditions
    ################################################################
    def _collapseElistToPathAndClass( self, comptList, path, className ):
        dummy = moose.element( '/' )
        ret = [ dummy ] * len( comptList )
        j = 0
        for i in comptList:
            if moose.exists( i.path + '/' + path ):
                obj = moose.element( i.path + '/' + path )
                if obj.isA[ className ]:
                    ret[j] = obj
            j += 1
        return ret

    # Utility function for doing lookups for objects.
    def _makeUniqueNameStr( self, obj ):
        # second one is faster than the former. 140 ns v/s 180 ns.
        #  return obj.name + " " + str( obj.index )
        return "%s %s" % (obj.name, obj.index)

    # Returns vector of source objects, and the field to use.
    # plotSpec is of the form
    #   [ region_wildcard, region_expr, path, field, title]
    def _parseComptField( self, comptList, plotSpec, knownFields ):
        # Put in stuff to go through fields if the target is a chem object
        field = plotSpec.field
        if not field in knownFields:
            print("Warning: Rdesigneur::_parseComptField: Unknown field '{}'".format( field ) )
            return (), ""

        kf = knownFields[field] # Find the field to decide type.
        if kf[0] in ['CaConcBase', 'ChanBase', 'NMDAChan', 'VClamp']:
            objList = self._collapseElistToPathAndClass( comptList, plotSpec.relpath, kf[0] )
            return objList, kf[1]
        elif field in [ 'n', 'conc', 'nInit', 'concInit', 'volume', 'increment']:
            path = plotSpec.relpath
            pos = path.find( '/' )
            if pos == -1:   # Assume it is in the dend compartment.
                path  = 'dend/' + path
                chemComptName = 'dend'
                cc = moose.element(self.modelPath + '/chem/dend')
            else:
                chemComptName = path.split('/')[0]
                el = moose.wildcardFind( self.modelPath + "/chem/##[ISA=ChemCompt]" )
                cc = moose.element( '/' )
                for elm in el:
                    if elm.name == chemComptName:
                        cc = elm
                        break
            if cc.path == '/':
                raise BuildError( "parseComptField: no compartment named: " + chemComptName )
            #pos = path.find( '/' )
            #chemCompt = path[:pos]
            #if chemCompt[-5:] == "_endo":
            #    chemCompt = chemCompt[0:-5]
            voxelVec = []
            temp = [ self._makeUniqueNameStr( i ) for i in comptList ]
            #print( temp )
            #print( "#####################" )
            comptSet = set( temp )
            #em = [ moose.element(i) for i in cc.elecComptMap ]
            em = sorted( [ self._makeUniqueNameStr(i[0]) for i in cc.elecComptMap ] )
            #print( "=================================================" )
            #print( em )

            # The indexing in the voxelVec need not overlap with the 
            # indexing in the chem path. Need to just go by lengths.
            voxelVec = [i for i in range(len( em ) ) if em[i] in comptSet ]
            # Here we collapse the voxelVec into objects to plot.
            #print( "=================================================" )
            #print( voxelVec )
            #print( "=================================================" )
            allObj = moose.vec( self.modelPath + '/chem/' + plotSpec.relpath )
            nd = len( allObj )
            objList = [ allObj[j] for j in voxelVec if j < nd]
            #print "############", chemCompt, len(objList), kf[1]
            return objList, kf[1]

        else:
            return comptList, kf[1]


    def _buildPlots( self ):
        knownFields = {
            'Vm':('CompartmentBase', 'getVm', 1000, 'Memb. Potential (mV)' ),
            'spikeTime':('CompartmentBase', 'getVm', 1, 'Spike Times (s)'),
            'Im':('CompartmentBase', 'getIm', 1e9, 'Memb. current (nA)' ),
            'Cm':('CompartmentBase', 'getCm', 1e12, 'Memb. capacitance (pF)' ),
            'Rm':('CompartmentBase', 'getRm', 1e-9, 'Memb. Res (GOhm)' ),
            'Ra':('CompartmentBase', 'getRa', 1e-6, 'Axial Res (MOhm)' ),
            'inject':('CompartmentBase', 'getInject', 1e9, 'inject current (nA)' ),
            'Gbar':('ChanBase', 'getGbar', 1e9, 'chan max conductance (nS)' ),
            'modulation':('ChanBase', 'getModulation', 1, 'chan modulation (unitless)' ),
            'Gk':('ChanBase', 'getGk', 1e9, 'chan conductance (nS)' ),
            'Ik':('ChanBase', 'getIk', 1e9, 'chan current (nA)' ),
            'ICa':('NMDAChan', 'getICa', 1e9, 'Ca current (nA)' ),
            'Ca':('CaConcBase', 'getCa', 1e3, 'Ca conc (uM)' ),
            'n':('PoolBase', 'getN', 1, '# of molecules'),
            'conc':('PoolBase', 'getConc', 1000, 'Concentration (uM)' ),
            'nInit':('PoolBase', 'getNInit', 1, '# of molecules'),
            'concInit':('PoolBase', 'getConcInit', 1000, 'Concentration (uM)' ),
            'volume':('PoolBase', 'getVolume', 1e18, 'Volume (um^3)' ),
            'current':('VClamp', 'getCurrent', 1e9, 'Holding Current (nA)')
        }
        graphs = moose.Neutral( self.modelPath + '/graphs' )
        dummy = moose.element( '/' )
        k = 0
        for i in self.plotList:
            pair = i.elecpath + ' ' + i.geom_expr
            dendCompts = self.elecid.compartmentsFromExpression[ pair ]
            #spineCompts = self.elecid.spinesFromExpression[ pair ]
            plotObj, plotField = self._parseComptField( dendCompts, i, knownFields )
            #plotObj2, plotField2 = self._parseComptField( spineCompts, i, knownFields )
            #assert( plotField == plotField2 )
            #plotObj3 = plotObj + plotObj2
            #print ( "LEEEENS = {}, {}, {}".format( len( plotObj ), len( plotObj2), len( plotObj3 ) ) )
            numPlots = sum( q != dummy for q in plotObj )
            #print( "PlotList: {0}: numobj={1}, field ={2}, nd={3}, ns={4}".format( pair, numPlots, plotField, len( dendCompts ), len( spineCompts ) ) )
            if numPlots > 0:
                tabname = graphs.path + '/plot' + str(k)
                scale = knownFields[i.field][2]
                units = knownFields[i.field][3]
                if i.mode == 'wave':
                    self.wavePlotNames.append( [ tabname, i.title, k, scale, units, i ] )
                else:
                    self.plotNames.append( [ tabname, i.title, k, scale, units, i.field, i.ymin, i.ymax ] )
                if len( i.saveFile ) > 4 and i.saveFile[-4] == '.xml' or i.saveFile:
                    self.saveNames.append( [ tabname, len(self.saveNames), scale, units, i ] )

                k += 1
                if i.field == 'n' or i.field == 'conc' or i.field == 'volume' or i.field == 'Gbar':
                    tabs = moose.Table2( tabname, numPlots )
                else:
                    tabs = moose.Table( tabname, numPlots )
                    if i.field == 'spikeTime':
                        tabs.vec.threshold = -0.02 # Threshold for classifying Vm as a spike.
                        tabs.vec.useSpikeMode = True # spike detect mode on

            vtabs = moose.vec( tabs )
            q = 0
            for p in [ x for x in plotObj if x != dummy ]:
                #print( p.path, plotField, q )
                moose.connect( vtabs[q], 'requestOut', p, plotField )
                q += 1

    def _buildMoogli( self ):
        knownFields = knownFieldsDefault
        moogliBase = moose.Neutral( self.modelPath + '/moogli' )
        for i in self.moogList:
            kf = knownFields[i.field]
            pair = i.elecpath + " " + i.geom_expr
            dendCompts = self.elecid.compartmentsFromExpression[ pair ]
            #spineCompts = self.elecid.spinesFromExpression[ pair ]
            dendObj, mooField = self._parseComptField( dendCompts, i, knownFields )
            #spineObj, mooField2 = self._parseComptField( spineCompts, i, knownFields )
            #assert( mooField == mooField2 )
            #mooObj3 = dendObj + spineObj
            numMoogli = len( dendObj )
            self.moogNames.append( rmoogli.makeMoogli( self, dendObj, i, kf ) )

    def _buildFileOutput( self ):
        fileBase = moose.Neutral( self.modelPath + "/file" )
        knownFields = knownFieldsDefault

        nsdfBlocks = {}
        nsdf = None
        
        for idx, fentry in enumerate( self.outputFileList ):
            oname = fentry.fname.split( "." )[0]
            if fentry.ftype in ["h5", "nsdf"]:
                # Should check for duplication.
                nsdfPath = fileBase.path + '/' + oname
                if fentry.field in ["n", "conc"]:
                    modelPath = self.modelPath + "/chem" 
                    basePath = modelPath + "/" + fentry.path
                    if fentry.path[-1] in [']', '#']: # explicit index
                        pathStr = basePath + "." + fentry.field
                    else:
                        pathStr = basePath + "[]." + fentry.field
                else:
                    modelPath = self.modelPath + "/elec" 
                    spl = fentry.path.split('/')
                    if spl[0][-1] == "#":
                        if len( spl ) == 1:
                            fentry.path = spl[0]+"[ISA=CompartmentBase]"
                        else:
                            fentry.path = spl[0]+"[ISA=CompartmentBase]/" + fentry.path[1:]

                    # Otherwise we use basepath as is.
                    basePath = modelPath + "/" + fentry.path
                    pathStr = basePath + "." + fentry.field
                if not nsdfPath in nsdfBlocks:
                    self.nsdfPathList.append( nsdfPath )
                    nsdfBlocks[nsdfPath] = [pathStr]
                    nsdf = moose.NSDFWriter2( nsdfPath )
                    nsdf.modelRoot = "" # Blank means don't save tree.
                    nsdf.filename = fentry.fname
                    # Insert the model setup files here.
                    nsdf.mode = 2
                    nsdf.flushLimit = fentry.flushSteps   # Number of timesteps between flush
                    nsdf.tick = 20 + len( nsdfBlocks )
                    moose.setClock( nsdf.tick, fentry.dt )
                    mfns = sys.argv[0]
                    for ii in self.modelFileNameList:
                        mfns += "," + ii
                    nsdf.modelFileNames = mfns 
                else:
                    nsdfBlocks[nsdfPath].append( pathStr )
        for nsdfPath in self.nsdfPathList:
            nsdf = moose.element( nsdfPath )
            nsdf.blocks = nsdfBlocks[nsdfPath]


    ################################################################
    # Here we display the plots and moogli
    ################################################################

    def displayMoogli( self, moogliDt, runtime, rotation = math.pi/500.0, fullscreen = False, block = True, azim = 0.0, elev = 0.0, mergeDisplays = False, colormap = 'jet', center = [], bg = 'default', animation = [],
            movieFrame = [] ):
        # If center is empty then use autoscaling.
        rmoogli.displayMoogli( self, moogliDt, runtime, rotation = rotation, fullscreen = fullscreen, azim = azim, elev = elev, mergeDisplays = mergeDisplays, colormap = colormap, center = center, bg = bg, animation = animation, movieFrame = movieFrame )
        pr = moose.PyRun( '/model/updateMoogli' )

        pr.runString = '''
import rdesigneur.rmoogli
rdesigneur.rmoogli.updateMoogliViewer()
'''
        moose.setClock( pr.tick, moogliDt )
        moose.reinit()
        moose.start( runtime )
        self._save()                                            
        rmoogli.notifySimulationEnd()
        if block:
            self.display( len( self.moogNames ) + 1)
        while True:
            time.sleep(1)

    def display( self, startIndex = 0, block=True ):
        self._save()                                            
        for i in self.plotNames:
            plt.figure( i[2] + startIndex )
            plt.title( i[1] )
            plt.xlabel( "Time (s)" )
            plt.ylabel( i[4] )
            vtab = moose.vec( i[0] )
            if i[5] == 'spikeTime':
                k = 0
                tmax = moose.element( '/clock' ).currentTime
                for j in vtab: # Plot a raster
                    y = [k] * len( j.vector )
                    plt.plot( j.vector * i[3], y, linestyle = 'None', marker = '.', markersize = 10 )
                    plt.xlim( 0, tmax )
                
            else:
                t = np.arange( 0, vtab[0].vector.size, 1 ) * vtab[0].dt
                for j in vtab:
                    plt.plot( t, j.vector * i[3] )
        if len( self.moogList ) or len( self.wavePlotNames ) > 0:
            plt.ion()
        # Here we build the plots and lines for the waveplots
        self.initWavePlots( startIndex )
        if len( self.wavePlotNames ) > 0:
            for i in range( 3 ):
                self.displayWavePlots()
        plt.show( block=block )
        

    def initWavePlots( self, startIndex ):
        self.frameDt = moose.element( '/clock' ).currentTime/self.numWaveFrames
        for wpn in range( len(self.wavePlotNames) ):
            i = self.wavePlotNames[wpn]
            vtab = moose.vec( i[0] )
            if len( vtab ) < 2:
                print( "Warning: Waveplot {} abandoned, only {} points".format( i[1], len( vtab ) ) )
                continue
            dFrame = int( len( vtab[0].vector ) / self.numWaveFrames )
            if dFrame < 1:
                dFrame = 1
            vpts = np.array( [ [k.vector[j] for j in range( 0, len( k.vector ), dFrame ) ] for k in vtab] ).T * i[3]
            fig = plt.figure( i[2] + startIndex )
            ax = fig.add_subplot( 111 )
            plt.title( i[1] )
            plt.xlabel( "position (voxels)" )
            plt.ylabel( i[4] )
            plotinfo = i[5]
            if plotinfo.ymin == plotinfo.ymax:
                mn = np.min(vpts)
                mx = np.max(vpts)
                if mn/mx < 0.3:
                    mn = 0
            else:
                mn = plotinfo.ymin
                mx = plotinfo.ymax
            ax.set_ylim( mn, mx )
            line, = plt.plot( range( len( vtab ) ), vpts[0] )
            timeLabel = plt.text( len(vtab ) * 0.05, mn + 0.9*(mx-mn), 'time = 0' )
            self.wavePlotNames[wpn].append( [fig, line, vpts, timeLabel] )
            fig.canvas.draw()

    def displayWavePlots( self ):
        for f in range( self.numWaveFrames ):
            for i in self.wavePlotNames:
                wp = i[6]
                if len( wp[2] ) > f:
                    wp[1].set_ydata( wp[2][f] )
                    wp[3].set_text( "time = {:.1f}".format(f*self.frameDt) )
                    #wp[0].canvas.draw()
                    wp[0].canvas.flush_events()
            #plt.pause(0.001)
        
        #This calls the _save function which saves only if the filenames have been specified

    ################################################################
    # Here we get the time-series data and write to various formats
    ################################################################
    '''
    The original author of the functions -- [_savePlots(), _writeXML(), _writeCSV(), _save()] is
    Sarthak Sharma.
    Email address: sarthaks442@gmail.com
    Heavily modified by U.S. Bhalla
    '''
    def _writeXML( self, plotData, time, vtab ): 
        tabname = plotData[0]
        idx = plotData[1]
        scale = plotData[2]
        units = plotData[3]
        rp = plotData[4]
        filename = rp.saveFile[:-4] + str(idx) + '.xml'
        root = etree.Element("TimeSeriesPlot")
        parameters = etree.SubElement( root, "parameters" )
        if self.params == None:
            parameters.text = "None"
        else:
            assert(isinstance(self.params, dict)), "'params' should be a dictionary."
            for pkey, pvalue in self.params.items():
                parameter = etree.SubElement( parameters, str(pkey) )
                parameter.text = str(pvalue)

        #plotData contains all the details of a single plot
        title = etree.SubElement( root, "timeSeries" )
        title.set( 'title', rp.title)
        title.set( 'field', rp.field)
        title.set( 'scale', str(scale) )
        title.set( 'units', units)
        title.set( 'dt', str(vtab[0].dt) )
        res = rp.saveResolution
        p = []
        for t, v in zip( time, vtab ):
            p.append( etree.SubElement( title, "data"))
            p[-1].set( 'path', v.path )
            p[-1].text = ''.join( str(round(y,res)) + ' ' for y in v.vector )
        tree = etree.ElementTree(root)
        tree.write(filename)

    def _writeCSV( self, plotData, time, vtab ): 
        tabname = plotData[0]
        idx = plotData[1]
        scale = plotData[2]
        units = plotData[3]
        rp = plotData[4]
        filename = rp.saveFile[:-4] + str(idx) + '.csv'

        header = ["time",]
        valMatrix = [time,]
        header.extend( [ v.path for v in vtab ] )
        valMatrix.extend( [ v.vector for v in vtab ] )
        nv = np.array( valMatrix ).T
        with open(filename, 'wb') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(header)
            for row in nv:
                writer.writerow(row)

    ##########****SAVING*****###############


    def _save( self ):
        self._finishedSaving = True
        for nsdfPath in self.nsdfPathList:
            nsdf = moose.element( nsdfPath )
            nsdf.close()
        for i in self.saveNames:
            tabname = i[0]
            idx = i[1]
            scale = i[2]
            units = i[3]
            rp = i[4] # The rplot data structure, it has the setup info.

            vtab = moose.vec( tabname )
            t = np.arange( 0, vtab[0].vector.size, 1 ) * vtab[0].dt
            ftype = rp.filename[-4:]
            if ftype == '.xml':
                self._writeXML( i, t, vtab )
            elif ftype == '.csv':
                self._writeCSV( i, t, vtab )
            else:
                print("Save format '{}' not known, please use .csv or .xml".format( ftype ) )

    ################################################################
    # Here we set up the stims
    ################################################################
    def _buildStims( self ):
        knownFields = {
                'inject':('CompartmentBase', 'setInject'),
                'Ca':('CaConcBase', 'setCa'),
                'n':('PoolBase', 'setN'),
                'conc':('PoolBase', 'setConc'),
                'nInit':('PoolBase', 'setNinit'),
                'concInit':('PoolBase', 'setConcInit'),
                'increment':('PoolBase', 'increment'),
                'vclamp':('CompartmentBase', 'setInject'),
                'randsyn':('SynChan', 'addSpike'),
                'periodicsyn':('SynChan', 'addSpike')
        }
        stims = moose.Neutral( self.modelPath + '/stims' )
        k = 0
        # rstim class has {fname, path, field, dt, flush_steps }
        for i in self.stimList:
            pair = i.elecpath + " " + i.geom_expr
            dendCompts = self.elecid.compartmentsFromExpression[ pair ]
            if i.field == 'vclamp':
                stimObj = self._buildVclampOnCompt( dendCompts, [], i )
                stimField = 'commandIn'
            elif i.field == 'randsyn':
                stimObj = self._buildSynInputOnCompt( dendCompts, [], i )
                stimField = 'setRate'
            elif i.field == 'periodicsyn':
                stimObj = self._buildSynInputOnCompt( dendCompts, [], i, doPeriodic = True )
                stimField = 'setRate'
            else:
                stimObj, stimField = self._parseComptField( dendCompts, i, knownFields )
                #print( "STIM OBJ: ", [k.dataIndex for k in stimObj] )
                #print( "STIM OBJ: ", [k.coords[0] for k in stimObj] )
            numStim = len( stimObj )
            if numStim > 0:
                funcname = stims.path + '/stim' + str(k)
                k += 1
                func = moose.Function( funcname )
                func.expr = i.expr
                func.doEvalAtReinit = 1
                for q in stimObj:
                    moose.connect( func, 'valueOut', q, stimField )
                if stimField == "increment": # Has to be under Ksolve
                    moose.move( func, q )

    ################################################################
    def _configureHSolve( self ):
        if not self.turnOffElec:
            hsolve = moose.HSolve( self.elecid.path + '/hsolve' )
            hsolve.dt = self.elecDt
            hsolve.target = self.soma.path

# Utility function for setting up clocks.
    def _configureClocks( self ):
        if self.turnOffElec:
            elecDt = 1e6
            elecPlotDt = 1e6
        else:
            elecDt = self.elecDt
            elecPlotDt = self.elecPlotDt
        diffDt = self.diffDt
        chemDt = self.chemDt
        for i in range( 0, 9 ):     # Assign elec family of clocks
            moose.setClock( i, elecDt )
        moose.setClock( 8, elecPlotDt ) 
        moose.setClock( 10, diffDt )# Assign diffusion clock.
        for i in range( 11, 18 ):   # Assign the chem family of clocks.
            moose.setClock( i, chemDt )
        if not self.turnOffElec:    # Assign the Function clock
            moose.setClock( 12, self.funcDt )
        moose.setClock( 18, self.chemPlotDt )
        sys.stdout.flush()
    ################################################################

    def validateFromMemory( self, epath, cpath ):
        return self.validateChem()

    #################################################################
    # assumes ePath is the parent element of the electrical model,
    # and cPath the parent element of the compts in the chem model
    def buildFromMemory( self, ePath, cPath, doCopy = False ):
        if not self.validateFromMemory( ePath, cPath ):
            return
        if doCopy:
            x = moose.copy( cPath, self.model )
            self.chemid = moose.element( x )
            self.chemid.name = 'chem'
            x = moose.copy( ePath, self.model )
            self.elecid = moose.element( x )
            self.elecid.name = 'elec'
        else:
            self.elecid = moose.element( ePath )
            self.chemid = moose.element( cPath )
            if self.elecid.path != self.model.path + '/elec':
                if ( self.elecid.parent != self.model ):
                    moose.move( self.elecid, self.model )
                self.elecid.name = 'elec'
            if self.chemid.path != self.model.path + '/chem':
                if ( self.chemid.parent != self.model ):
                    moose.move( self.chemid, self.model )
                self.chemid.name = 'chem'


        ep = self.elecid.path
        somaList = moose.wildcardFind( ep + '/#oma#[ISA=CompartmentBase]' )
        if len( somaList ) == 0:
            somaList = moose.wildcardFind( ep + '/#[ISA=CompartmentBase]' )
        assert( len( somaList ) > 0 )
        maxdia = 0.0
        for i in somaList:
            if ( i.diameter > maxdia ):
                self.soma = i
        #self.soma = self.comptList[0]
        self._decorateWithSpines()
        self.spineList = moose.wildcardFind( ep + '/#spine#[ISA=CompartmentBase],' + ep + '/#head#[ISA=CompartmentBase]' )
        if len( self.spineList ) == 0:
            self.spineList = moose.wildcardFind( ep + '/#head#[ISA=CompartmentBase]' )
        nmdarList = moose.wildcardFind( ep + '/##[ISA=NMDAChan]' )

        self.comptList = moose.wildcardFind( ep + '/#[ISA=CompartmentBase]')
        print("Rdesigneur: Elec model has ", len( self.comptList ),
            " compartments and ", len( self.spineList ),
            " spines with ", len( nmdarList ), " NMDARs")


        # This is outdated. I haven't run across a case yet where we
        # call it this way. Haven't updated.
        #self._buildNeuroMesh()

        self._configureSolvers()
        for i in self.adaptorList:
            #  print(i)
            assert len(i) >= 8
            self._buildAdaptor( i[0],i[1],i[2],i[3],i[4],i[5],i[6],i[7] )

    ################################################################

    def buildFromFile( self, efile, cfile ):
        self.efile = efile
        self.cfile = cfile
        self._loadElec( efile, 'tempelec' )
        if len( self.chanDistrib ) > 0:
            self.elecid.channelDistribution = self.chanDistrib
            self.elecid.parseChanDistrib()
        self._loadChem( cfile, 'tempchem' )
        self.buildFromMemory( self.model.path + '/tempelec', self.model.path + '/tempchem' )

    ################################################################
    # Utility function to add a single spine to the given parent.

    # parent is parent compartment for this spine.
    # spineProto is just that.
    # pos is position (in metres ) along parent compartment
    # angle is angle (in radians) to rotate spine wrt x in plane xy.
    # Size is size scaling factor, 1 leaves as is.
    # x, y, z are unit vectors. Z is along the parent compt.
    # We first shift the spine over so that it is offset by the parent compt
    # diameter.
    # We then need to reorient the spine which lies along (i,0,0) to
    #   lie along x. X is a unit vector so this is done simply by
    #   multiplying each coord of the spine by x.
    # Finally we rotate the spine around the z axis by the specified angle
    # k is index of this spine.
    def _addSpine( self, parent, spineProto, pos, angle, x, y, z, size, k ):
        spine = moose.copy( spineProto, parent.parent, 'spine' + str(k) )
        kids = spine[0].children
        coords = []
        ppos = np.array( [parent.x0, parent.y0, parent.z0] )
        for i in kids:
            #print i.name, k
            j = i[0]
            j.name += str(k)
            #print 'j = ', j
            coords.append( [j.x0, j.y0, j.z0] )
            coords.append( [j.x, j.y, j.z] )
            self._scaleSpineCompt( j, size )
            moose.move( i, self.elecid )
        origin = coords[0]
        #print 'coords = ', coords
        # Offset it so shaft starts from surface of parent cylinder
        origin[0] -= parent.diameter / 2.0
        coords = np.array( coords )
        coords -= origin # place spine shaft base at origin.
        rot = np.array( [x, [0,0,0], [0,0,0]] )
        coords = np.dot( coords, rot )
        moose.delete( spine )
        moose.connect( parent, "raxial", kids[0], "axial" )
        self._reorientSpine( kids, coords, ppos, pos, size, angle, x, y, z )

    ################################################################
    ## The spineid is the parent object of the prototype spine. The
    ## spine prototype can include any number of compartments, and each
    ## can have any number of voltage and ligand-gated channels, as well
    ## as CaConc and other mechanisms.
    ## The parentList is a list of Object Ids for parent compartments for
    ## the new spines
    ## The spacingDistrib is the width of a normal distribution around
    ## the spacing. Both are in metre units.
    ## The reference angle of 0 radians is facing away from the soma.
    ## In all cases we assume that the spine will be rotated so that its
    ## axis is perpendicular to the axis of the dendrite.
    ## The simplest way to put the spine in any random position is to have
    ## an angleDistrib of 2 pi. The algorithm selects any angle in the
    ## linear range of the angle distrib to add to the specified angle.
    ## With each position along the dendrite the algorithm computes a new
    ## spine direction, using rotation to increment the angle.
    ################################################################
    def _decorateWithSpines( self ):
        args = []
        for i in self.addSpineList:
            if not moose.exists( '/library/' + i[0] ):
                print('Warning: _decorateWithSpines: spine proto ', i[0], ' not found.')
                continue
            s = ""
            for j in range( 9 ):
                s = s + str(i[j]) + ' '
            args.append( s )
        self.elecid.spineSpecification = args
        self.elecid.parseSpines()

    ################################################################

    def _loadElec( self, efile, elecname ):
        self.modelFileNameList.append( efile )
        if ( efile[ len( efile ) - 2:] == ".p" ):
            self.elecid = moose.loadModel( efile, '/library/' + elecname)
        elif ( efile[ len( efile ) - 4:] == ".swc" ):
            self.elecid = moose.loadModel( efile, '/library/' + elecname)
        else:
            nm = NeuroML()
            print("in _loadElec, combineSegments = ", self.combineSegments)
            nm.readNeuroMLFromFile( efile, \
                    params = {'combineSegments': self.combineSegments, \
                    'createPotentialSynapses': True } )
            if moose.exists( '/cells' ):
                kids = moose.wildcardFind( '/cells/#' )
            else:
                kids = moose.wildcardFind( '/library/#[ISA=Neuron],/library/#[TYPE=Neutral]' )
                if ( kids[0].name == 'spine' ):
                    kids = kids[1:]

            assert( len( kids ) > 0 )
            self.elecid = kids[0]
            temp = moose.wildcardFind( self.elecid.path + '/#[ISA=CompartmentBase]' )

        transformNMDAR( self.elecid.path )
        kids = moose.wildcardFind( '/library/##[0]' )
        for i in kids:
            i.tick = -1


    #################################################################

    # This assumes that the chemid is located in self.parent.path+/chem
    # It moves the existing chem compartments into a NeuroMesh
    # For now this requires that we have a dend, a spine and a PSD,
    # with those names and volumes in decreasing order.
    def validateChem( self  ):
        cpath = self.chemid.path
        comptlist = moose.wildcardFind( cpath + '/##[ISA=ChemCompt]' )
        if len( comptlist ) == 0:
            raise BuildError( "validateChem: no compartment on: " + cpath )

        return True

    #################################################################

    def _isModelFromKkit_SBML( self ):
        for i in self.chemProtoList:
            if i[0][-2:] == ".g" or i[0][-4:] == ".xml":
                return True
        return False

    def _assignComptNamesFromKkit_SBML( self ):
        comptList = moose.wildcardFind( self.chemid.path + '/##[ISA=ChemCompt]' )
        if len( comptList ) == 0:
            print( "EMPTY comptlist: ", self.chemid.path , ", found kinetics" )
        return comptList

    #################################################################
    def _configureSolvers( self ):
        if not hasattr( self, 'chemid' ) or len( self.chemDistrib ) == 0:
            return
        fixXreacs.fixXreacs( self.chemid.path )
        sortedChemDistrib = sorted( self.chemDistrib, key = lambda c: meshOrder.index( c[2] ) )
        spineMeshJunctionList = []
        psdMeshJunctionList = []
        endoMeshJunctionList = []
        for line in sortedChemDistrib:
            chemSrc, elecPath, meshType, geom = line[:4]
            mesh = self.comptDict[ chemSrc ]
            if self.useGssa and meshType != 'dend':
                ksolve = moose.Gsolve( mesh.path + '/ksolve' )
            else:
                ksolve = moose.Ksolve( mesh.path + '/ksolve' )
                ksolve.method = self.ode_method
            dsolve = moose.Dsolve( mesh.path + '/dsolve' )
            stoich = moose.Stoich( mesh.path + '/stoich' )
            stoich.compartment = mesh
            stoich.ksolve = ksolve
            stoich.dsolve = dsolve
            if meshType == 'psd':
                if len( moose.wildcardFind( mesh.path + '/##[ISA=PoolBase     ]' ) ) == 0:
                    moose.Pool( mesh.path + '/dummy' )
            stoich.reacSystemPath = mesh.path + "/##"
            if meshType == 'spine':
                spineMeshJunctionList.append( [mesh.path, line[4], dsolve])
            if meshType == 'psd':
                psdMeshJunctionList.append( [mesh.path, line[4], dsolve] )
            elif meshType == 'endo':
                # Endo mesh is easy as it explicitly defines surround.
                endoMeshJunctionList.append( [mesh.path, line[4], dsolve] )
        
        for sm, pm in zip( spineMeshJunctionList, psdMeshJunctionList ):
            # Locate associated NeuroMesh and PSD mesh
            if sm[1] == pm[1]:  # Check for same parent dend.
                nmesh = self.comptDict[ sm[1] ]
                dmdsolve = moose.element( nmesh.path + "/dsolve" )
                dmdsolve.buildNeuroMeshJunctions( sm[2], pm[2] )
                # set up the connections so that the spine volume scaling can happen
                self.elecid.setSpineAndPsdMesh( moose.element(sm[0]), moose.element(pm[0]))
                self.elecid.setSpineAndPsdDsolve( sm[2], pm[2] )

        for em in endoMeshJunctionList:
            emdsolve = em[2]
            surroundMesh = self.comptDict[ em[1] ]
            surroundDsolve = moose.element( surroundMesh.path + "/dsolve" )
            emdsolve.buildMeshJunctions( surroundDsolve )

    ################################################################

    def _loadChem( self, fname, chemName ):
        self.modelFileNameList.append( fname )
        chem = moose.Neutral( '/library/' + chemName )
        pre, ext = os.path.splitext( fname )
        if ext == '.xml' or ext == '.sbml':
            modelId = moose.readSBML( fname, chem.path )
        else:
            modelId = moose.loadModel( fname, chem.path, 'ee' )
        comptlist = moose.wildcardFind( chem.path + '/##[ISA=ChemCompt]' )
        if len( comptlist ) == 0:
            print("loadChem: No compartment found in file: ", fname)
            return

    ################################################################

    def _moveCompt( self, a, b ):

        b.setVolumeNotRates( a.volume )
        # Potential problem: If we have grouped sub-meshes down one level in the tree, this will silenty move those too.
        for i in moose.wildcardFind( a.path + '/#' ):
            #if ( i.name != 'mesh' ):
            if not ( i.isA('ChemCompt' ) or i.isA( 'MeshEntry' ) ):
                moose.move( i, b )
                #print( "Moving {} {} to {}".format( i.className, i.name, b.name ))
        moose.delete( a )
    ################################################################
    def _buildAdaptor( self, meshName, elecRelPath, elecField, \
            chemRelPath, chemField, isElecToChem, offset, scale ):
        #print "offset = ", offset, ", scale = ", scale
        #print( "buildAdaptor: ", meshName, chemRelPath )
        if moose.exists( '/model/chem/' + meshName ):
            mesh = moose.element( '/model/chem/' + meshName )
        elif moose.exists( '/model/chem/kinetics/' + meshName ):
            mesh = moose.element( '/model/chem/kinetics/' + meshName )
        else:
            print( "rdes::buildAdaptor: Error: meshName not found: ", meshName )
            quit()
        #elecComptList = mesh.elecComptList
        if elecRelPath == 'spine':
            # This is nasty. The spine indexing is different from
            # the compartment indexing and the mesh indexing and the 
            # chem indexing. Need to fix at some time.
            #elecComptList = moose.vec( mesh.elecComptList[0].path + '/../spine' )
            elec = moose.element( '/model/elec' )
            elecComptList = [ elec.spineFromCompartment[i.me] for i in mesh.elecComptList ]
            #elecComptList = moose.element( '/model/elec').spineIdsFromCompartmentIds[ mesh.elecComptList ]
            #elecComptList = mesh.elecComptMap
            print( len( mesh.elecComptList ) )
            for i,j in zip( elecComptList, mesh.elecComptList ):
                print( "Lookup: {} {} {}; orig: {} {} {}".format( i.name, i.index, i.fieldIndex, j.name, j.index, j.fieldIndex ))
        else:
            #print("Building adapter: elecComptList on mesh: ", mesh.path , " with elecRelPath = ", elecRelPath )
            elecComptList = mesh.elecComptList

        if len( elecComptList ) == 0:
            raise BuildError( \
                "buildAdaptor: no elec compts in elecComptList on: " + \
                mesh.path )
        startVoxelInCompt = mesh.startVoxelInCompt
        endVoxelInCompt = mesh.endVoxelInCompt
        capField = elecField[0].capitalize() + elecField[1:]
        capChemField = chemField[0].capitalize() + chemField[1:]
        chemPath = mesh.path + '/' + chemRelPath
        #print( "ADAPTOR: elecCompts = {}; startVx = {}, endVox = {}, chemPath = {}".format( [i.name for i in elecComptList], startVoxelInCompt, endVoxelInCompt, chemPath ) )
        if not( moose.exists( chemPath ) ):
            raise BuildError( \
                "Error: buildAdaptor: no chem obj in " + chemPath )
        chemObj = moose.element( chemPath )
        #print( "CHEMPATH = ", chemPath, chemObj )
        assert( chemObj.numData >= len( elecComptList ) )
        adName = '/adapt'
        for i in range( 1, len( elecRelPath ) ):
            if ( elecRelPath[-i] == '/' ):
                adName += elecRelPath[1-i]
                break
        ad = moose.Adaptor( chemObj.path + adName, len( elecComptList ) )
        #print 'building ', len( elecComptList ), 'adaptors ', adName, ' for: ', mesh.name, elecRelPath, elecField, chemRelPath
        av = ad.vec
        chemVec = moose.element( mesh.path + '/' + chemRelPath ).vec

        for i in zip( elecComptList, startVoxelInCompt, endVoxelInCompt, av ):
            i[3].inputOffset = 0.0
            i[3].outputOffset = offset
            i[3].scale = scale
            if elecRelPath == 'spine':
                # Check needed in case there were unmapped entries in 
                # spineIdsFromCompartmentIds
                elObj = i[0]
                #print( "EL OBJ = ", elObj.path )
                #moose.showfield( elObj.me )
                if elObj.path == "/":
                    continue
            else:
                ePath = i[0].path + '/' + elecRelPath
                #print( "EPATH = ", ePath )
                if not( moose.exists( ePath ) ):
                    continue
                    #raise BuildError( "Error: buildAdaptor: no elec obj in " + ePath )
                elObj = moose.element( i[0].path + '/' + elecRelPath )
            if ( isElecToChem ):
                elecFieldSrc = 'get' + capField
                chemFieldDest = 'set' + capChemField
                #print ePath, elecFieldSrc, scale
                moose.connect( i[3], 'requestOut', elObj, elecFieldSrc )
                for j in range( i[1], i[2] ):
                    moose.connect( i[3], 'output', chemVec[j],chemFieldDest)
            else:
                chemFieldSrc = 'get' + capChemField
                if capField == 'Activation':
                    elecFieldDest = 'activation'
                else:
                    elecFieldDest = 'set' + capField
                for j in range( i[1], i[2] ):
                    moose.connect( i[3], 'requestOut', chemVec[j], chemFieldSrc)
                    #print( i[3].name, 'requestOut', chemVec[j].name, chemFieldSrc)
                msg = moose.connect( i[3], 'output', elObj, elecFieldDest )
                #print( "Connecting {} to {} and {}.{}".format( i[3], chemVec[0], elObj, elecFieldDest ) )


#######################################################################
# Some helper classes, used to define argument lists.
#######################################################################

class baseplot:
    def __init__( self,
            elecpath='soma', geom_expr='1', relpath='.', field='Vm' ):
        self.elecpath = elecpath
        self.geom_expr = geom_expr
        self.relpath = relpath
        self.field = field

class rplot( baseplot ):
    def __init__( self,
        elecpath = 'soma', geom_expr = '1', relpath = '.', field = 'Vm', 
        title = 'Membrane potential', 
        mode = 'time', 
        ymin = 0.0, ymax = 0.0, 
        saveFile = "", saveResolution = 3, show = True ):
        baseplot.__init__( self, elecpath, geom_expr, relpath, field )
        self.title = title
        self.mode = mode # Options: time, wave, wave_still, raster
        self.ymin = ymin # If ymin == ymax, it autoscales.
        self.ymax = ymax
        if len( saveFile ) < 5:
            self.saveFile = ""
        else:
            f = saveFile.split('.')
            if len(f) < 2 or ( f[-1] != 'xml' and f[-1] != 'csv' ):
                raise BuildError( "rplot: Filetype is '{}', must be of type .xml or .csv.".format( f[-1] ) )
        self.saveFile = saveFile
        self.show = show

    def printme( self ):
        print( "{}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format( 
            self.elecpath,
            self.geom_expr, self.relpath, self.field, self.title,
            self.mode, self.ymin, self.ymax, self.saveFile, self.show ) )

    @staticmethod
    def convertArg( arg ):
        if isinstance( arg, rplot ):
            return arg
        elif isinstance( arg, list ):
            return rplot( *arg )
        else:
            raise BuildError( "rplot initialization failed" )

class rmoog( baseplot ):
    def __init__( self,
        elecpath = 'soma', 
        geom_expr = '1', 
        relpath = '.', 
        field = 'Vm', 
        title = 'Membrane potential', 
        ymin = 0.0, ymax = 0.0, 
        show = True ,
        diaScale = 1.0
    ): # Could put in other display options.
        baseplot.__init__( self, elecpath, geom_expr, relpath, field )
        self.title = title
        self.ymin = ymin # If ymin == ymax, it autoscales.
        self.ymax = ymax
        self.show = show
        self.diaScale = diaScale

    @staticmethod
    def convertArg( arg ):
        if isinstance( arg, rmoog ):
            return arg
        elif isinstance( arg, list ):
            return rmoog( *arg )
        else:
            raise BuildError( "rmoog initialization failed" )

class rstim( baseplot ):
    def __init__( self,
            elecpath = 'soma', geom_expr = '1', relpath = '.', field = 'inject', expr = '0'):
        baseplot.__init__( self, elecpath, geom_expr, relpath, field )
        self.expr = expr

    def printme( self ):
        print( "{0}, {1}, {2}, {3}, {4}".format( 
            self.elecpath, self.geom_expr, self.relpath, self.field, self.expr
            ) )

    @staticmethod
    def convertArg( arg ):
        if isinstance( arg, rstim ):
            return arg
        elif isinstance( arg, list ):
            return rstim( *arg )
        else:
            raise BuildError( "rstim initialization failed" )


class rfile:
    def __init__( self,
            fname = 'output.h5', path = 'soma', field = 'Vm', dt = 1e-4, flushSteps = 200, start = 0.0, stop = -1.0, ftype = 'nsdf'):
        self.fname = fname
        self.path = path
        if not field in knownFieldsDefault:
            print( "Error: Field '{}' not known.".format( field ) )
            assert( 0 )
        self.field = field
        self.dt = dt
        self.flushSteps = flushSteps
        self.start = start
        self.stop = stop
        self.ftype = self.fname.split(".")[-1]
        if not self.ftype in ["txt", "csv", "h5", "nsdf"]:
            print( "Error: output file format for ", fname , " not known")
            assert( 0 )
        self.fname = self.fname.split("/")[-1]

    def printme( self ):
        print( "{0}, {1}, {2}, {3}".format( 
            self.fname, self.path, self.field, self.dt) )

    @staticmethod
    def convertArg( arg ):
        if isinstance( arg, rfile ):
            return arg
        elif isinstance( arg, list ):
            return rfile( *arg )
        else:
            raise BuildError( "rfile initialization failed" )

