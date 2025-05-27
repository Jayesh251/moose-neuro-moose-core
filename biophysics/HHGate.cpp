/**********************************************************************
 ** This program is part of 'MOOSE', the
 ** Messaging Object Oriented Simulation Environment.
 **           Copyright (C) 2003-2007 Upinder S. Bhalla. and NCBS
 ** It is made available under the terms of the
 ** GNU Lesser General Public License version 2.1
 ** See the file COPYING.LIB for the full notice.
 **********************************************************************/

#include <cmath>
#include "../utility/strutil.h"
#include "exprtk.hpp"
#include "../basecode/header.h"
#include "../basecode/ElementValueFinfo.h"
#include "../builtins/MooseParser.h"
#include "HHGateBase.h"
#include "HHGate.h"

static const double SINGULARITY = 1.0e-6;

const Cinfo* HHGate::initCinfo()
{
    ///////////////////////////////////////////////////////
    // Field definitions.
    ///////////////////////////////////////////////////////
    static ReadOnlyLookupValueFinfo<HHGate, double, double> A(
        "A",
        "lookupA: Look up the A gate value from a double. Usually does"
        "so by direct scaling and offset to an integer lookup, using"
        "a fine enough table granularity that there is little error."
        "Alternatively uses linear interpolation."
        "The range of the double is predefined based on knowledge of"
        "voltage or conc ranges, and the granularity is specified by"
        "the min, max, and divs fields.",
        &HHGate::lookupA);
    static ReadOnlyLookupValueFinfo<HHGate, double, double> B(
        "B",
        "lookupB: Look up the B gate value from a double."
        "Note that this looks up the raw tables, which are transformed"
        "from the reference parameters.",
        &HHGate::lookupB);

    static ElementValueFinfo<HHGate, vector<double>> alpha(
        "alpha",
        "Parameters for voltage-dependent rates, alpha:"
        "Set up alpha term using 5 parameters, as follows:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "The original HH equations can readily be cast into this form",
        &HHGate::setAlpha, &HHGate::getAlpha);

    static ElementValueFinfo<HHGate, vector<double>> beta(
        "beta",
        "Parameters for voltage-dependent rates, beta:"
        "Set up beta term using 5 parameters, as follows:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "The original HH equations can readily be cast into this form",
        &HHGate::setBeta, &HHGate::getBeta);

    static ElementValueFinfo<HHGate, vector<double>> tau(
        "tau",
        "Parameters for voltage-dependent rates, tau:"
        "Set up tau curve using 5 parameters, as follows:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))",
        &HHGate::setTau, &HHGate::getTau);

    static ElementValueFinfo<HHGate, vector<double>> mInfinity(
        "mInfinity", "Deprecated. Use `inf` instead.", &HHGate::setMinfinity,
        &HHGate::getMinfinity);

    static ElementValueFinfo<HHGate, vector<double>> inf(
        "inf",
        "Parameters for voltage-dependent rates, inf:"
        "Set up inf curve using 5 parameters, as follows:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "The original HH equations can readily be cast into this form",
        &HHGate::setMinfinity, &HHGate::getMinfinity);

    static ElementValueFinfo<HHGate, string> alphaExpr(
        "alphaExpr",
        "Explicit expression for computing `alpha`."
        " For using this, `betaExpr` must be set as well.\n"
        " SYNTAX: The expression evaluation uses exprtk syntax,"
        " with predefined variables `alpha`, `beta`, `tau`, `inf`, and `v`."
        " `v` is the input variable, the others can be used as"
        " local variables for intermediate computations.\n"
        "Example:\n"
        "~(alpha:=0.3 * exp(-80 * (v -(-46e-3))) + 3.5,"
        "alpha < 3.8? 3.8: alpha)\n"
        " first computes a local variable `alpha` by the first formula,"
        " and if it is < 3.8 then returns 3.8, otherwise returns the"
        " computed value.",
        &HHGate::setAlphaExpr, &HHGate::getAlphaExpr);

    static ElementValueFinfo<HHGate, string> betaExpr(
        "betaExpr",
        "Explicit expression for computing `beta`."
        " For using this, `alphaExpr` must be set as well."
        " See `alphaExpr` and `HHChannelF` documentation.",
        &HHGate::setBetaExpr, &HHGate::getBetaExpr);

    static ElementValueFinfo<HHGate, string> tauExpr(
        "tauExpr",
        "Explicit expression for computing `tau`."
        " For using this, `infExpr` must be set as well."
        " See `alphaExpr` and `HHChannelF` documentation.",
        &HHGate::setTauExpr, &HHGate::getTauExpr);

    static ElementValueFinfo<HHGate, string> infExpr(
        "infExpr",
        "Explicit expression for computing `inf`."
        " When using this, `tauExpr` must be set as well."
        " See `alphaExpr` and `HHChannelF` documentation.",
        &HHGate::setInfExpr, &HHGate::getInfExpr);

    static ElementValueFinfo<HHGate, double> min(
        "min", "Minimum range for lookup", &HHGate::setMin, &HHGate::getMin);

    static ElementValueFinfo<HHGate, double> max(
        "max", "Minimum range for lookup", &HHGate::setMax, &HHGate::getMax);

    static ElementValueFinfo<HHGate, unsigned int> divs(
        "divs", "Divisions for lookup. Zero means to use linear interpolation",
        &HHGate::setDivs, &HHGate::getDivs);

    static ElementValueFinfo<HHGate, vector<double>> tableA(
        "tableA", "Table of A entries", &HHGate::setTableA, &HHGate::getTableA);

    static ElementValueFinfo<HHGate, vector<double>> tableB(
        "tableB", "Table of alpha + beta entries", &HHGate::setTableB,
        &HHGate::getTableB);

    static ElementValueFinfo<HHGate, bool> useInterpolation(
        "useInterpolation",
        "Flag: use linear interpolation if true, else direct lookup",
        &HHGate::setUseInterpolation, &HHGate::getUseInterpolation);

    static ReadOnlyValueFinfo<HHGate, int> form(
        "form",
        "Form of the gate specification:\n 0 for old-style tables,\n"
        " 1 for expression string in alpha-beta form, and\n"
        " 2 for expression string in tau-inf form.\n"
        "This is set automatically when the user assigns the gate"
        " tables or the expressions.",
        &HHGate::getForm);

    static ElementValueFinfo<HHGate, vector<double>> alphaParms(
        "alphaParms",
        "Set up both gates using 13 parameters, as follows:"
        "setupAlpha AA AB AC AD AF BA BB BC BD BF xdivs xmin xmax"
        "Here AA-AF are Coefficients A to F of the alpha (forward) term"
        "Here BA-BF are Coefficients A to F of the beta (reverse) term"
        "Here xdivs is the number of entries in the table,"
        "xmin and xmax define the range for lookup."
        "Outside this range the returned value will be the low [high]"
        "entry of the table."
        "The equation describing each table is:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "The original HH equations can readily be cast into this form",
        &HHGate::setupAlpha, &HHGate::getAlphaParms);

    ///////////////////////////////////////////////////////
    // DestFinfos
    ///////////////////////////////////////////////////////
    static DestFinfo setupAlpha(
        "setupAlpha",
        "Set up both gates using 13 parameters, as follows:"
        "setupAlpha AA AB AC AD AF BA BB BC BD BF xdivs xmin xmax"
        "Here AA-AF are Coefficients A to F of the alpha (forward) term"
        "Here BA-BF are Coefficients A to F of the beta (reverse) term"
        "Here xdivs is the number of entries in the table,"
        "xmin and xmax define the range for lookup."
        "Outside this range the returned value will be the low [high]"
        "entry of the table."
        "The equation describing each table is:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "The original HH equations can readily be cast into this form",
        new EpFunc1<HHGate, vector<double>>(&HHGate::setupAlpha));
    static DestFinfo setupTau(
        "setupTau",
        "Identical to setupAlpha, except that the forms specified by"
        "the 13 parameters are for the tau and m-infinity curves rather"
        "than the alpha and beta terms. So the parameters are:"
        "setupTau TA TB TC TD TF MA MB MC MD MF xdivs xmin xmax"
        "As before, the equation describing each curve is:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))",
        new EpFunc1<HHGate, vector<double>>(&HHGate::setupTau));
    static DestFinfo tweakAlpha(
        "tweakAlpha",
        "Dummy function for backward compatibility. It used to convert"
        "the tables from alpha, beta values to alpha, alpha+beta"
        "because the internal calculations used these forms. Not"
        "needed now, deprecated.",
        new OpFunc0<HHGate>(&HHGate::tweakAlpha));
    static DestFinfo tweakTau(
        "tweakTau",
        "Dummy function for backward compatibility. It used to convert"
        "the tables from tau, inf values to alpha, alpha+beta"
        "because the internal calculations used these forms. Not"
        "needed now, deprecated.",
        new OpFunc0<HHGate>(&HHGate::tweakTau));
    static DestFinfo setupGate(
        "setupGate",
        "Sets up one gate at a time using the alpha/beta form."
        "Has 9 parameters, as follows:"
        "setupGate A B C D F xdivs xmin xmax is_beta"
        "This sets up the gate using the equation:"
        "y(x) = (A + B * x) / (C + exp((x + D) / F))"
        "Deprecated.",
        new EpFunc1<HHGate, vector<double>>(&HHGate::setupGate));
    static DestFinfo tabFillExpr(
        "tabFillExpr",
        "If the gating variables are specified as string expressions"
        " (alphaExpr/betaExpr/tauExpr/infExpr), then fill up the"
        " tables by evaluating the expressions. This function is"
        " for debugging. If assigned, the expressions are evaluated to fill"
        " the tables at `reinit()`",
        new EpFunc0<HHGate>(&HHGate::tabFillExpr));

    static Finfo* HHGateFinfos[] = {
        &A,          // ReadOnlyLookupValue
        &B,          // ReadOnlyLookupValue
        &alpha,      // ElementValue
        &beta,       // ElementValue
        &tau,        // ElementValue
        &mInfinity,  // ElementValue
        &inf,        // ElementValue
        &alphaExpr,
        &betaExpr,
        &tauExpr,
        &infExpr,
        &min,               // ElementValue
        &max,               // ElementValue
        &divs,              // ElementValue
        &tableA,            // ElementValue
        &tableB,            // ElementValue
        &useInterpolation,  // ElementValue
        &alphaParms,        // ElementValue
        &setupAlpha,        // Dest
        &setupTau,          // Dest
        &tweakAlpha,        // Dest
        &tweakTau,          // Dest
        &setupGate,         // Dest
        &tabFillExpr,       // Dest
    };

    static string doc[] = {
        "Name",
        "HHGate",
        "Author",
        "Upinder S. Bhalla, 2011, NCBS. Updates by Subhasis Ray, 2025, CHINTA",
        "Description",
        "HHGate: Gate for Hodkgin-Huxley type channels, equivalent to the"
        " m and h terms on the Na squid channel and the n term on K."
        " This takes the voltage and state variable from the channel,"
        " computes the new value of the state variable and a scaling,"
        " depending on gate power, for the conductance.\n"
	"This class uses a pair of lookup tables to quickly"
	" find the gating terms for a given voltage.\n"
	"To populate the tables one can directly assign precomputed arrays"
	" to `tableA` and `tableB` fields, or use specify string equations"
	" for `alphaExpr/betaExpr` or `tauExpr/infExpr`."
	" This requires the fields the range of input voltages be specified"
	" through the fields `min`, `max` and `divs`.\n"
	" When the gate equations can be expressed in the standard form"
	" `y(x) = (A + B * x) / (C + exp((x + D) / F))` one can "
	" set `alphaParms` or call `setupAlpha()` or `setupTau()`"
	" functions with the proper arguments to setup the tables."
	,
    };

    static Dinfo<HHGate> dinfo;
    static Cinfo HHGateCinfo("HHGate", Neutral::initCinfo(), HHGateFinfos,
                             sizeof(HHGateFinfos) / sizeof(Finfo*), &dinfo, doc,
                             sizeof(doc) / sizeof(string));

    return &HHGateCinfo;
}

