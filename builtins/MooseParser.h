/***
 *    Description:  Parser class. Similar API as muParser.
 *
 *         Author:  Dilawar Singh <dilawars@ncbs.res.in>
 *   Organization:  NCBS Bangalore
 *
 *        License:  See the LICENSE.md file.
 */

#ifndef PARSER_H
#define PARSER_H

#include <string>
#include <regex>
#include <memory>
#include <exception>
#include <map>
#include <iostream>

#define exprtk_enabled_debugging 0
#define exprtk_disable_comments 1
#include "../external/exprtk/exprtk.hpp"

using namespace std;

class Variable;
class Function;

namespace moose
{
namespace Parser
{

// ExprTk types.
typedef exprtk::symbol_table<double> symbol_table_t;
typedef exprtk::expression<double>     expression_t;
typedef exprtk::parser<double>             parser_t;
typedef exprtk::parser_error::type error_t;

struct ParserException : public std::exception
{
    ParserException( const string msg ) : msg_(msg) { ; }

    string GetMsg()
    {
        return msg_;
    }

    string msg_;
};

typedef ParserException exception_type;
typedef map<string, double> varmap_type;
} // namespace Parser

class MooseParser
{
public:
    MooseParser();
    ~MooseParser();

    void PrintSymbolTable() const;

    /*-----------------------------------------------------------------------------
     *  Set/Get
     *-----------------------------------------------------------------------------*/
    Parser::symbol_table_t& GetSymbolTable(const unsigned int nth=0);
    const Parser::symbol_table_t& GetSymbolTable(const unsigned int nth=0) const;

    /*-----------------------------------------------------------------------------
     *  User interface.
     *-----------------------------------------------------------------------------*/
    bool DefineVar( const string varName, double* const v );

    void DefineConst( const string& cname, const double val );

    void DefineFun1( const string& funcName, double (&func)(double) );

    bool SetExpr( const string& expr);
    bool SetExprWithUnknown( const string& expr, Function* func);

    bool CompileExpr();
    bool CompileExprWithUnknown(Function* func);

    // Reformat the expression to meet TkExpr.
    string Reformat( const string user_expr );

    static void findAllVars( const string& expr, set<string>& vars, const string& start );
    static void findXsYs(const string& expr, set<string>& xs, set<string>& ys);

    void LinkVariables(vector<Variable*>& xs_, vector<double*>& ys_, double* t);
    void LinkVariables(vector<shared_ptr<Variable>>& xs_, vector<shared_ptr<double>>& ys_, double* t);

    double Eval(bool check=false) const;

    double Derivative(const string& name, unsigned int nth=1) const;

    double Diff( const double a, const double b) const;

    bool IsConst(const string& name) const;
    double GetConst(const string& name) const;
    double GetVarValue(const string& name) const;


    void ClearVariables( );
    void ClearAll( );
    void Reset( );

    const string GetExpr( ) const;

    /*-----------------------------------------------------------------------------
     *  User defined function of parser.
     *-----------------------------------------------------------------------------*/
    static double Ln(double v);
    static double Rand( );
    static double SRand( double seed );
    static double Rand2( double a, double b );
    static double SRand2( double a, double b, double seed );
    static double Fmod( double a, double b );

private:

    /* data */
    string expr_;

    Parser::expression_t expression_;     /* expression type */

    unsigned int num_user_defined_funcs_ = 0;

    bool valid_{false};

};

} // namespace moose.

#endif /* end of include guard: PARSER_H */
