'''
*******************************************************************
 * File:            readSBML.py
 * Description:
 * Author:          HarshaRani
 * E-mail:          hrani@ncbs.res.in
 ********************************************************************/

/**********************************************************************
** This program is part of 'MOOSE', the
** Messaging Object Oriented Simulation Environment,
** also known as GENESIS 3 base code.
**           copyright (C) 2003-2017 Upinder S. Bhalla. and NCBS
Created : Thu May 13 10:19:00 2016(+0530)
Version
Last-Updated: Mon May 26 15:31:36 2025 (+0530)
          By: Subhasis Ray
**********************************************************************/
2023
Aug3: SBMLread will not accept & and  < special character in the name
      Moose will not accept '/' (bcos path kinetics/pool etc),#,&,[,],?,/,<
      explicitly I was converting space to _space_ which is removed
2022:
Apr 05: - edge case NN_mapk15.g, extra Neutral path '/kinetics' exist which
          was not created in xml file which was causing ex12.0* example break
          This is fixed in writeSBML by adding basepath in compartment Annotation
          And same is create in ReadSBML

Mar 22: - function connection are done after Enzyme and Reaction are created
          this is because cplx path is modified after Enzyme created, which
          would be a problem as path changes
        - edge case like pool is parent and product to enzyme, Stoichiometry
          need to reduce (eg osc_different_vols)
        - function expression fixed if multiple of same pool exist

2020:
Sep 21: - Complex pool which is created at species level is copied under enzyme,
          ensuring the value set at species is retained.
Mar 04: - Enzyme-cplx reactant/product's based on stoichiometry number of connection are made.
Jan 09: - reading channel back from MMenz 
2019:
Jun 06: - both compartment name and Id is mapped to the values in comptSbmlidMooseIdMap
May 23: - checking for integer in Assignment expr
Jan 19: - validator flag is set 'on' from True
         - groupname if missing in the sbml file then groupid is taken, 
         if both are missing then its not a valide sbml file
2018
Dec 3:  - reading motor and diffconstant from pool
Nov 30: - groups and subgroups are read from xml to moose 
Nov 19: - reading and creating CylMesh and EndoMesh if specified in the Annotation field in compartment
          definition, also checking if EndoMesh missing/wrong surround compartment 
Oct 26: - validator can be switchedoff by passing validate="off" while readSBML files
May 18: - cleanedup and connected cplx pool to correct parent enzyme 
Jan 6:  - only if valid model exists, then printing the no of compartment,pool,reaction etc
        - at reaction level a check made to see if path exist while creating a new reaction
2017
Oct 4:  - loadpath is cleaned up
Sep 13: - After EnzymaticReaction's k2 is set, explicity ratio is set to 4 to make sure it balance.
        - If units are defined in the rate law for the reaction then check is made and if not in milli mole the base unit 
          then converted to milli unit
        - Moose doesn't allow Michaelis-Menten Enz to have more than one substrates/product
Sep 12: - Now mooseReadSBML return model and errorFlag
        - check's are made if model is valid if its not errorFlag is set
        - check if model has atleast one compartment, if not errorFlag is set
        - errorFlag is set for Rules (for now piecewise is set which is not read user are warned)
        - rateLaw are also calculated depending on units and number of substrates/product

Sep 8 : - functionDefinitions is read, 
        - if Kf and Kb unit are not defined then checked if substance units is defined and depending on this unit Kf and Kb is calculated
            -kf and kb units is not defined and if substance units is also not defined validator fails 
Aug 9 : - a check made to for textColor while adding to Annotator
Aug 8 : - removed "findCompartment" function to chemConnectUtil and imported the function from the same file

2025-05-26 : Updated use of Function: setting numVar is deprecated. Workaround added.

   TODO in
    -Compartment
      --Need to deal with compartment outside
    -Molecule
      -- mathML only AssisgmentRule is taken partly I have checked addition and multiplication,
      -- concentration as piecewise (like tertiary operation with time )
      -- need to do for other calculation.
       -- In Assisgment rule one of the variable is a function, in moose since assignment is done using function,
          function can't get input from another function (model 000740 in l3v1)
    -Loading Model from SBML
      --Tested 1-30 testcase example model provided by l3v1 and l2v4 std.
        ---These are the models that worked (sbml testcase)1-6,10,14-15,17-21,23-25,34,35,58
    ---Need to check
         ----what to do when boundarycondition is true i.e.,
             differential equation derived from the reaction definitions
             should not be calculated for the species(7-9,11-13,16)
             ----kineticsLaw, Math fun has fraction,ceiling,reminder,power 28etc.
             ----Events to be added 26
         ----initial Assisgment for compartment 27
             ----when stoichiometry is rational number 22
         ---- For Michaelis Menten kinetics km is not defined which is most of the case need to calculate
'''


import sys
import collections
import moose
from moose.chemUtil.chemConnectUtil import *
from moose.SBML.validation import validateModel
import re
import os

foundLibSBML_ = False
try:
    import libsbml
    foundLibSBML_ = True
except ImportError:
    pass

def mooseReadSBML(filepath, loadpath, solver="ee",validate="on"):
    """Load SBML model 
    """
    global foundLibSBML_
    if not foundLibSBML_:
        print('[WARN] No python-libsbml found.'
            '\nThis module can be installed by using `pip` in terminal:'
            '\n\t $ pip install python-libsbml --user'
            )
        exit()
        return moose.element('/')

    if not os.path.isfile(filepath):
        print('%s is not found ' % filepath)
        return moose.element('/')

    with open(filepath, "r") as filep:
        loadpath  = loadpath[loadpath.find('/')+1:]
        loaderror = None
        errorFlag = ""
        filep = open(filepath, "r")
        document = libsbml.readSBML(filepath)
        tobecontinue = False
        if validate == "on":
            tobecontinue,errorFlag = validateModel(document)
        else:
            tobecontinue = True

        if tobecontinue:
            level = document.getLevel()
            version = document.getVersion()
            print("\nFile: " + filepath + " (Level " +
                   str(level) + ", version " + str(version) + ")")
            model = document.getModel()
            if model is None:
                print("No model present.")
                return moose.element('/')
            else:
                
                if (model.getNumCompartments() == 0):
                    return moose.element('/'), "Atleast one compartment is needed"
                else:
                    loadpath ='/'+loadpath
                    baseId = moose.Neutral(loadpath)
                    # Map Compartment's SBML id as key and value is
                    # list of[ Moose ID and SpatialDimensions ]
                    global comptSbmlidMooseIdMap
                    global warning
                    warning = " "
                    global msg
                    msg = " "
                    msgRule = ""
                    msgReac = ""
                    noRE = ""
                    groupInfo  = {}
                    funcDef = {}
                    modelAnnotaInfo = {}
                    #comptSbmlidMooseIdMap = {}
                    comptSbmlidMooseIdMap = dict()
                    globparameterIdValue = {}

                    mapParameter(model, globparameterIdValue)
                    msgCmpt = ""
                    errorFlag,msgCmpt,baseId = createCompartment(
                        baseId, model, comptSbmlidMooseIdMap)

                    groupInfo = checkGroup(baseId,model,comptSbmlidMooseIdMap)
                    funcDef = checkFuncDef(model)
                    if errorFlag:
                        specInfoMap = {}
                        errorFlag,warning = createSpecies(
                            baseId, model, comptSbmlidMooseIdMap, specInfoMap, modelAnnotaInfo,groupInfo)

                        if errorFlag:
                            errorFlag, msgReac = createReaction(
                                model, specInfoMap, modelAnnotaInfo, globparameterIdValue,funcDef,groupInfo)
                            if len(moose.wildcardFind(moose.element(loadpath).path+"/##[ISA=Reac],/##[ISA=EnzBase]")) == 0:
                                errorFlag = False
                                noRE = ("Atleast one reaction should be present to display in the widget ")

                            if errorFlag:
                                msgRule = createRules(
                                 model, specInfoMap, globparameterIdValue)
                            
                        getModelAnnotation(model, baseId)
                    if not errorFlag:
                        # Any time in the middle if SBML does not read then I
                        # delete everything from model level This is important
                        # as while reading in GUI the model will show up untill
                        # built which is not correct print "Deleted rest of the
                        # model"
                        print(" model: " + str(model))
                        print("functionDefinitions: " +
                            str(model.getNumFunctionDefinitions()))
                        print("    unitDefinitions: " +
                            str(model.getNumUnitDefinitions()))
                        print("   compartmentTypes: " +
                               str(model.getNumCompartmentTypes()))
                        print("        specieTypes: " +
                               str(model.getNumSpeciesTypes()))
                        print("       compartments: " +
                               str(model.getNumCompartments()))
                        print("            species: " +
                               str(model.getNumSpecies()))
                        print("         parameters: " +
                               str(model.getNumParameters()))
                        print(" initialAssignments: " +
                               str(model.getNumInitialAssignments()))
                        print("              rules: " +
                               str(model.getNumRules()))
                        print("        constraints: " +
                               str(model.getNumConstraints()))
                        print("          reactions: " +
                               str(model.getNumReactions()))
                        print("             events: " +
                               str(model.getNumEvents()))
                        print("\n")
                        moose.delete(baseId.path)
                        loadpath = moose.Shell('/')

            loaderror = msgCmpt+str(msgRule)+msgReac+noRE
            if loaderror != "":
                loaderror = loaderror
            return moose.element(loadpath), loaderror
        else:
            print("Validation failed while reading the model.\n"+errorFlag)
            if errorFlag != "":
                return moose.element('/'), errorFlag
            else:
                return moose.element('/'), "This document is not a valid SBML"