static const Cinfo* hhGateCinfo = HHGate::initCinfo();
///////////////////////////////////////////////////
// Core class functions
///////////////////////////////////////////////////
HHGate::HHGate()
    : HHGateBase(0, 0),
      xmin_(0),
      xmax_(1),
      invDx_(1),
      form_(0),
      alphaExpr_(""),
      betaExpr_(""),
      lookupByInterpolation_(0),
      isDirectTable_(0)
{
    cerr << "# HHGate::HHGate() should never be called" << endl;
}

HHGate::HHGate(Id originalChanId, Id originalGateId)
    : HHGateBase(originalChanId, originalGateId),
      A_(1, 0.0),
      B_(1, 0.0),
      xmin_(0),
      xmax_(1),
      invDx_(1),
      form_(0),
      alphaExpr_(""),
      betaExpr_(""),
      lookupByInterpolation_(0),
      isDirectTable_(0)
{
    ;
}

///////////////////////////////////////////////////
// Field function definitions
///////////////////////////////////////////////////

double HHGate::lookupTable(const vector<double>& tab, double v) const
{
    if(v <= xmin_)
        return tab[0];
    if(v >= xmax_)
        return tab.back();
    if(lookupByInterpolation_) {
        unsigned int index = static_cast<unsigned int>((v - xmin_) * invDx_);
        assert(tab.size() > index);
        double frac = (v - xmin_ - index / invDx_) * invDx_;
        return tab[index] * (1 - frac) + tab[index + 1] * frac;
    }
    else {
        return tab[static_cast<unsigned int>((v - xmin_) * invDx_)];
    }
}

