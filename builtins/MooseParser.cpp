/***
 *    Description:  Moose Parser class, wraps exprtk.
 *
 *        Created:  2018-08-25

 *         Author:  Dilawar Singh <dilawars@ncbs.res.in>
 *   Organization:  NCBS Bangalore
 */

#include <vector>
#include <cassert>
#include <regex>
#include <algorithm>

#include "../basecode/header.h"

#include "../randnum/randnum.h"

#include "../utility/testing_macros.hpp"
#include "../utility/print_function.hpp"
#include "../utility/strutil.h"

#include "../builtins/Variable.h"
#include "../builtins/Function.h"
#include "MooseParser.h"

using namespace std;

namespace moose
{

MooseParser::MooseParser(): expr_("0"), valid_(true)
{
    Parser::symbol_table_t symbolTable;
    symbolTable.add_constants();
    symbolTable.add_function("ln", MooseParser::Ln);
    symbolTable.add_function("rand", MooseParser::Rand); // between 0 and 1
    symbolTable.add_function("rnd", MooseParser::Rand);  // between 0 and 1
    symbolTable.add_function("srand", MooseParser::SRand);
    symbolTable.add_function("rand2", MooseParser::Rand2);
    symbolTable.add_function("srand2", MooseParser::SRand2);
    symbolTable.add_function("fmod", MooseParser::Fmod);
    expression_.register_symbol_table(symbolTable);
    SetExpr(expr_);
}

MooseParser::~MooseParser()
{
}

/*-----------------------------------------------------------------------------
 *  User defined function here.
 *-----------------------------------------------------------------------------*/
double MooseParser::Ln( double v )
{
    return std::log(v);
}

double MooseParser::Rand( )
{
    return moose::mtrand();
}

double MooseParser::SRand( double seed = -1 )
{
    if( seed >= 0 )
        moose::mtseed( (unsigned int) seed );
    return moose::mtrand();
}

double MooseParser::Rand2( double a, double b )
{
    return moose::mtrand( a, b );
}

double MooseParser::SRand2( double a, double b, double seed = -1 )
{
    if( seed >= 0 )
        moose::mtseed( (unsigned int) seed );
    return moose::mtrand( a, b );
}

double MooseParser::Fmod( double a, double b )
{
    return fmod(a, b);
}


/*-----------------------------------------------------------------------------
 *  Get/Set
 *-----------------------------------------------------------------------------*/
Parser::symbol_table_t& MooseParser::GetSymbolTable(const unsigned int nth)
{
    return expression_.get_symbol_table(nth);
}

const Parser::symbol_table_t& MooseParser::GetSymbolTable(const unsigned int nth) const
{
    return expression_.get_symbol_table(nth);
}

double MooseParser::GetVarValue(const string& name) const
{
    return GetSymbolTable().get_variable(name)->value();
}

void MooseParser::PrintSymbolTable(void) const
{
    stringstream ss;
    auto symbTable = GetSymbolTable();
    vector<pair<string, double>> vars;
    auto n = symbTable.get_variable_list(vars);
    ss << "More Information:\nTotal variables " << n << ".";
    for (auto i : vars)
        ss << "\t" << i.first << "=" << i.second << " " << symbTable.get_variable(i.first)->ref();
    cerr << ss.str() << endl;
}

void MooseParser::findAllVars( const string& expr, set<string>& vars, const string& pattern)
{
    const regex pat(pattern);
    smatch sm;
    string temp(expr);
    while(regex_search(temp, sm, pat))
    {
        vars.insert(sm.str());
        temp = sm.suffix();
    }
}

/*-----------------------------------------------------------------------------
 *  Other function.
 *-----------------------------------------------------------------------------*/
bool MooseParser::DefineVar( const string varName, double* const val)
{
    // Use in copy assignment.
    if( GetSymbolTable().is_variable(varName))
        GetSymbolTable().remove_variable(varName);
    return GetSymbolTable().add_variable(varName, *val);
}

void MooseParser::DefineConst( const string& constName, const double value )
{
    if (GetSymbolTable().is_constant_node(constName)) {
	cout << "Warning: Ignoring attempt to change existing constant "
	     << constName << endl;
    } else if(!GetSymbolTable().add_constant(constName, value)){
	cout << "Warning: Failed to set constant " << constName << " = " << value << endl;
    }
}

void MooseParser::DefineFun1( const string& funcName, double (&func)(double) )
{
    // Add a function. This function currently handles only one argument
    // function.
    num_user_defined_funcs_ += 1;
    GetSymbolTable().add_function( funcName, func );
}


/* --------------------------------------------------------------------------*/
/**
 * @Synopsis  EXPRTK does not have && and || but have 'and' and 'or' symbol.
 * Replace && with 'and' and '||' with 'or'.
 *
 * @Param user_expr
 *
 * @Returns   
 */
/* ----------------------------------------------------------------------------*/
string MooseParser::Reformat( const string user_expr )
{
    string expr( user_expr );

    // Replate || with 'or'
    moose::str_replace_all( expr, "||", " or " );
    // Replace && with 'and'
    moose::str_replace_all( expr, "&&", " and " );

    // Trickt business: Replace ! with not but do not change !=
    moose::str_replace_all( expr, "!=", "@@@" ); // placeholder
    moose::str_replace_all( expr, "!", " not " );
    moose::str_replace_all( expr, "@@@", "!=" ); // change back @@@ to !=

    return expr;
}


/* --------------------------------------------------------------------------*/
/**
 * @Synopsis  Find all x\d+ and y\d+ in the experssion.
 *
 * @Param expr
 * @Param vars
 */
/* ----------------------------------------------------------------------------*/
void MooseParser::findXsYs( const string& expr, set<string>& xs, set<string>& ys )
{
    findAllVars( expr, xs, "x\\d+");
    findAllVars( expr, ys, "y\\d+" );
}

/* --------------------------------------------------------------------------*/
/**
 * @Synopsis  Set expression on parser.
 *
 * @Param user_expr
 *
 * @Returns   
 */
/* ----------------------------------------------------------------------------*/
bool MooseParser::SetExpr( const string& user_expr)
{
    ASSERT_FALSE( user_expr.empty(), "Empty expression" );
    expr_ = Reformat(user_expr);
    return CompileExpr();
}

bool MooseParser::SetExprWithUnknown(const string& user_expr, Function* func)
{
    ASSERT_FALSE( user_expr.empty(), "Empty expression" );
    expr_ = Reformat(user_expr);
    return CompileExprWithUnknown(func);
}

/* --------------------------------------------------------------------------*/
/**
 * @Synopsis  Compile a given expression.
 *
 * @Returns Return true if successful, throws exception if compilation fails.
 * Exception includes a detailed diagnostic.
 */
/* ----------------------------------------------------------------------------*/
bool MooseParser::CompileExpr()
{
    // User should make sure that symbol table has been setup. Do not raise
    // exception here. User can set expression again.
    // GCC specific
    ASSERT_FALSE(expr_.empty(), __func__ << ": Empty expression not allowed here");

    Parser::parser_t  parser;

    // This option is very useful when setting expression which don't have
    // standard naming of variables. For example, A + B etc.
    bool res = parser.compile(expr_, expression_);
    if(! res)
    {
        stringstream ss;
        ss << "Failed to parse '" << expr_ << "' :" << endl;
        for (unsigned int i = 0; i < parser.error_count(); ++i)
        {
            Parser::error_t error = parser.get_error(i);
            ss << "Error[" << i << "] Position: " << error.token.position
               << " Type: [" << exprtk::parser_error::to_str(error.mode)
               << "] Msg: " << error.diagnostic << endl;

            // map is
            auto symbTable = GetSymbolTable();
            vector<pair<string, double>> vars;
            auto n = symbTable.get_variable_list(vars);
            ss << "More Information:\nTotal variables " << n << ".";
            for (auto i : vars)
                ss << "\t" << i.first << "=" << i.second << " " << symbTable.get_variable(i.first)->ref();
            ss << endl;
        }
        // Throw the error, this is handled in callee.
        throw moose::Parser::exception_type(ss.str());
    }
    return res;
}

bool MooseParser::CompileExprWithUnknown(Function* func)
{
    ASSERT_FALSE(expr_.empty(), __func__ << ": Empty expression not allowed here");

    // User should make sure that symbol table has been setup. 
    Parser::parser_t  parser;
    parser.enable_unknown_symbol_resolver();

    // This option is very useful when setting expression which don't have
    // standard naming of variables. For example, A + B etc. This call to parse
    // will collect all variables in a symbol table.
    bool res = parser.compile(expr_, expression_);

    // Get all symbols and create Variable() for them. Note that now the
    // previos symbol table and compiled expressions are invalid.
    auto symbTable = GetSymbolTable();
    vector<pair<string, double>> vars;
    symbTable.get_variable_list(vars);

    // note: Don't clear the symbol table. Constants will also get cleared
    // which we don't want. 
    // We want continuity in xi's to make sure the OLD api still works. For
    // example, if x5+x1 is the expression, we have to make sure that x0, x1,
    // ..., x5 are present in symbol table.
    for(auto& v: vars)
    {
        // We have already made sure, before calling this function that xi, yi
        // ci, and t are set up. Only XVAR_NAMED variables need to be added.
        if(func->getVarType(v.first) == XVAR_NAMED)
        {
            GetSymbolTable().remove_variable(v.first, true);
            func->callbackAddSymbol(v.first);
        }
    }

    // Compile again with updated symbol table.
    // parser.disable_unknown_symbol_resolver();
    res = parser.compile(expr_, expression_);
    if(! res)
    {
        stringstream ss;
        ss << "Failed to parse '" << expr_ << "' :" << endl;
        for (unsigned int i = 0; i < parser.error_count(); ++i)
        {
            Parser::error_t error = parser.get_error(i);
            ss << "Error[" << i << "] Position: " << error.token.position
               << " Type: [" << exprtk::parser_error::to_str(error.mode)
               << "] Msg: " << error.diagnostic << endl;

            // map is
            auto symbTable = GetSymbolTable();
            vector<pair<string, double>> vars;
            auto n = symbTable.get_variable_list(vars);
            ss << "More Information:\nTotal variables " << n << ".";
            for (auto i : vars)
                ss << "\t" << i.first << "=" << i.second << " " << symbTable.get_variable(i.first)->ref();
            ss << endl;
        }
        // Throw the error, this is handled in callee.
        throw moose::Parser::exception_type(ss.str());
    }
    return res;
}


double MooseParser::Derivative(const string& name, unsigned int nth) const
{
    if(nth > 3)
    {
        cout << "Error: " << nth << "th derivative is not supported." << endl;
        return 0.0;
    }
    if(nth == 3)
        return exprtk::third_derivative(expression_, name);
    if(nth == 2)
        return exprtk::second_derivative(expression_, name);
    return exprtk::derivative(expression_, name);
}

double MooseParser::Eval(bool check) const
{
    if(! valid_)
    {
        cout << "MooseParser::Eval: Warn: Invalid parser state." << endl;
        return 0.0;
    }

    if(expr_.empty())
    {
        cout << "MooseParser::Eval: Warn: Expr is empty " << endl;
        return 0.0;
    }

    // PrintSymbolTable();
    // Make sure that no symbol is unknown at this point. Else emit error. The
    // Function::reinit must take of it.
    return expression_.value();
}


double MooseParser::Diff( const double a, const double b ) const
{
    return a-b;
}

bool MooseParser::IsConst(const string& name) const
{
    
    return GetSymbolTable().is_constant_node(name);
}

double MooseParser::GetConst(const string& name ) const
{
    if(!IsConst(name)) {
    // if(!GetSymbolTable().type_store.is_constant(name)) {
        cout << "Warning: no constant defined with name " << name << endl;
        return 0.0;
    }
    return GetSymbolTable().get_variable(name)->value();
}

void MooseParser::ClearVariables( )
{
    GetSymbolTable().clear_variables();
}

void MooseParser::ClearAll( )
{
    ClearVariables();
}

void MooseParser::Reset( )
{
    expression_.release();
}

const string MooseParser::GetExpr( ) const
{
    return expr_;
}

void MooseParser::LinkVariables(vector<Variable*>& xs, vector<double*>& ys, double* t)
{
    for(unsigned int i = 0; i < xs.size(); i++)
        DefineVar('x'+to_string(i), xs[i]->ref());

    for (unsigned int i = 0; i < ys.size(); i++) 
        DefineVar('y'+to_string(i), ys[i]);

    DefineVar("t", t);
}

void MooseParser::LinkVariables(vector<shared_ptr<Variable>>& xs, vector<shared_ptr<double>>& ys, double* t)
{
    for(unsigned int i = 0; i < xs.size(); i++)
        DefineVar('x'+to_string(i), xs[i]->ref());

    for (unsigned int i = 0; i < ys.size(); i++) 
        DefineVar('y'+to_string(i), ys[i].get());

    DefineVar("t", t);
}



} // namespace moose.