def checkFuncDef(model):
    funcDef = {}
    for findex in range(0,model.getNumFunctionDefinitions()):
        bvar = []
        funMathML = ""
        foundbvar = False
        foundfuncMathML = False
        f = model.getFunctionDefinition(findex)
        fmath = f.getMath()
        for i in range(0,fmath.getNumBvars()):
            bvar.append(fmath.getChild(i).getName())
            foundbvar = True
        funcMathML = fmath.getRightChild()
        if fmath.getRightChild():
            foundfuncMathML = True
        if foundbvar and foundfuncMathML:
            funcDef[f.getName()] = {'bvar':bvar, "MathML": fmath.getRightChild()}
    return funcDef

def checkGroup(basePath,model,comptSbmlidMooseIdMap):
    groupInfo = {}
    modelAnnotaInfo = {}
    if model.getPlugin("groups") != None:
        mplugin = model.getPlugin("groups")
        modelgn = mplugin.getNumGroups()
        for gindex in range(0, mplugin.getNumGroups()):
            p = mplugin.getGroup(gindex)
            grpName = ""
            groupAnnoInfo = {}
            groupAnnoInfo = getObjAnnotation(p, modelAnnotaInfo)
            
            if groupAnnoInfo != {}:
                if moose.exists(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name):
                    groupName = p.getName()
                    if groupName == "":
                        groupName = p.getId()
                    if "Group" in groupAnnoInfo:
                        if moose.exists(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]):
                            if moose.exists(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName):
                                moosegrp = moose.element(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName)
                            else:
                                moosegrp = moose.Neutral(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName)
                        else:
                            moose.Neutral(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"])
                            if moose.exists(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName):
                                moosegrp = moose.element(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName)
                            else:
                                moosegrp = moose.Neutral(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupAnnoInfo["Group"]+'/'+groupName)
                    else:
                        if not moose.exists(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupName):
                            moosegrp = moose.Neutral(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupName)
                        else:
                            moosegrp = moose.element(basePath.path+'/'+comptSbmlidMooseIdMap[groupAnnoInfo["Compartment"]]["MooseId"].name+'/'+groupName)
                    
                    moosegrpinfo = moose.Annotator(moosegrp.path+'/info')
                    moosegrpinfo.color = groupAnnoInfo["bgColor"]
                else:
                    print ("Group's compartment not found in xml file")
            if p.getKind() == 2:
                if p.getId() not in groupInfo:
                    memlists = []
                    for gmemIndex in range(0,p.getNumMembers()):
                        mem = p.getMember(gmemIndex)
                        memlists.append(mem.getIdRef())
                    groupInfo[p.getId()] = {"mpath":moosegrp, "splist":memlists}
    return groupInfo

def setupEnzymaticReaction(enz, groupName, enzName, specInfoMap, modelAnnotaInfo,deletcplxMol):
    enzPool = (modelAnnotaInfo[groupName]["enzyme"])
    enzPool = str(idBeginWith(enzPool))
    enzParent = specInfoMap[enzPool]["Mpath"]
    cplx = (modelAnnotaInfo[groupName]["complex"])
    cplx = str(idBeginWith(cplx))
    complx = moose.element(specInfoMap[cplx]["Mpath"].path)
    enzyme_ = moose.Enz(enzParent.path + '/' + enzName)
    #complx1 = moose.Pool(enzyme_.path+'/'+moose.element(complx).name)
    if not moose.exists(enzyme_.path+'/'+complx.name):
        complx1 = moose.copy(complx,enzyme_.path)
    else:
        complx1 = moose.element(enzyme_.path+'/'+complx.name)
    specInfoMap[cplx]["Mpath"] = moose.element(complx1)

    moose.connect(enzyme_, "cplx", complx1, "reac")
    moose.connect(enzyme_, "enz", enzParent, "reac")
    sublist = (modelAnnotaInfo[groupName]["substrate"])
    prdlist = (modelAnnotaInfo[groupName]["product"])
    deletcplxMol.append(complx.path)
    complx = complx1
    
    enz_sublist = {}
    enz_prdlist = {}
    #getting the reference of enz_complex_formation to get substrate and its stoichiometry    
    enz_cplx_form = (modelAnnotaInfo[groupName]["enz_id_s1"])
    for tr in range(0,enz_cplx_form.getNumReactants()):
        sp = enz_cplx_form.getReactant(tr)
        spspieces = sp.getSpecies()
        enz_sublist[spspieces] = int(sp.getStoichiometry())

    for tr in range(0,enz.getNumProducts()):
        sp = enz.getProduct(tr)
        spspieces = sp.getSpecies()
        spspieces = sp.getSpecies()
        # one of the edge (osc_different_vols) case where pool is a enzyme's parent and 
        # product, which case the stoichiometry = 2 which is ideally correct for SBML simulator
        # but for moose we need to reduce stoichiometry as we connect enzyme parent
        if enzPool == spspieces and int(sp.getStoichiometry()) >1:
            enz_prdlist[spspieces] = int(sp.getStoichiometry())-1
        else:
            enz_prdlist[spspieces] = int(sp.getStoichiometry())

    for si in range(0, len(sublist)):
        sl = sublist[si]
        sl = str(idBeginWith(sl))
        mSId = specInfoMap[sl]["Mpath"]
        substoic = 1
        if sl in enz_sublist:
            substoic = enz_sublist[sl]
        
        for sls in range(0,substoic):
            moose.connect(enzyme_, "sub", mSId, "reac")


    for pi in range(0, len(prdlist)):
        pl = prdlist[pi]
        pl = str(idBeginWith(pl))
        mPId = specInfoMap[pl]["Mpath"]
        prdstoic = 1
        if pl in enz_prdlist:
            prdstoic = enz_prdlist[pl]
        for pls in range(0,prdstoic):
            moose.connect(enzyme_, "prd", mPId, "reac")

    if (enz.isSetNotes):
        pullnotes(enz, enzyme_)
    return enzyme_, True


def addSubPrd(reac, reName, type, reactSBMLIdMooseId, specInfoMap):
    rctMapIter = {}
    if (type == "sub"):
        noplusStoichsub = 0
        addSubinfo = collections.OrderedDict()
        for rt in range(0, reac.getNumReactants()):
            rct = reac.getReactant(rt)
            sp = rct.getSpecies()
            if rct.isSetStoichiometry():
                rctMapIter[sp] = rct.getStoichiometry()
            else:
                rctMapIter[sp] = 1
            noplusStoichsub = noplusStoichsub + rct.getStoichiometry()
        for key, value in list(rctMapIter.items()):
            key = str(idBeginWith(key))
            src = specInfoMap[key]["Mpath"]
            des = reactSBMLIdMooseId[reName]["MooseId"]
            for s in range(0, int(value)):
                if (reactSBMLIdMooseId[reName]["MooseId"]).className == "ConcChan":
                    moose.connect(des, 'in', src, 'reac', 'OneToOne')
                else:
                    moose.connect(des, 'sub', src, 'reac', 'OneToOne')
        addSubinfo = {"nSub": noplusStoichsub}
        reactSBMLIdMooseId[reName].update(addSubinfo)

    else:
        noplusStoichprd = 0
        addPrdinfo = collections.OrderedDict()
        for rt in range(0, reac.getNumProducts()):
            rct = reac.getProduct(rt)
            sp = rct.getSpecies()
            if rct.isSetStoichiometry():
                rctMapIter[sp] = rct.getStoichiometry()
            else:
                rctMapIter[sp] = 1
            
            noplusStoichprd = noplusStoichprd + rct.getStoichiometry()

        for key, values in list(rctMapIter.items()):
            # src Reac
            src = reactSBMLIdMooseId[reName]["MooseId"]
            key = parentSp = str(idBeginWith(key))
            des = specInfoMap[key]["Mpath"]
            for i in range(0, int(values)):
                if (reactSBMLIdMooseId[reName]["MooseId"]).className == "ConcChan":
                    moose.connect(src, 'out', des, 'reac', 'OneToOne')
                else:
                    moose.connect(src, 'prd', des, 'reac', 'OneToOne')
        addPrdinfo = {"nPrd": noplusStoichprd}
        reactSBMLIdMooseId[reName].update(addPrdinfo)


def populatedict(annoDict, label, value):
    if label in annoDict:
        annoDict.setdefault(label, [])
        annoDict[label].update({value})
    else:
        annoDict[label] = {value}


def getModelAnnotation(obj, baseId):
    annotationNode = obj.getAnnotation()
    if annotationNode is not None:
        numchild = annotationNode.getNumChildren()
        for child_no in range(0, numchild):
            childNode = annotationNode.getChild(child_no)
            if (childNode.getPrefix() ==
                    "moose" and childNode.getName() == "ModelAnnotation"):
                num_gchildren = childNode.getNumChildren()
                for gchild_no in range(0, num_gchildren):
                    grandChildNode = childNode.getChild(gchild_no)
                    nodeName = grandChildNode.getName()
                    if (grandChildNode.getNumChildren() == 1):
                        baseinfo = moose.Annotator(baseId.path + '/info')
                        baseinfo.modeltype = "xml"
                        if nodeName == "runTime":
                            runtime = float(
                                (grandChildNode.getChild(0).toXMLString()))
                            baseinfo.runtime = runtime
                        if nodeName == "solver":
                            solver = (grandChildNode.getChild(0).toXMLString())
                            solver = solver.replace(" ","")
                            baseinfo.solver = solver
                        if(nodeName == "plots"):
                            plotValue = (
                                grandChildNode.getChild(0).toXMLString())
                            datapath = moose.element(baseId).path + "/data"
                            if not moose.exists(datapath):
                                datapath = moose.Neutral(baseId.path + "/data")
                                graph = moose.Neutral(
                                    datapath.path + "/graph_0")
                                plotlist = plotValue.split(";")
                                tablelistname = []
                                for plots in plotlist:
                                    plots = plots.replace(" ", "")
                                    plotorg = plots
                                    if( moose.exists(baseId.path + plotorg) and
                                            ( (moose.element(baseId.path+plotorg)).isA("PoolBase"))) :
                                        plotSId = moose.element(
                                            baseId.path + plotorg)
                                        # plotorg = convertSpecialChar(plotorg)
                                        plot2 = plots.replace('/', '_')
                                        plot3 = plot2.replace('[', '_')
                                        plotClean = plot3.replace(']', '_')
                                        plotName = plotClean + ".conc"
                                        fullPath = graph.path + '/' + \
                                            plotName.replace(" ", "")
                                        # If table exist with same name then
                                        # its not created
                                        if not fullPath in tablelistname:
                                            tab = moose.Table2(fullPath)
                                            tablelistname.append(fullPath)
                                            moose.connect(tab, "requestOut", plotSId, "getConc")

def getCmptAnnotation(obj):
    annotateMap = {}
    if (obj.getAnnotation() is not None):
        annoNode = obj.getAnnotation()
        for ch in range(0, annoNode.getNumChildren()):
            childNode = annoNode.getChild(ch)
            if (childNode.getPrefix() == "moose" and (childNode.getName() in["CompartmentAnnotation"])):
                sublist = []
                for gch in range(0, childNode.getNumChildren()):
                    grandChildNode = childNode.getChild(gch)
                    nodeName = grandChildNode.getName()
                    nodeValue = ""
                    if (grandChildNode.getNumChildren() == 1):
                        nodeValue = grandChildNode.getChild(0).toXMLString()
                    else:
                        print(
                            "Error: expected exactly ONE child of ", nodeName)
                    if nodeName == "Mesh":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "numDiffCompts":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "isMembraneBound":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "totLength":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "diffLength":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "surround":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "basePath":
                        annotateMap[nodeName] = nodeValue
    return annotateMap

def getObjAnnotation(obj, modelAnnotationInfo):
    name = obj.getId()
    #name = name.replace(" ", "_space_")
    # modelAnnotaInfo= {}
    annotateMap = {}
    if (obj.getAnnotation() is not None):

        annoNode = obj.getAnnotation()
        for ch in range(0, annoNode.getNumChildren()):
            childNode = annoNode.getChild(ch)
            if (childNode.getPrefix() == "moose" and (childNode.getName() in["ModelAnnotation","EnzymaticReaction","GroupAnnotation"])):
                sublist = []
                for gch in range(0, childNode.getNumChildren()):
                    grandChildNode = childNode.getChild(gch)
                    nodeName = grandChildNode.getName()
                    nodeValue = ""
                    if (grandChildNode.getNumChildren() == 1):
                        nodeValue = grandChildNode.getChild(0).toXMLString()
                    else:
                        print(
                            "Error: expected exactly ONE child of ", nodeName)
                    if nodeName == "xCord":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "yCord":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "bgColor":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "textColor":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "Group":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "Compartment":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "diffConstant":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "motorConstant":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "Channel":
                        annotateMap[nodeName] = nodeValue
                    if nodeName == "Permeability":
                        annotateMap[nodeName] = nodeValue
    return annotateMap


def getEnzAnnotation(obj, modelAnnotaInfo, rev,
                     globparameterIdValue, specInfoMap,funcDef):
    name = obj.getId()
    #name = name.replace(" ", "_space_")
    # modelAnnotaInfo= {}
    annotateMap = {}
    if (obj.getAnnotation() is not None):
        annoNode = obj.getAnnotation()
        for ch in range(0, annoNode.getNumChildren()):
            childNode = annoNode.getChild(ch)
            if (childNode.getPrefix() ==
                    "moose" and childNode.getName() == "EnzymaticReaction"):
                sublist = []
                for gch in range(0, childNode.getNumChildren()):
                    grandChildNode = childNode.getChild(gch)
                    nodeName = grandChildNode.getName()
                    nodeValue = ""
                    if (grandChildNode.getNumChildren() == 1):
                        nodeValue = grandChildNode.getChild(0).toXMLString()
                    else:
                        print(
                            "Error: expected exactly ONE child of ", nodeName)

                    if nodeName == "enzyme":
                        populatedict(annotateMap, "enzyme", nodeValue)

                    elif nodeName == "complex":
                        populatedict(annotateMap, "complex", nodeValue)
                    elif (nodeName == "substrates"):
                        populatedict(annotateMap, "substrates", nodeValue)
                    elif (nodeName == "product"):
                        populatedict(annotateMap, "product", nodeValue)
                    elif (nodeName == "groupName"):
                        populatedict(annotateMap, "grpName", nodeValue)
                    elif (nodeName == "stage"):
                        populatedict(annotateMap, "stage", nodeValue)
                    elif (nodeName == "Group"):
                        populatedict(annotateMap, "group", nodeValue)
                    elif (nodeName == "xCord"):
                        populatedict(annotateMap, "xCord", nodeValue)
                    elif (nodeName == "yCord"):
                        populatedict(annotateMap, "yCord", nodeValue)
    groupName = ""
    if 'grpName' in annotateMap:
        groupName = list(annotateMap["grpName"])[0]
        klaw = obj.getKineticLaw()
        mmsg = ""

        if 'substrates' in annotateMap:
            sublist = list(annotateMap["substrates"])
        else:
            sublist = {}
        if 'product' in annotateMap:
            prdlist = list(annotateMap["product"])
        else:
            prdlist = {}
        noOfsub = len(sublist)
        noOfprd = len(prdlist)
        errorFlag, mmsg, k1, k2 = getKLaw(
            obj, klaw, noOfsub, noOfprd, rev, globparameterIdValue, funcDef,specInfoMap)

        if list(annotateMap["stage"])[0] == '1':
            if groupName in modelAnnotaInfo:
                modelAnnotaInfo[groupName].update(
                    {"enzyme": list(annotateMap["enzyme"])[0],
                     "stage": list(annotateMap["stage"])[0],
                     "substrate": sublist,
                     "k1": k1,
                     "k2": k2,
                     "enz_id_s1":obj
                     }
                )
            else:
                modelAnnotaInfo[groupName] = {
                    "enzyme": list(annotateMap["enzyme"])[0],
                    "stage": list(annotateMap["stage"])[0],
                    "substrate": sublist,
                    "k1": k1,
                    "k2": k2,
                    "enz_id_s1":obj
                    #"group" : list(annotateMap["Group"])[0],
                    #"xCord" : list(annotateMap["xCord"])[0],
                    #"yCord" : list(annotateMap["yCord"]) [0]
                }

        elif list(annotateMap["stage"])[0] == '2':
            if groupName in modelAnnotaInfo:
                stage = int(modelAnnotaInfo[groupName][
                            "stage"]) + int(list(annotateMap["stage"])[0])
                modelAnnotaInfo[groupName].update(
                    {"complex": list(annotateMap["complex"])[0],
                     "product": prdlist,
                     "stage": [stage],
                     "k3": k1
                     }
                )
            else:
                modelAnnotaInfo[groupName] = {
                    "complex": list(annotateMap["complex"])[0],
                    "product": prdlist,
                    "stage": [stage],
                    "k3": k1
                }
    return(groupName)


def createReaction(model, specInfoMap, modelAnnotaInfo, globparameterIdValue,funcDef,groupInfo):
    # print " reaction "
    # Things done for reaction
    # --Reaction is not created, if substrate and product is missing
    # --Reaction is created under first substrate's compartment if substrate not found then product
    # --Reaction is created if substrate or product is missing, but while run time in GUI atleast I have stopped
    # ToDo
    # -- I need to check here if any substance/product is if ( constant == true && bcondition == false)
    # cout <<"The species "<< name << " should not appear in reactant or product as per sbml Rules"<< endl;
    deletecplxMol = []
    errorFlag = True
    reactSBMLIdMooseId = {}
    msg = ""
    reaction_ = None
    for ritem in range(0, model.getNumReactions()):
        reactionCreated = False
        channelCreated = False
        groupName = ""
        rName = ""
        rId = ""
        reac = model.getReaction(ritem)
        group = ""
        reacAnnoInfo = {}
        reacAnnoInfo = getObjAnnotation(reac, modelAnnotaInfo)
        # if "Group" in reacAnnoInfo:
        #     group = reacAnnoInfo["Group"]
        if (reac.isSetId()):
            rId = reac.getId()
            #groups = [k for k, v in groupInfo.items() if rId in v]
            for k,v in groupInfo.items():
                if rId in v["splist"]:
                    group = v["mpath"]

            # if groups:
            #     group = groups[0]
        if (reac.isSetName()):
            rName = reac.getName()
            #rName = rName.replace(" ", "_space_")
        if not(rName):
            rName = rId
        rev = reac.getReversible()
        fast = reac.getFast()
        if (fast):
            print(
                " warning: for now fast attribute is not handled \"",
                rName,
                "\"")
        if (reac.getAnnotation() is not None):
            groupName = getEnzAnnotation(
                reac, modelAnnotaInfo, rev, globparameterIdValue, specInfoMap,funcDef)
        if (groupName != "" and list(
                modelAnnotaInfo[groupName]["stage"])[0] == 3):
            reaction_, reactionCreated = setupEnzymaticReaction(
                reac, groupName, rName, specInfoMap, modelAnnotaInfo,deletecplxMol)
            reaction_.k3 = modelAnnotaInfo[groupName]['k3']
            reaction_.concK1 = modelAnnotaInfo[groupName]['k1']
            reaction_.k2 = modelAnnotaInfo[groupName]['k2']
            reaction_.ratio = 4
            if reactionCreated:
                if (reac.isSetNotes):
                    pullnotes(reac, reaction_)
                    reacAnnoInfo = {}
                reacAnnoInfo = getObjAnnotation(reac, modelAnnotaInfo)

                #if reacAnnoInfo.keys() in ['xCord','yCord','bgColor','Color']:
                if not moose.exists(reaction_.path + '/info'):
                    reacInfo = moose.Annotator(reaction_.path + '/info')
                else:
                    reacInfo = moose.element(reaction_.path + '/info')
                for k, v in list(reacAnnoInfo.items()):
                    if k == 'xCord':
                        reacInfo.x = float(v)
                    elif k == 'yCord':
                        reacInfo.y = float(v)
                    elif k == 'bgColor':
                        reacInfo.color = v
                    elif k == 'Color':
                        reacInfo.textColor = v

        elif(groupName == ""):
            channelfound = False
            for k, v in list(reacAnnoInfo.items()):
                if k == "Channel":
                    channelfound = True
            numRcts = reac.getNumReactants()
            numPdts = reac.getNumProducts()
            nummodifiers = reac.getNumModifiers()
            # if (nummodifiers > 0 and (numRcts > 1 or numPdts >1)):
            #     print("Warning: %s" %(rName)," : Enzymatic Reaction has more than one Substrate or Product which is not allowed in moose, we will be skiping creating this reaction in MOOSE")
            #     reactionCreated = False

            if not (numRcts and numPdts):
                #print("Warning: %s" %(rName)," : Substrate or Product is missing, we will be skiping creating this reaction in MOOSE")
                print("Warning: %s" %(rName)," : Substrate or Product is missing, we will be skiping creating this %s" %("reaction" if not channelfound  else "Channel") +" in MOOSE")
                reactionCreated = False
            elif (reac.getNumModifiers() > 0):
                if not channelfound:
                    reactionCreated, reaction_ = setupMMEnzymeReaction(
                        reac, rName, specInfoMap, reactSBMLIdMooseId, modelAnnotaInfo, model, globparameterIdValue)
                else:
                    channelCreated, channel_ = setupConcChannel(reac,rName,specInfoMap,reactSBMLIdMooseId, modelAnnotaInfo, model, globparameterIdValue)
                    reactSBMLIdMooseId[rName] = {
                        "MooseId": channel_}
            # elif (reac.getNumModifiers() > 0):
            #     reactionCreated = setupMMEnzymeReaction(reac,rName,specInfoMap,reactSBMLIdMooseId,modelAnnotaInfo,model,globparameterIdValue)
            #     reaction_ = reactSBMLIdMooseId['classical']['MooseId']
            #     reactionType = "MMEnz"
            elif (numRcts):
                # In moose, reactions compartment are decided from first Substrate compartment info
                # substrate is missing then check for product
                if (reac.getNumReactants()):
                    react = reac.getReactant(reac.getNumReactants() - 1)
                    # react = reac.getReactant(0)
                    sp = react.getSpecies()
                    sp = str(idBeginWith(sp))
                    speCompt = specInfoMap[sp]["comptId"].path
                    if group:
                        speCompt = group.path
                        # if moose.exists(speCompt+'/'+group):
                        #     speCompt = speCompt+'/'+group
                        # else:
                        #     speCompt = (moose.Neutral(speCompt+'/'+group)).path
                    if moose.exists(speCompt + '/' + rName):
                        rName =rId
                    reaction_ = moose.Reac(speCompt + '/' + rName)
                    reactionCreated = True
                    reactSBMLIdMooseId[rName] = {
                        "MooseId": reaction_}
            elif (numPdts):
                # In moose, reactions compartment are decided from first Substrate compartment info
                # substrate is missing then check for product
                if (reac.getNumProducts()):
                    react = reac.getProducts(0)
                    sp = react.getSpecies()
                    sp = str(idBeginWith(sp))
                    speCompt = specInfoMap[sp]["comptId"].path
                    reaction_ = moose.Reac(speCompt + '/' + rName)
                    reactionCreated = True
                    reactSBMLIdMooseId[rId] = {
                        "MooseId": reaction_}
            if reactionCreated or channelCreated:
                if channelCreated:
                    reaction_ = channel_

                if (reac.isSetNotes):
                    pullnotes(reac, reaction_)
                    reacAnnoInfo = {}
                reacAnnoInfo = getObjAnnotation(reac, modelAnnotaInfo)

                #if reacAnnoInfo.keys() in ['xCord','yCord','bgColor','Color']:
                if not moose.exists(reaction_.path + '/info'):
                    reacInfo = moose.Annotator(reaction_.path + '/info')
                else:
                    reacInfo = moose.element(reaction_.path + '/info')
                for k, v in list(reacAnnoInfo.items()):
                    if k == 'xCord':
                        reacInfo.x = float(v)
                    elif k == 'yCord':
                        reacInfo.y = float(v)
                    elif k == 'bgColor':
                        reacInfo.color = v
                    elif k == 'Color':
                        reacInfo.textColor = v

                addSubPrd(reac, rName, "sub", reactSBMLIdMooseId, specInfoMap)
                addSubPrd(reac, rName, "prd", reactSBMLIdMooseId, specInfoMap)
                if reac.isSetKineticLaw():
                    klaw = reac.getKineticLaw()
                    mmsg = ""
                    errorFlag, mmsg, kfvalue, kbvalue = getKLaw(
                        model, klaw, reac.num_reactants,reac.num_products, rev, globparameterIdValue,funcDef,specInfoMap)
                    if not errorFlag:
                        msg = "Error while importing reaction \"" + \
                            rName + "\"\n Error in kinetics law "
                        if mmsg != "":
                            msg = msg + mmsg
                        return(errorFlag, msg)
                    else:
                        if reaction_.className == "Reac":
                            subn = reactSBMLIdMooseId[rName]["nSub"]
                            prdn = reactSBMLIdMooseId[rName]["nPrd"]
                            reaction_.Kf = kfvalue  # * pow(1e-3,subn-1)
                            reaction_.Kb = kbvalue  # * pow(1e-3,prdn-1)
                        elif reaction_.className == "MMenz":
                            reaction_.kcat = kfvalue
                            reaction_.Km = kbvalue
                        elif reaction_.className == "ConcChan":
                            reaction_.permeability = kfvalue
    for l in deletecplxMol:
        if moose.exists(l):
            moose.delete(moose.element(l))
    return (errorFlag, msg)


def getKLaw(model, klaw,noOfsub, noOfprd,rev, globparameterIdValue, funcDef, specMapList):
    parmValueMap = {}
    amt_Conc = "amount"
    value = 0.0
    np = klaw. getNumParameters()
    for pi in range(0, np):
        p = klaw.getParameter(pi)
        if (p.isSetId()):
            ids = p.getId()
        if (p.isSetValue()):
            value = p.getValue()
        parmValueMap[ids] = value
    ruleMemlist = []
    flag, msg = getMembers(klaw.getMath(), ruleMemlist)
    index = 0
    kfparm = ""
    kbparm = ""
    kfvalue = 0
    kbvalue = 0
    kfp = ""
    kbp = ""
    mssgstr = ""
    for i in ruleMemlist:
        if i in parmValueMap or i in globparameterIdValue:
            if index == 0:
                kfparm = i
                if i in parmValueMap:
                    kfvalue = parmValueMap[i]
                    kfp = klaw.getParameter(kfparm)
                else:
                    kfvalue = globparameterIdValue[i]
                    kfp = model.getParameter(kfparm)
            elif index == 1:
                kbparm = i
                if i in parmValueMap:
                    kbvalue = parmValueMap[i]
                    kbp = klaw.getParameter(kbparm)
                else:
                    kbvalue = globparameterIdValue[i]
                    kbp = model.getParameter(kbparm)
            index += 1
        elif not (i in specMapList or i in comptSbmlidMooseIdMap):
            mssgstr = "\"" + i + "\" is not defined "
            return (False, mssgstr, 0,0)

    if kfp != "":
        lvalue =1.0
        if kfp.isSetUnits():
            kfud = kfp.getDerivedUnitDefinition()
            lvalue = transformUnits( 1,kfud ,"substance",True)
        else:
            unitscale = 1
            if (noOfsub >1):
                #converting units to milli M for Moose
                #depending on the order of reaction,millifactor will calculated
                unitscale = unitsforRates(model)
                unitscale = unitscale*1000
                lvalue = pow(unitscale,1-noOfsub)
        kfvalue = kfvalue*lvalue;
            
    if kbp != "":
        lvalue = 1.0;
        if kbp.isSetUnits():
            kbud = kbp.getDerivedUnitDefinition()
        else:
            unitscale = 1
            if (noOfprd >1):
                unitscale = unitsforRates(model)
                unitscale = unitscale*1000
                lvalue = pow(unitscale,1-noOfprd)
        kbvalue = kbvalue*lvalue;
    return (True, mssgstr, kfvalue, kbvalue)

def transformUnits( mvalue, ud, type, hasonlySubUnit ):
    lvalue = mvalue;
    if (type == "compartment"): 
        if(ud.getNumUnits() == 0):
            unitsDefined = False
        else:
            for ut in range(0, ud.getNumUnits()):
                unit = ud.getUnit(ut)
            if ( unit.isLitre() ):
                exponent = unit.getExponent()
                multiplier = unit.getMultiplier()
                scale = unit.getScale()
                offset = unit.getOffset()
                lvalue *= pow( multiplier * pow(10.0,scale), exponent ) + offset
                # Need to check if spatial dimension is less than 3 then,
                # then volume conversion e-3 to convert cubicmeter shd not be done.
                #lvalue *= pow(1e-3,exponent)
                
    elif(type == "substance"):
        exponent = 1.0
        if(ud.getNumUnits() == 0):
            unitsDefined = False
        else:
            for ut in range(0, ud.getNumUnits()):
                unit = ud.getUnit(ut)
                if ( unit.isMole() ):
                    exponent = unit.getExponent()
                    multiplier = unit.getMultiplier()
                    scale = unit.getScale()
                    offset = unit.getOffset()
                    #scale+3 is to convert to milli moles for moose
                    lvalue *= pow( multiplier * pow(10.0,scale+3), exponent ) + offset
                
                elif (unit.isItem()):
                    exponent = unit.getExponent()
                    multiplier = unit.getMultiplier()
                    scale = unit.getScale()
                    offset = unit.getOffset()
                    lvalue *= pow( multiplier * pow(10.0,scale), exponent ) + offset
                else:
                    
                    exponent = unit.getExponent()
                    multiplier = unit.getMultiplier()
                    scale = unit.getScale()
                    offset = unit.getOffset()
                    lvalue *= pow( multiplier * pow(10.0,scale), exponent ) + offset
        return lvalue

def unitsforRates(model):
    lvalue =1;
    if model.getNumUnitDefinitions():
        for n in range(0,model.getNumUnitDefinitions()):
            ud = model.getUnitDefinition(n)
            for ut in range(0,ud.getNumUnits()):
                unit = ud.getUnit(ut)
                if (ud.getId() == "substance"):
                    if ( unit.isMole() ):
                        exponent = unit.getExponent();
                        multiplier = unit.getMultiplier();
                        scale = unit.getScale();
                        offset = unit.getOffset();
                        lvalue *= pow( multiplier * pow(10.0,scale), exponent ) + offset;
                        return lvalue
    else:
        return lvalue
def getMembers(node, ruleMemlist):
    msg = ''
    found = True
    if node is not None:
        nodetype = node.getType()
        if nodetype == libsbml.AST_POWER:
            # Keeping for future update
            pass
        elif nodetype == libsbml.AST_REAL or nodetype == libsbml.AST_INTEGER:
            pass
        elif nodetype == libsbml.AST_FUNCTION:
            for i in range(0,node.getNumChildren()):
                _, msg = getMembers(node.getChild(i),ruleMemlist)
        elif nodetype == libsbml.AST_PLUS and node.getNumChildren() > 0:
            getMembers(node.getChild(0), ruleMemlist)
            for i in range(1, node.getNumChildren()):
                # addition
                _, msg = getMembers(node.getChild(i), ruleMemlist)
        elif nodetype == libsbml.AST_NAME:
            # This will be the ci term"
            ruleMemlist.append(node.getName())
        elif nodetype == libsbml.AST_MINUS and node.getNumChildren() > 0:
            lchild = node.getLeftChild()
            _, msg = getMembers(lchild, ruleMemlist)
            rchild = node.getRightChild()
            _, tmp = getMembers(rchild, ruleMemlist)
            msg = '\n'.join([msg, tmp])
        elif nodetype == libsbml.AST_DIVIDE and node.getNumChildren() > 0:
            lchild = node.getLeftChild()
            _, msg = getMembers(lchild, ruleMemlist)
            rchild = node.getRightChild()
            _, tmp = getMembers(rchild, ruleMemlist)
            msg = '\n'.join([msg, tmp])
        elif nodetype == libsbml.AST_TIMES and node.getNumChildren() > 0:
            getMembers(node.getChild(0), ruleMemlist)
            for i in range(1, node.getNumChildren()):
                # Multiplication
                _, msg = getMembers(node.getChild(i), ruleMemlist)
        elif nodetype == libsbml.AST_LAMBDA and node.getNumChildren() > 0 and node.getNumBvars() > 0:
            #In lambda get Bvar values and getRighChild which will be kineticLaw
            for i in range (0,node.getNumBvars()):
                ruleMemlist.append(node.getChild(i).getName())
            #funcD[funcName] = {"bvar" : bvar, "MathML":node.getRightChild()}
        else:
            msg = f'{msg}\nmoose is yet to handle "{node.getName()}" operator'
            found = False
    return found, msg

def createRules(model, specInfoMap, globparameterIdValue):
    #This section where assigment, Algebraic, rate rules are converted
    #For now assignment rules are written and that too just summation of pools for now.
    msg = ""
    found = True
    for r in range(0, model.getNumRules()):
        rule = model.getRule(r)
        
        comptvolume = []

        if (rule.isAssignment()):
            rule_variable = rule.getVariable()
        
            if rule_variable in specInfoMap:
                #In assignment rule only if pool exist, then that is conveted to moose as 
                # this can be used as summation of pool's, P1+P2+P3 etc 
                rule_variable = parentSp = str(idBeginWith(rule_variable))
                poolList = specInfoMap[rule_variable]["Mpath"].path
                poolsCompt = findCompartment(moose.element(poolList))
                #If pool comes without a compartment which is not allowed moose
                #then returning with -2
                if not (moose.element(poolsCompt).isA("ChemCompt")):
                    return -2
                else:
                    if poolsCompt.name not in comptvolume:
                        comptvolume.append(poolsCompt.name)

                    ruleMath = rule.getMath()
                    #libsbml.writeMathMLToString(ruleMath)
                    ruleMemlist = []
                    speFunXterm = {}
                    found, msg = getMembers(ruleMath, ruleMemlist)

                    if found:
                        allPools = True
                        for i in ruleMemlist:
                            if i not in specInfoMap:
                                allPools = False
                                break
                        if allPools:
                            #only if addition then summation works, only then I create a function in moose
                            # which is need to get the summation's output to a pool
                            funcId = moose.Function(poolList + '/func')
                            index_var_map = {}
                            objclassname = moose.element(poolList).className
                            if objclassname == "BufPool" or objclassname == "ZombieBufPool":
                                moose.connect(funcId, 'valueOut', poolList, 'setN')
                            elif objclassname == "Pool" or objclassname == "ZombiePool":
                                # moose.connect( funcId, 'valueOut', poolList ,'increament' )
                                moose.connect(funcId, 'valueOut', poolList, 'setN')
                            elif objclassname == "Reac" or objclassname == "ZombieReac":
                                moose.connect(funcId, 'valueOut', poolList, 'setNumkf')
                            for i in ruleMemlist: 
                                if (i in specInfoMap):
                                    i = str(idBeginWith(i))
                                    specMapList = specInfoMap[i]["Mpath"]
                                    poolsCompt = findCompartment(moose.element(specMapList))
                                    if not (moose.element(poolsCompt).isA("ChemCompt")):
                                        return -2
                                    else:
                                        if poolsCompt.name not in comptvolume:
                                            comptvolume.append(poolsCompt.name)
                                    # numVars = funcId.numVars
                                    # x = funcId.path + '/x[' + str(numVars) + ']'
                                    # #speFunXterm[i] = 'x' + str(numVars)
                                    # speFunXterm['x'+str(numVars)] = i
                                    # moose.connect(specMapList, 'nOut', x, 'input')
                                    # funcId.numVars = numVars + 1
                                    specFunXterm[f'x{len(index_var_map)}'] = i
                                    index_var_map[len(index_var_map)] = (specMapList, 'nOut')
                                    

                                elif not(i in globparameterIdValue):
                                    msg = msg + "check the variable name in mathML, this object neither pool or a constant \"" + str(i)+"\" in assignmentRule " +rule.getVariable()

                                exp = rule.getFormula()
                                exprOK = True
                                #print " specFunXTerm ",speFunXterm
                            for mem in ruleMemlist:
                                if (mem in specInfoMap):
                                    #exp1 = exp.replace(mem, str(speFunXterm[mem]))
                                    #exp1 = re.sub(r'\b%s\b'% (mem), speFunXterm[mem], exp)
                                    exp1 = re.sub(r'\b%s\b'% (mem), list(speFunXterm.keys())[list(speFunXterm.values()).index(mem)], exp,1)
                                    speFunXterm.pop(list(speFunXterm.keys())[list(speFunXterm.values()).index(mem)])
                                    
                                    exp = exp1
                                elif(mem in globparameterIdValue):
                                    #exp1 = exp.replace(mem, str(globparameterIdValue[mem]))
                                    exp1 = re.sub(r'\b%s\b'% (mem), globparameterIdValue[mem], exp)
                                    exp = exp1
                                else:
                                    msg = msg +"Math expression need to be checked", exp
                                    exprOK = False
                            if exprOK:
                                exp = exp.replace(" ", "")
                                funcId.expr = exp.strip(" \t\n\r")
                                for index, (src, srcField) in index_var_map.items():
                                    moose.connect(src, srcField, funcId.x[index], 'input')
            else:
                msg = msg +"\nAssisgment Rule has parameter as variable, currently moose doesn't have this capability so ignoring."\
                          + rule.getVariable() + " is not converted to moose."
                found = False


                    
            
        elif(rule.isRate()):
            print(
                "Warning : For now this \"",
                rule.getVariable(),
                "\" rate Rule is not handled in moose ")
            # return False

        elif (rule.isAlgebraic()):
            print("Warning: For now this ", rule.getVariable(),
                  " Algebraic Rule is not handled in moose")
            # return False
        if len(comptvolume) > 1:
            warning = "\nFunction ", moose.element(
                poolList).name, " has input from different compartment which is depricated in moose and running this model cause moose to crash"
    return msg


def pullnotes(sbmlId, mooseId):
    if sbmlId.getNotes() is not None:
        tnodec = ((sbmlId.getNotes()).getChild(0)).getChild(0)
        notes = tnodec.getCharacters()
        notes = notes.strip(' \t\n\r')
        objPath = mooseId.path + "/info"
        if not moose.exists(objPath):
            objInfo = moose.Annotator(mooseId.path + '/info')
        else:
            objInfo = moose.element(mooseId.path + '/info')
        objInfo.notes = notes

def createSpecies(basePath, model, comptSbmlidMooseIdMap,
                  specInfoMap, modelAnnotaInfo,groupInfo):
    # ToDo:
    # - Need to add group name if exist in pool
    # - Notes
    # print "species "
    if not (model.getNumSpecies()):
        return (False,"number of species is zero")
    else:
        for sindex in range(0, model.getNumSpecies()):
            spe = model.getSpecies(sindex)
            group = ""
            specAnnoInfo = {}
            specAnnoInfo = getObjAnnotation(spe, modelAnnotaInfo)
            # if "Group" in specAnnoInfo:
            #     group = specAnnoInfo["Group"]

            sName = None
            sId = spe.getId()
            group = ""
            #groups = [k for k, v in groupInfo.items() if sId in v]
            for k,v in groupInfo.items():
                if sId in v["splist"]:
                    group = v["mpath"]
            # if groups:
            #     group = groups[0]
            if spe.isSetName():
                sName = spe.getName()
                #sName = sName.replace(" ", "_space_")

            if spe.isSetCompartment():
                comptId = spe.getCompartment()

            if not(sName):
                sName = sId

            constant = spe.getConstant()
            boundaryCondition = spe.getBoundaryCondition()
            comptEl = comptSbmlidMooseIdMap[comptId]["MooseId"].path
            hasonlySubUnit = spe.getHasOnlySubstanceUnits()
            # "false": is {unit of amount}/{unit of size} (i.e., concentration or density).
            # "true": then the value is interpreted as having a unit of amount only.
            if group:
                comptEl = group.path
                # if moose.exists(comptEl+'/'+group):
                #     comptEl = comptEl+'/'+group
                # else:
                #     comptEl = (moose.Neutral(comptEl+'/'+group)).path
            if (boundaryCondition):
                poolId = moose.BufPool(comptEl + '/' + sName)
            else:
                poolId = moose.Pool(comptEl + '/' + sName)
            if (spe.isSetNotes):
                pullnotes(spe, poolId)

            #if specAnnoInfo.keys() in ['xCord','yCord','bgColor','textColor']:
            if not moose.exists(poolId.path + '/info'):
                poolInfo = moose.Annotator(poolId.path + '/info')
            else:
                poolInfo = moose.element(poolId.path + '/info')

            for k, v in list(specAnnoInfo.items()):
                if k == 'xCord':
                    poolInfo.x = float(v)
                elif k == 'yCord':
                    poolInfo.y = float(v)
                elif k == 'bgColor':
                    poolInfo.color = v
                elif k == 'textColor':
                    poolInfo.textColor = v
                elif k == 'diffConstant':
                    poolId.diffConst = float(v)
                elif k == 'motorConstant':
                    poolId.motorConst = float(v)
            
            specInfoMap[sId] = {
                "Mpath": poolId,
                "const": constant,
                "bcondition": boundaryCondition,
                "hassubunit": hasonlySubUnit,
                "comptId": comptSbmlidMooseIdMap[comptId]["MooseId"]}
            initvalue = 0.0
            unitfactor, unitset, unittype = transformUnit(spe, hasonlySubUnit)
            if hasonlySubUnit == True:
                if spe.isSetInitialAmount():
                    initvalue = spe.getInitialAmount()
                    # populating nInit, will automatically calculate the
                    # concInit.
                    if not (unitset):
                        # if unit is not set,
                        # default unit is assumed as Mole in SBML
                        unitfactor = pow(6.0221409e23, 1)
                        unittype = "Mole"

                    initvalue = initvalue * unitfactor
                elif spe.isSetInitialConcentration():
                    initvalue = spe.getInitialConcentration()
                    print(" Since hasonlySubUnit is true and concentration is set units are not checked")
                poolId.nInit = initvalue

            elif hasonlySubUnit == False:
                # ToDo : check 00976
                if spe.isSetInitialAmount():
                    initvalue = spe.getInitialAmount()
                    # initAmount is set we need to convert to concentration
                    initvalue = initvalue / comptSbmlidMooseIdMap[comptId]["size"]

                elif spe.isSetInitialConcentration():
                    initvalue = spe.getInitialConcentration()
                if not unitset:
                    # print " unit is not set"
                    unitfactor = pow(10, -3)
                initvalue = initvalue * unitfactor

                poolId.concInit = initvalue
            else:
                nr = model.getNumRules()
                found = False
                for nrItem in range(0, nr):
                    rule = model.getRule(nrItem)
                    assignRule = rule.isAssignment()
                    if (assignRule):
                        rule_variable = rule.getVariable()
                        if (rule_variable == sId):
                            found = True
                            break

                if not (found):
                    print(
                        "Invalid SBML: Either initialConcentration or initialAmount must be set or it should be found in assignmentRule but non happening for ",
                        sName)
                    return (False,"Invalid SBML: Either initialConcentration or initialAmount must be set or it should be found in assignmentRule but non happening for ",sName)

    return (True," ")

def transformUnit(unitForObject, hasonlySubUnit=False):
    # print "unit
    # ",UnitDefinition.printUnits(unitForObject.getDerivedUnitDefinition())
    unitset = False
    unittype = None
    if (unitForObject.getDerivedUnitDefinition()):
        unit = (unitForObject.getDerivedUnitDefinition())
        unitnumber = int(unit.getNumUnits())
        if unitnumber > 0:
            for ui in range(0, unit.getNumUnits()):
                lvalue = 1.0
                unitType = unit.getUnit(ui)
                if(unitType.isLitre()):
                    exponent = unitType.getExponent()
                    multiplier = unitType.getMultiplier()
                    scale = unitType.getScale()
                    offset = unitType.getOffset()
                    # units for compartment is Litre but MOOSE compartment is
                    # m3
                    scale = scale - 3
                    lvalue *= pow(multiplier * pow(10.0, scale),
                                  exponent) + offset
                    unitset = True
                    unittype = "Litre"
                    return (lvalue, unitset, unittype)
                elif(unitType.isMole()):
                    exponent = unitType.getExponent()
                    multiplier = unitType.getMultiplier()
                    scale = unitType.getScale()
                    offset = unitType.getOffset()
                    # if hasOnlySubstanceUnit = True, then assuming Amount
                    if hasonlySubUnit == True:
                        lvalue *= pow(multiplier *
                                      pow(10.0, scale), exponent) + offset
                        # If SBML units are in mole then convert to number by
                        # multiplying with avogadro's number
                        lvalue = lvalue * pow(6.0221409e23, 1)
                    elif hasonlySubUnit == False:
                        # Pool units in moose is mM

                        lvalue = lvalue * pow(multiplier*pow(10.0,scale+3),exponent)+offset
                        # if scale > 0:
                        #     lvalue *= pow(multiplier * pow(10.0,
                        #                                    scale - 3), exponent) + offset
                        # elif scale <= 0:
                        #     lvalue *= pow(multiplier * pow(10.0,
                        #                                    scale + 3), exponent) + offset
                    unitset = True
                    unittype = "Mole"
                    return (lvalue, unitset, unittype)

                elif(unitType.isItem()):
                    exponent = unitType.getExponent()
                    multiplier = unitType.getMultiplier()
                    scale = unitType.getScale()
                    offset = unitType.getOffset()
                    # if hasOnlySubstanceUnit = True, then assuming Amount
                    if hasonlySubUnit == True:
                        # If SBML units are in Item then amount is populate as
                        # its
                        lvalue *= pow(multiplier *
                                      pow(10.0, scale), exponent) + offset
                    if hasonlySubUnit == False:
                        # hasonlySubUnit is False, which is assumed concentration,
                        # Here Item is converted to mole by dividing by
                        # avogadro and at initiavalue divided by volume"
                        lvalue *= pow(multiplier *
                                      pow(10.0, scale), exponent) + offset
                        lvalue = lvalue / pow(6.0221409e23, 1)
                    unitset = True
                    unittype = "Item"
                    return (lvalue, unitset, unittype)
        else:
            lvalue = 1.0
    return (lvalue, unitset, unittype)


def createCompartment(basePath, model, comptSbmlidMooseIdMap):
    # ToDoList : Check what should be done for the spaitialdimension is 2 or
    # 1, area or length
    cmptAnnotaInfo = {}
    
    if not(model.getNumCompartments()):
        return False, "Model has no compartment, atleast one compartment should exist to display in the widget"
    else:
        endo_surr = {}
        toRewritebasepath = True
        for c in range(0, model.getNumCompartments()):
            compt = model.getCompartment(c)
            # print("Compartment " + str(c) + ": "+ UnitDefinition.printUnits(compt.getDerivedUnitDefinition()))
            msize = 0.0
            unitfactor = 1.0
            sbmlCmptId = None
            name = None

            if (compt.isSetId()):
                sbmlCmptId = compt.getId()

            if (compt.isSetName()):
                name = compt.getName()
                #name = name.replace(" ", "_space")

            if (compt.isSetOutside()):
                outside = compt.getOutside()

            if (compt.isSetSize()):
                msize = compt.getSize()
                if msize == 1:
                    print("Compartment size is 1")

            dimension = compt.getSpatialDimensions()
            if dimension == 3:
                unitfactor, unitset, unittype = transformUnit(compt)

            else:
                return False," Currently we don't deal with spatial Dimension less than 3 and unit's area or length" 

            if not(name):
                name = sbmlCmptId
            cmptAnnotaInfo = {}
            cmptAnnotaInfo = getCmptAnnotation(compt)
            if "basePath" in cmptAnnotaInfo.keys():
                nl = list(filter(None, (cmptAnnotaInfo["basePath"]).split('/')))
                pathAnno = ""
                if len(nl) > 0:
                    for i in range(0,len(nl)):
                        pathAnno = pathAnno+'/'+nl[i]
                        if not moose.exists(basePath.path+pathAnno):
                            rewritebasepath = moose.Neutral(basePath.path+pathAnno)
                if toRewritebasepath:
                    basePath = rewritebasepath
                    toRewritebasepath = False
                
            if "Mesh" in cmptAnnotaInfo.keys():
                if cmptAnnotaInfo["Mesh"] == "CubeMesh" or cmptAnnotaInfo["Mesh"] == "NeuroMesh":
                    mooseCmptId = moose.CubeMesh(basePath.path + '/' + name)
                
                elif cmptAnnotaInfo["Mesh"] == "CylMesh":
                    mooseCmptId = moose.CylMesh(basePath.path + '/' + name)
                    ln = (float(cmptAnnotaInfo["totLength"])/float(cmptAnnotaInfo["diffLength"]))*float(cmptAnnotaInfo["diffLength"])
                    mooseCmptId.x1 = ln
                    mooseCmptId.diffLength = float(cmptAnnotaInfo["diffLength"])
                
                elif cmptAnnotaInfo["Mesh"] == "EndoMesh":
                    mooseCmptId = moose.EndoMesh(basePath.path + '/' + name)
                    endo_surr[sbmlCmptId] = cmptAnnotaInfo["surround"]

                if cmptAnnotaInfo["isMembraneBound"] == 'True':
                    mooseCmptId.isMembraneBound = bool(cmptAnnotaInfo["isMembraneBound"])
            else:
                mooseCmptId = moose.CubeMesh(basePath.path+'/'+name)
            
            mooseCmptId.volume = (msize * unitfactor)
            #both compartment name and Id is mapped to the values
            comptSbmlidMooseIdMap.update(dict.fromkeys([sbmlCmptId,name], {"MooseId": mooseCmptId, "spatialDim": dimension, "size": msize}))
            #comptSbmlidMooseIdMap[sbmlCmptId] = {
            #    "MooseId": mooseCmptId, "spatialDim": dimension, "size": msize}
        for key,value in endo_surr.items():
            if value in comptSbmlidMooseIdMap:
                endomesh = comptSbmlidMooseIdMap[key]["MooseId"]
                endomesh.surround = comptSbmlidMooseIdMap[value]["MooseId"]
            elif key in comptSbmlidMooseIdMap:
                del(comptSbmlidMooseIdMap[key])
                return False," EndoMesh's surrounding compartment missing or wrong deleting the compartment check the file"
    return True,"",basePath

def setupConcChannel(reac, rName, specInfoMap, reactSBMLIdMooseId,
                          modelAnnotaInfo, model, globparameterIdValue):
    msg = ""
    errorFlag = ""
    numRcts = reac.getNumReactants()
    numPdts = reac.getNumProducts()
    nummodifiers = reac.getNumModifiers()
    if (nummodifiers):
        parent = reac.getModifier(0)
        parentSp = parent.getSpecies()
        parentSp = str(idBeginWith(parentSp))
        enzParent = specInfoMap[parentSp]["Mpath"]
        ConcChan = moose.ConcChan(enzParent.path + '/' + rName)
        moose.connect(enzParent, "nOut", ConcChan, "setNumChan")
        channelCreated = True
        if channelCreated:
            return (channelCreated,ConcChan)

def setupMMEnzymeReaction(reac, rName, specInfoMap, reactSBMLIdMooseId,
                          modelAnnotaInfo, model, globparameterIdValue):
    msg = ""
    errorFlag = ""
    numRcts = reac.getNumReactants()
    numPdts = reac.getNumProducts()
    nummodifiers = reac.getNumModifiers()
    if (nummodifiers):
        parent = reac.getModifier(0)
        parentSp = parent.getSpecies()
        parentSp = str(idBeginWith(parentSp))
        enzParent = specInfoMap[parentSp]["Mpath"]
        MMEnz = moose.MMenz(enzParent.path + '/' + rName)
        moose.connect(enzParent, "nOut", MMEnz, "enzDest")
        reactionCreated = True
        reactSBMLIdMooseId[rName] = {"MooseId": MMEnz}
        if reactionCreated:
            if (reac.isSetNotes):
                pullnotes(reac, MMEnz)
                reacAnnoInfo = {}
                reacAnnoInfo = getObjAnnotation(reac, modelAnnotaInfo)

                #if reacAnnoInfo.keys() in ['xCord','yCord','bgColor','Color']:
                if not moose.exists(MMEnz.path + '/info'):
                    reacInfo = moose.Annotator(MMEnz.path + '/info')
                else:
                    reacInfo = moose.element(MMEnz.path + '/info')
                for k, v in list(reacAnnoInfo.items()):
                    if k == 'xCord':
                        reacInfo.x = float(v)
                    elif k == 'yCord':
                        reacInfo.y = float(v)
                    elif k == 'bgColor':
                        reacInfo.color = v
                    elif k == 'Color':
                        reacInfo.textColor = v
            return(reactionCreated, MMEnz)


def mapParameter(model, globparameterIdValue):
    for pm in range(0, model.getNumParameters()):
        prm = model.getParameter(pm)
        if (prm.isSetId()):
            parid = prm.getId()
        value = 0.0
        if (prm.isSetValue()):
            value = prm.getValue()
        globparameterIdValue[parid] = value


def idBeginWith(name):
    changedName = name
    if name[0].isdigit():
        changedName = "_" + name
    return changedName


def convertSpecialChar(str1):
    # d = {"&": "_and", "<": "_lessthan_", ">": "_greaterthan_", "BEL": "&#176", "-": "_minus_", "'": "_prime_",
    #      "+": "_plus_", "*": "_star_", "/": "_slash_", "(": "_bo_", ")": "_bc_",
    #      "[": "_sbo_", "]": "_sbc_", " ": "_"
    #      }
    d = {"BEL": "&#176" , "'": "_prime_", "/": "_slash_"   ,"[": "_sbo_", "]": "_sbc_",
         "#"  :"_hash_" , "\"":"_quote_" , "?":"_question_" ,"\\":"_slash","&":"_and_","<":"_greater_"
         }
    for i, j in list(d.items()):
        str1 = str1.replace(i, j)
    return str1

if __name__ == "__main__":
    try:
        sys.argv[1]
    except IndexError:
        print("Filename or path not given")
        exit(0)
    else:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print("Filename or path does not exist",filepath)

        else:
            try:
                sys.argv[2]
            except :
                modelpath = filepath[filepath.rfind('/'):filepath.find('.')]
            else:
                modelpath = sys.argv[2]
            read = mooseReadSBML(filepath, modelpath)
            if read:
                print(" Model read to moose path "+ modelpath)
            else:
                print(" could not read  SBML to MOOSE")