double HHGate::lookupA(double v) const
{
    return lookupTable(A_, v);
}

double HHGate::lookupB(double v) const
{
    return lookupTable(B_, v);
}

void HHGate::lookupBoth(double v, double* A, double* B) const
{
    if(v <= xmin_) {
        *A = A_[0];
        *B = B_[0];
    }
    else if(v >= xmax_) {
        *A = A_.back();
        *B = B_.back();
    }
    else {
        unsigned int index = static_cast<unsigned int>((v - xmin_) * invDx_);
        assert(A_.size() > index && B_.size() > index);
        if(lookupByInterpolation_) {
            double frac = (v - xmin_ - index / invDx_) * invDx_;
            *A = A_[index] * (1 - frac) + A_[index + 1] * frac;
            *B = B_[index] * (1 - frac) + B_[index + 1] * frac;
        }
        else {
            *A = A_[index];
            *B = B_[index];
        }
    }
}

vector<double> HHGate::getAlpha(const Eref& e) const
{
    return alpha_;
}

void HHGate::setAlpha(const Eref& e, vector<double> val)
{
    if(val.size() != 5) {
        cout << "Error: HHGate::setAlpha on " << e.id().path()
             << ": Number of entries on argument vector should be 5, was "
             << val.size() << endl;
        return;
    }
    if(checkOriginal(e.id(), "alpha")) {
        alpha_ = val;
        updateTauMinf();
        updateTables();
    }
}

vector<double> HHGate::getBeta(const Eref& e) const
{
    return beta_;
}

void HHGate::setBeta(const Eref& e, vector<double> val)
{
    if(val.size() != 5) {
        cout << "Error: HHGate::setBeta on " << e.id().path()
             << ": Number of entries on argument vector should be 5, was "
             << val.size() << endl;
        return;
    }
    if(checkOriginal(e.id(), "beta")) {
        beta_ = val;
        updateTauMinf();
        updateTables();
    }
}

vector<double> HHGate::getTau(const Eref& e) const
{
    return tau_;
}

void HHGate::setTau(const Eref& e, vector<double> val)
{
    if(val.size() != 5) {
        cout << "Error: HHGate::setTau on " << e.id().path()
             << ": Number of entries on argument vector should be 5, was "
             << val.size() << endl;
        return;
    }
    if(checkOriginal(e.id(), "tau")) {
        tau_ = val;
        updateAlphaBeta();
        updateTables();
    }
}

vector<double> HHGate::getMinfinity(const Eref& e) const
{
    return mInfinity_;
}

void HHGate::setMinfinity(const Eref& e, vector<double> val)
{
    if(val.size() != 5) {
        cout << "Error: HHGate::setMinfinity on " << e.id().path()
             << ": Number of entries on argument vector should be 5, was "
             << val.size() << endl;
        return;
    }
    if(checkOriginal(e.id(), "mInfinity")) {
        mInfinity_ = val;
        updateAlphaBeta();
        updateTables();
    }
}

/// Utility function to fill singularities with interpolated values
void fixSingularities(vector<double>& tab)
{
    int prev, next;
    double dy;

    for(int ii = 0; ii < tab.size();
        ++ii) {  // Little chance, but look for possibly multiple patches of
                 // discontinuity
        if(std::isnan(tab[ii]) || std::isinf(tab[ii]) ||
           fabs(tab[ii]) < SINGULARITY) {
            prev = ii - 1;
            next = ii + 1;
            while((next < tab.size()) &&
                  (std::isnan(tab[next]) || std::isinf(tab[next]) ||
                   fabs(tab[next]) < SINGULARITY)) {
                ++next;
            }
            if(next >= tab.size()) {  // all entries till end are invalid,
                                      // extrapolate
                assert(prev >= 1);
                dy = tab[prev] - tab[prev - 1];
            }
            else {
                dy = (tab[next] - tab[prev]) / (next - prev);
            }
            for(int jj = prev + 1; jj < next; ++jj) {
                tab[jj] = tab[jj - 1] + dy;
            }
            ii = next;
        }
    }
}

// Fill the A/B tables by evaluating gate formulae
void HHGate::tabFillExpr(const Eref& e)
{
    if(form_ == 0) {
        return;
    }
    exprtk::symbol_table<double> symTab_;
    exprtk::expression<double> alpha_;
    exprtk::expression<double> beta_;
    exprtk::parser<double> parser_;
    double v_;
    // Add extra variables to allow intermediate expressions for cases
    // where there is conditional on alpha/beta or tau/inf values
    double a_;
    double b_;
    double tau_;
    double inf_;
    symTab_.add_variable("v", v_);
    symTab_.add_variable("alpha", a_);
    symTab_.add_variable("beta", b_);
    symTab_.add_variable("tau", tau_);
    symTab_.add_variable("inf", inf_);
    symTab_.add_constants();
    alpha_.register_symbol_table(symTab_);
    beta_.register_symbol_table(symTab_);

    if(moose::trim(alphaExpr_).length() == 0) {
        cerr << "Error: Element: " << e.objId().path()
             << ": HHGate::tabFillExpr: empty expression for A" << endl;
        return;
    }
    if(!parser_.compile(alphaExpr_, alpha_)) {
        cerr << "Error: Element: " << e.objId().path()
             << ": HHGate::tabFillExpr: cannot compile expression!\n"
             << alphaExpr_ << endl
             << parser_.error() << endl;
        return;
    }
    if(moose::trim(alphaExpr_).length() == 0) {
        cerr << "Error: Element: " << e.objId().path()
             << ": HHGate::tabFillExpr: empty expression for B" << endl;
        return;
    }
    if(!parser_.compile(betaExpr_, beta_)) {
        cerr << "Error: Element: " << e.objId().path()
             << ": HHGate::tabFillExpr: cannot compile expression!\n"
             << betaExpr_ << endl
             << parser_.error() << endl;
        return;
    }
    if((xmax_ == 1) && (xmin_ == 0)) {
        cout << "Warning: " << e.objId().path()
             << ": HHGate::tabFillExpr: `min` and `max` have default values. "
                "Did you forget to"
             << " set them?" << endl;
    }
    unsigned int xdivs = A_.size() - 1;
    assert(A_.size() == B_.size());
    invDx_ = static_cast<double>(xdivs) / (xmax_ - xmin_);
    double dv = (xmax_ - xmin_) / xdivs;
    for(int ii = 0; ii <= xdivs; ++ii) {
        v_ = xmin_ + ii * dv;
        // Check singularity to avoid division by 0/nan values
        double a_{alpha_.value()}, b_{beta_.value()};
        if(form_ == 1) {  // alpha/beta
            b_ += a_;     // B = alpha + beta
            A_[ii] = a_;
            B_[ii] = b_;
        }
        else {  // form = 2, tau/inf
            B_[ii] = 1 / a_;
            A_[ii] = b_ / a_;
        }
    }
    // interpolate out nan and inf or small values
    fixSingularities(A_);
    fixSingularities(B_);
}

string HHGate::getAlphaExpr(const Eref& e) const
{
    return form_ == 1 ? alphaExpr_ : "";
}

void HHGate::setAlphaExpr(const Eref& e, string expr)
{
    if(checkOriginal(e.id(), "alphaExpr")) {
        form_ = 1;
        alphaExpr_ = expr;
    }
}

string HHGate::getBetaExpr(const Eref& e) const
{
    return form_ == 1 ? betaExpr_ : "";
}

void HHGate::setBetaExpr(const Eref& e, string expr)
{
    if(checkOriginal(e.id(), "betaExpr")) {
        form_ = 1;
        betaExpr_ = expr;
    }
}

string HHGate::getTauExpr(const Eref& e) const
{
    return form_ == 2 ? alphaExpr_ : "";
}

void HHGate::setTauExpr(const Eref& e, string expr)
{
    if(checkOriginal(e.id(), "tauExpr")) {
        form_ = 2;
        alphaExpr_ = expr;
    }
}

string HHGate::getInfExpr(const Eref& e) const
{
    return form_ == 2 ? betaExpr_ : "";
}

void HHGate::setInfExpr(const Eref& e, string expr)
{
    if(checkOriginal(e.id(), "infExpr")) {
        form_ = 2;
        betaExpr_ = expr;
    }
}

int HHGate::getForm() const
{
    return form_;
}

double HHGate::getMin(const Eref& e) const
{
    return xmin_;
}

void HHGate::setMin(const Eref& e, double val)
{
    if(checkOriginal(e.id(), "min")) {
        xmin_ = val;
        unsigned int xdivs = A_.size() - 1;
        if(isDirectTable_ && xdivs > 0) {
            // Stuff here to stretch out table using interpolation.
            invDx_ = static_cast<double>(xdivs) / (xmax_ - val);
            tabFill(A_, xdivs, val, xmax_);
            tabFill(B_, xdivs, val, xmax_);
        }
        else {
            updateTables();
        }
    }
}

double HHGate::getMax(const Eref& e) const
{
    return xmax_;
}

void HHGate::setMax(const Eref& e, double val)
{
    if(checkOriginal(e.id(), "max")) {
        xmax_ = val;
        unsigned int xdivs = A_.size() - 1;
        if(isDirectTable_ && xdivs > 0) {
            // Set up using direct assignment of table values.
            invDx_ = static_cast<double>(xdivs) / (val - xmin_);
            tabFill(A_, xdivs, xmin_, val);
            tabFill(B_, xdivs, xmin_, val);
        }
        else {
            // Set up using functional form. here we just recalculate.
            updateTables();
        }
    }
}

unsigned int HHGate::getDivs(const Eref& e) const
{
    return A_.size() - 1;
}

void HHGate::setDivs(const Eref& e, unsigned int val)
{
    if(checkOriginal(e.id(), "divs")) {
        if(isDirectTable_) {
            invDx_ = static_cast<double>(val) / (xmax_ - xmin_);
            tabFill(A_, val, xmin_, xmax_);
            tabFill(B_, val, xmin_, xmax_);
        }
        else {
            /// Stuff here to redo sizes.
            A_.resize(val + 1);
            B_.resize(val + 1);
            invDx_ = static_cast<double>(val) / (xmax_ - xmin_);
            updateTables();
        }
    }
}

vector<double> HHGate::getTableA(const Eref& e) const
{
    return A_;
}

void HHGate::setTableA(const Eref& e, vector<double> v)
{
    if(v.size() < 2) {
        cout << "Warning: HHGate::setTableA: size must be >= 2 entries on "
             << e.id().path() << endl;
        return;
    }
    if(checkOriginal(e.id(), "tableA")) {
        isDirectTable_ = 1;
        A_ = v;
        unsigned int xdivs = A_.size() - 1;
        invDx_ = static_cast<double>(xdivs) / (xmax_ - xmin_);
        form_ = 0;
    }
}

vector<double> HHGate::getTableB(const Eref& e) const
{
    return B_;
}

void HHGate::setTableB(const Eref& e, vector<double> v)
{
    if(checkOriginal(e.id(), "tableB")) {
        isDirectTable_ = 1;
        if(A_.size() != v.size()) {
            cout << "Warning: HHGate::setTableB: size should be same as table "
                    "A: "
                 << v.size() << " != " << A_.size() << ". Ignoring.\n";
            return;
        }
        B_ = v;
        form_ = 0;
    }
}

bool HHGate::getUseInterpolation(const Eref& e) const
{
    return lookupByInterpolation_;
}

void HHGate::setUseInterpolation(const Eref& e, bool val)
{
    if(checkOriginal(e.id(), "useInterpolation"))
        lookupByInterpolation_ = val;
}

void HHGate::setupAlpha(const Eref& e, vector<double> parms)
{
    if(checkOriginal(e.id(), "setupAlpha")) {
        if(parms.size() != 13) {
            cout << "HHGate::setupAlpha: Error: parms.size() != 13\n";
            return;
        }
        setupTables(parms, false);
        alpha_.resize(5, 0);
        beta_.resize(5, 0);
        for(unsigned int i = 0; i < 5; ++i)
            alpha_[i] = parms[i];
        for(unsigned int i = 5; i < 10; ++i)
            beta_[i - 5] = parms[i];
        form_ = 0;
    }
}

vector<double> HHGate::getAlphaParms(const Eref& e) const
{
    vector<double> ret = alpha_;
    ret.insert(ret.end(), beta_.begin(), beta_.end());
    ret.push_back((double)A_.size());
    ret.push_back(xmin_);
    ret.push_back(xmax_);

    return ret;
}

///////////////////////////////////////////////////
// Dest function definitions
///////////////////////////////////////////////////

void HHGate::setupTau(const Eref& e, vector<double> parms)
{
    if(checkOriginal(e.id(), "setupTau")) {
        if(parms.size() != 13) {
            cout << "HHGate::setupTau: Error: parms.size() != 13\n";
            return;
        }
        setupTables(parms, true);
        form_ = 0;
    }
}

void HHGate::tweakAlpha()
{
    ;  // Dummy
}

void HHGate::tweakTau()
{
    ;  // Dummy
}

/**
 * Sets up the tables one at a time. Based on GENESIS/src/olf/new_interp.c,
 * function setup_tab_values,
 * fine tuned by Erik De Schutter.
 */
void HHGate::setupTables(const vector<double>& parms, bool doTau)
{
    assert(parms.size() == 13);
    static const int XDIVS = 10;
    static const int XMIN = 11;
    static const int XMAX = 12;
    if(parms[XDIVS] < 1)
        return;
    unsigned int xdivs = static_cast<unsigned int>(parms[XDIVS]);

    A_.resize(xdivs + 1);
    B_.resize(xdivs + 1);
    xmin_ = parms[XMIN];
    xmax_ = parms[XMAX];
    assert(xmax_ > xmin_);
    invDx_ = xdivs / (xmax_ - xmin_);
    double dx = (xmax_ - xmin_) / xdivs;

    double x = xmin_;
    double prevAentry = 0.0;
    double prevBentry = 0.0;
    double temp;
    double temp2 = 0.0;
    unsigned int i;

    for(i = 0; i <= xdivs; i++) {
        if(fabs(parms[4]) < SINGULARITY) {
            temp = 0.0;
            A_[i] = temp;
        }
        else {
            temp2 = parms[2] + exp((x + parms[3]) / parms[4]);
            if(fabs(temp2) < SINGULARITY) {
                temp2 = parms[2] + exp((x + dx / 10.0 + parms[3]) / parms[4]);
                temp = (parms[0] + parms[1] * (x + dx / 10)) / temp2;

                temp2 = parms[2] + exp((x - dx / 10.0 + parms[3]) / parms[4]);
                temp += (parms[0] + parms[1] * (x - dx / 10)) / temp2;
                temp /= 2.0;
                // cout << "interpolated temp = " << temp << ", prev = " <<
                // prevAentry << endl;

                // temp = prevAentry;
                A_[i] = temp;
            }
            else {
                temp = (parms[0] + parms[1] * x) / temp2;
                A_[i] = temp;
            }
        }
        if(fabs(parms[9]) < SINGULARITY) {
            B_[i] = 0.0;
        }
        else {
            temp2 = parms[7] + exp((x + parms[8]) / parms[9]);
            if(fabs(temp2) < SINGULARITY) {
                temp2 = parms[7] + exp((x + dx / 10.0 + parms[8]) / parms[9]);
                temp = (parms[5] + parms[6] * (x + dx / 10)) / temp2;
                temp2 = parms[7] + exp((x - dx / 10.0 + parms[8]) / parms[9]);
                temp += (parms[5] + parms[6] * (x - dx / 10)) / temp2;
                temp /= 2.0;
                B_[i] = temp;
                // B_[i] = prevBentry;
            }
            else {
                B_[i] = (parms[5] + parms[6] * x) / temp2;
                // B_.table_[i] = ( parms[5] + parms[6] * x ) / temp2;
            }
        }
        // There are cleaner ways to do this, but this keeps
        // the relation to the GENESIS version clearer.
        // Note the additional SINGULARITY check, to fix a bug
        // in the earlier code.
        if(doTau == 0 && fabs(temp2) > SINGULARITY)
            B_[i] += temp;

        prevAentry = A_[i];
        prevBentry = B_[i];
        x += dx;
    }

    prevAentry = 0.0;
    prevBentry = 0.0;
    if(doTau) {
        for(i = 0; i <= xdivs; i++) {
            temp = A_[i];
            temp2 = B_[i];
            if(fabs(temp) < SINGULARITY) {
                A_[i] = prevAentry;
                B_[i] = prevBentry;
            }
            else {
                A_[i] = temp2 / temp;
                B_[i] = 1.0 / temp;
            }
            prevAentry = A_[i];
            prevBentry = B_[i];
        }
    }
    form_ = 0;
}

/**
 * Tweaks the A and B entries in the tables from the original
 * alpha/beta or inf/tau values. See code in
 * GENESIS/src/olf/new_interp.c, function tweak_tab_values
 */
void HHGate::tweakTables(bool doTau)
{
    unsigned int i;
    unsigned int size = A_.size();
    assert(size == B_.size());
    if(doTau) {
        for(i = 0; i < size; i++) {
            double temp = A_[i];
            double temp2 = B_[i];
            if(fabs(temp) < SINGULARITY) {
                if(temp < 0.0)
                    temp = -SINGULARITY;
                else
                    temp = SINGULARITY;
            }
            A_[i] = temp2 / temp;
            B_[i] = 1.0 / temp;
        }
    }
    else {
        for(i = 0; i < size; i++)
            B_[i] = A_[i] + B_[i];
    }
}

void HHGate::setupGate(const Eref& e, vector<double> parms)
{
    // The nine arguments are :
    // A B C D F size min max isbeta
    // If size == 0 then we check that the gate has already been allocated.
    // If isbeta is true then we also have to do the conversion to
    // HHGate form of alpha, alpha+beta, assuming that the alpha gate
    // has already been setup. This uses tweakTables.
    // We may need to resize the tables if they don't match here.
    if(!checkOriginal(e.id(), "setupGate"))
        return;

    if(parms.size() != 9) {
        cout << "HHGate::setupGate: Error: parms.size() != 9\n";
        return;
    }

    double A = parms[0];
    double B = parms[1];
    double C = parms[2];
    double D = parms[3];
    double F = parms[4];
    int size = static_cast<int>(parms[5]);
    double min = parms[6];
    double max = parms[7];
    bool isBeta = static_cast<bool>(parms[8]);

    vector<double>& ip = (isBeta) ? B_ : A_;

    if(size <= 0)  // Look up size, min, max from the interpol
    {
        size = ip.size() - 1;
        if(size <= 0) {
            cout << "Error: setupGate has zero size\n";
            return;
        }
    }
    else {
        ip.resize(size + 1);
    }

    double dx = (max - min) / static_cast<double>(size);
    double x = min + dx / 2.0;
    for(int i = 0; i <= size; i++) {
        if(fabs(F) < SINGULARITY) {
            ip[i] = 0.0;
        }
        else {
            double temp2 = C + exp((x + D) / F);
            if(fabs(temp2) < SINGULARITY)
                ip[i] = ip[i - 1];
            else
                ip[i] = (A + B * x) / temp2;
        }
    }

    if(isBeta) {
        assert(A_.size() > 0);
        // Here we ensure that the tables are the same size
        if(A_.size() != B_.size()) {
            if(A_.size() > B_.size()) {
                // Note that the tabFill expects to allocate the
                // terminating entry, so we put in size - 1.
                tabFill(B_, A_.size() - 1, xmin_, xmax_);
            }
            else {
                tabFill(A_, B_.size() - 1, xmin_, xmax_);
            }
        }
        // Then we do the tweaking to convert to HHChannel form.
        tweakTables(0);
    }
    form_ = 0;
}

///////////////////////////////////////////////////////////////////////
// Utility funcs
///////////////////////////////////////////////////////////////////////

/**
 * This utility function does interpolation and range resizing for
 * a table representing a lookup function.
 * newXdivs is one less than the size of the table; it is the number of
 * subdivisions that the table represents.
 */
void HHGate::tabFill(vector<double>& table, unsigned int newXdivs,
                     double newXmin, double newXmax)
{
    if(newXdivs < 3) {
        cout << "Error: tabFill: # divs must be >= 3. Not filling table.\n";
        return;
    }

    vector<double> old = table;
    double newDx = (newXmax - newXmin) / newXdivs;
    table.resize(newXdivs + 1);
    bool origLookupMode = lookupByInterpolation_;
    lookupByInterpolation_ = 1;

    for(unsigned int i = 0; i <= newXdivs; ++i) {
        table[i] = lookupTable(table, newXmin + i * newDx);
    }

    lookupByInterpolation_ = origLookupMode;
}

void HHGate::updateAlphaBeta()
{
}

void HHGate::updateTauMinf()
{
}

void HHGate::updateTables()
{
    if(alpha_.size() == 0 || beta_.size() == 0)
        return;
    vector<double> parms = alpha_;
    parms.insert(parms.end(), beta_.begin(), beta_.end());
    parms.push_back((double)A_.size());
    parms.push_back(xmin_);
    parms.push_back(xmax_);

    setupTables(parms, 0);
}
