
# import os
# import sys

# dir = os.path.dirname(__file__)
# path = os.path.join(dir, '../')
# sys.path.insert(0, path)

import textwrap
import excellib
from excellib import *
from excelutils import *
from math import *
from networkx.classes.digraph import DiGraph
from networkx.drawing.nx_pydot import write_dot
from networkx.drawing.nx_pylab import draw, draw_circular
from networkx.readwrite.gexf import write_gexf
from tokenizer import ExcelParser, f_token, shunting_yard
import cPickle
import logging
import networkx as nx
from itertools import chain
from Range import Range

from ..excel.utils import rows_from_range

class Spreadsheet(object):
    def __init__(self,G,cellmap):
        super(Spreadsheet,self).__init__()
        self.G = G
        self.cellmap = cellmap
        self.params = None

    @staticmethod
    def load_from_file(fname):
        f = open(fname,'rb')
        obj = cPickle.load(f)
        #obj = load(f)
        return obj
    
    def save_to_file(self,fname):
        f = open(fname,'wb')
        cPickle.dump(self, f, protocol=2)
        f.close()

    def export_to_dot(self,fname):
        write_dot(self.G,fname)
                    
    def export_to_gexf(self,fname):
        write_gexf(self.G,fname)
    
    def plot_graph(self):
        import matplotlib.pyplot as plt

        pos=nx.spring_layout(self.G,iterations=2000)
        #pos=nx.spectral_layout(G)
        #pos = nx.random_layout(G)
        nx.draw_networkx_nodes(self.G, pos)
        nx.draw_networkx_edges(self.G, pos, arrows=True)
        nx.draw_networkx_labels(self.G, pos)
        plt.show()
    
    def set_value(self,cell,val,is_addr=True):
        if is_addr:
            cell = self.cellmap[cell]

        if cell.value != val:
            # reset the node + its dependencies
            self.reset(cell)
            # set the value
            cell.value = val
        
    def reset(self, cell):
        if cell.value is None: return
        #print "resetting", cell.address()
        cell.value = None
        map(self.reset,self.G.successors_iter(cell))

    def print_value_tree(self,addr,indent):
        cell = self.cellmap[addr]
        print "%s %s = %s" % (" "*indent,addr,cell.value)
        for c in self.G.predecessors_iter(cell):
            self.print_value_tree(c.address(), indent+1)

    def recalculate(self):
        for c in self.cellmap.values():
            if isinstance(c,CellRange):
                self.evaluate_range(c,is_addr=False)
            else:
                self.evaluate(c,is_addr=False)
                
    def evaluate_range(self,rng,is_addr=True):
        if is_addr:
            rng = self.cellmap[rng]

        # its important that [] gets treated ad false here
        if rng.value:
            return rng.value

        cells,nrows,ncols = rng.celladdrs,rng.nrows,rng.ncols

        if nrows == 1 or ncols == 1:
            data = Range(cells, [ self.evaluate(c) for c in cells ])
        else:
            # Warning, n-dimensional ranges will not work with Range operations
            raise Exception('Multi dimensional Range => needs to be addressed')
            data = Range([ [self.evaluate(c) for c in cells[i]] for i in range(len(cells)) ] )
        
        rng.value = data
        
        return data

    def evaluate(self,cell,is_addr=True):

        if is_addr:
            try:
                # print '->', cell
                cell = self.cellmap[cell]
            except:
                # print 'Empty cell at '+ cell
                return 0

            
        # no formula, fixed value
        if not cell.formula or cell.value != None:
            #print "returning constant or cached value for ", cell.address()
            return cell.value
        
        # recalculate formula
        # the compiled expression calls this function
        def eval_cell(address):
            evaluation = self.evaluate(address)

            # if evaluation is a list, that's because the cell is part of a shared formula, so we need to extract the corresponding value from the list
            # if type(evaluation) == List:
            #     if cell.index:
            #         evaluation = evaluation[cell.index]
            #     else:
            #         evaluation = evaluation[0]

            return evaluation
        
        def eval_range(rng, rng2=None):
            if rng2 is None:
                return self.evaluate_range(rng)
            else:
                # print 'eval_range', rng
                if '!' in rng:
                    sheet = rng.split('!')[0]
                else:
                    sheet = None
                if '!' in rng2:
                    rng2 = rng2.split('!')[1]
                # for s in self.cellmap:
                #     print self.cellmap[s]
                # return eval_range('%s:%s' % (rng, rng2))
                return self.evaluate_range(CellRange('%s:%s' % (rng, rng2),sheet), False)
        
        try:
            #for s in self.cellmap:
            #    print self.cellmap[s]

            # print "Evalling: %s, %s" % (cell.address(),cell.python_expression)
            vv = eval(cell.compiled_expression)

            if vv is None:
                print "WARNING %s is None" % (cell.address())
            # elif isinstance(vv, (List, list)):
            #     print 'Output is list => converting', cell.index
            #     vv = vv[cell.index]
            cell.value = vv
        except Exception as e:
            if e.message.startswith("Problem evalling"):
                raise e
            else:
                # print 'PB L208', eval_range("Calculations!L196","Calculations!DG196")
                # print 'PB L208' eval_cell("Calculations!I132")
                print 'PB'
                # print else eval_range("Calculations!L132","Calculations!DG132")
                raise Exception("Problem evalling: %s for %s, %s" % (e,cell.address(),cell.python_expression)) 

        try:
            # if type(cell.value) == List:
            #     if cell.index:
            #         cell.value = cell.value[cell.index]
            #     else:
            #         cell.value = cell.value[0]
            return cell.value
        except:
            for f in missing_functions:
                print 'MISSING', f
            # return missing_functions

class ASTNode(object):
    """A generic node in the AST"""
    
    def __init__(self,token):
        super(ASTNode,self).__init__()
        self.token = token
    def __str__(self):
        return self.token.tvalue
    def __getattr__(self,name):
        return getattr(self.token,name)

    def children(self,ast):
        args = ast.predecessors(self)
        args = sorted(args,key=lambda x: ast.node[x]['pos'])
        #args.reverse()
        return args

    def parent(self,ast):
        args = ast.successors(self)
        return args[0] if args else None

    def emit(self,ast,context=None):
        """Emit code"""
        self.token.tvalue
    
class OperatorNode(ASTNode):
    def __init__(self, args, ref):
        super(OperatorNode,self).__init__(args)
        self.ref = ref
        
        # convert the operator to python equivalents
        self.opmap = {
                 "^":"**",
                 "=":"==",
                 "&":"+",
                 "":"+" #union
                 }

    def emit(self,ast,context=None):
        xop = self.tvalue
        
        # Get the arguments
        args = self.children(ast)
        
        op = self.opmap.get(xop,xop)
        
        # convert ":" operator to a range function
        if op == ":":
            return "eval_range(%s)" % ','.join([a.emit(ast,context=context) for a in args])

         
        if self.ttype == "operator-prefix":
            return "-" + args[0].emit(ast,context=context)

        if op == "+":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.add(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.add(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "-":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.substract(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.substract(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "*":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.multiply(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.multiply(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "/":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.divide(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.divide(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "=":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_equal(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_equal(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "<>":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_not_equal(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_not_equal(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == ">":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_strictly_superior(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_strictly_superior(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "<":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_strictly_inferior(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_strictly_inferior(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == ">=":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_superior_or_equal(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_superior_or_equal(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        if op == "<=":
            arg1 = args[0]
            arg2 = args[1]

            is_arg1_range = arg1.emit(ast,context=context)[:10] == 'eval_range'
            is_arg2_range = arg2.emit(ast,context=context)[:10] == 'eval_range'

            if is_arg1_range:
                return "Range.is_inferior_or_equal(%s)" % ','.join([str(arg1.emit(ast,context=context)), str(arg2.emit(ast,context=context)), "'"+self.ref+"'"])
            elif is_arg2_range:
                return "Range.is_inferior_or_equal(%s)" % ','.join([str(arg2.emit(ast,context=context)), str(arg1.emit(ast,context=context)), "'"+self.ref+"'"])

        parent = self.parent(ast)

        #TODO silly hack to work around the fact that None < 0 is True (happens on blank cells)
        if op == "<" or op == "<=":
            aa = args[0].emit(ast,context=context)
            ss = "(" + aa + " if " + aa + " is not None else float('inf'))" + op + args[1].emit(ast,context=context)
        elif op == ">" or op == ">=":
            aa = args[1].emit(ast,context=context)
            ss =  args[0].emit(ast,context=context) + op + "(" + aa + " if " + aa + " is not None else float('inf'))"
        else:
            ss = args[0].emit(ast,context=context) + op + args[1].emit(ast,context=context)
                    

        #avoid needless parentheses
        if parent and not isinstance(parent,FunctionNode):
            ss = "("+ ss + ")"          

        return ss

class OperandNode(ASTNode):
    def __init__(self,*args):
        super(OperandNode,self).__init__(*args)
    def emit(self,ast,context=None):
        t = self.tsubtype
        
        if t == "logical":
            return str(self.tvalue.lower() == "true")
        elif t == "text" or t == "error":
            #if the string contains quotes, escape them
            val = self.tvalue.replace('"','\\"')
            return '"' + val + '"'
        else:
            return str(self.tvalue)

class RangeNode(OperandNode):
    """Represents a spreadsheet cell or range, e.g., A5 or B3:C20"""
    def __init__(self,*args):
        super(RangeNode,self).__init__(*args)
    
    def get_cells(self):
        return resolve_range(self.tvalue)[0]
    
    def emit(self,ast,context=None):
        # resolve the range into cells
        rng = self.tvalue.replace('$','')
        sheet = context + "!" if context else ""

        is_a_range = is_range(rng)

        if is_a_range:
            sh,start,end = split_range(rng)
        else:
            sh,col,row = split_address(rng)

        if sh:
            str = '"' + rng + '"'
        else:
            str = '"' + sheet + rng + '"'


        to_eval = True
        # exception for formulas which use the address and not it content as ":" or "OFFSET"
        parent = self.parent(ast)
        # for OFFSET, it will also depends on the position in the formula (1st position required)
        if (parent is not None and
            (parent.tvalue == ':' or 
            (parent.tvalue == 'OFFSET' and 
             parent.children(ast)[0] == self))):
            to_eval = False
                        
        if to_eval == False:
            return str
        elif is_a_range:
            return 'eval_range(' + str + ')'
        else:
            return 'eval_cell(' + str + ')'
        
        return str
    
class FunctionNode(ASTNode):
    """AST node representing a function call"""
    def __init__(self,*args):
        super(FunctionNode,self).__init__(*args)
        self.numargs = 0

        # map  excel functions onto their python equivalents
        self.funmap = excellib.FUNCTION_MAP
        
    def emit(self,ast,context=None):
        fun = self.tvalue.lower()
        str = ''

        # Get the arguments
        args = self.children(ast)
        
        if fun == "atan2":
            # swap arguments
            str = "atan2(%s,%s)" % (args[1].emit(ast,context=context),args[0].emit(ast,context=context))
        elif fun == "pi":
            # constant, no parens
            str = "pi"
        elif fun == "if":
            # inline the if
            if len(args) == 2:
                str = "%s if %s else 0" %(args[1].emit(ast,context=context),args[0].emit(ast,context=context))
            elif len(args) == 3:
                str = "(%s if %s else %s)" % (args[1].emit(ast,context=context),args[0].emit(ast,context=context),args[2].emit(ast,context=context))
            else:
                raise Exception("if with %s arguments not supported" % len(args))

        elif fun == "array":
            str += '['
            if len(args) == 1:
                # only one row
                str += args[0].emit(ast,context=context)
            else:
                # multiple rows
                str += ",".join(['[' + n.emit(ast,context=context) + ']' for n in args])
                     
            str += ']'
        elif fun == "arrayrow":
            #simply create a list
            str += ",".join([n.emit(ast,context=context) for n in args])

        elif fun == "and":
            str = "all([" + ",".join([n.emit(ast,context=context) for n in args]) + "])"
        elif fun == "or":
            str = "any([" + ",".join([n.emit(ast,context=context) for n in args]) + "])"
        else:
            # map to the correct name
            f = self.funmap.get(fun,fun)
            str = f + "(" + ",".join([n.emit(ast,context=context) for n in args]) + ")"

        return str

def create_node(t, ref):
    """Simple factory function"""
    if t.ttype == "operand":
        if t.tsubtype == "range":
            return RangeNode(t)
        else:
            return OperandNode(t)
    elif t.ttype == "function":
        return FunctionNode(t)
    elif t.ttype.startswith("operator"):
        return OperatorNode(t, ref)
    else:
        return ASTNode(t)

class Operator:
    """Small wrapper class to manage operators during shunting yard"""
    def __init__(self,value,precedence,associativity):
        self.value = value
        self.precedence = precedence
        self.associativity = associativity

def shunting_yard(expression, named_range, ref = None):
    """
    Tokenize an excel formula expression into reverse polish notation
    
    Core algorithm taken from wikipedia with varargs extensions from
    http://www.kallisti.net.nz/blog/2008/02/extension-to-the-shunting-yard-algorithm-to-allow-variable-numbers-of-arguments-to-functions/
    """
    #remove leading =
    if expression.startswith('='):
        expression = expression[1:]

    #remove %
    expression = expression.replace("%", "")
        
    p = ExcelParser();
    p.parse(expression)

    # insert tokens for '(' and ')', to make things clearer below
    tokens = []
    for t in p.tokens.items:
        if t.ttype == "function" and t.tsubtype == "start":
            t.tsubtype = ""
            tokens.append(t)
            tokens.append(f_token('(','arglist','start'))
        elif t.ttype == "function" and t.tsubtype == "stop":
            tokens.append(f_token(')','arglist','stop'))
        elif t.ttype == "subexpression" and t.tsubtype == "start":
            t.tvalue = '('
            tokens.append(t)
        elif t.ttype == "subexpression" and t.tsubtype == "stop":
            t.tvalue = ')'
            tokens.append(t)
        else:
            tokens.append(t)

    # print "tokens: ", "|".join([x.tvalue for x in tokens])

    # print "==> ", "".join([t.tvalue for t in tokens]) 


    #http://office.microsoft.com/en-us/excel-help/calculation-operators-and-precedence-HP010078886.aspx
    operators = {}
    operators[':'] = Operator(':',8,'left')
    operators[''] = Operator(' ',8,'left')
    operators[','] = Operator(',',8,'left')
    operators['u-'] = Operator('u-',7,'left') #unary negation
    operators['%'] = Operator('%',6,'left')
    operators['^'] = Operator('^',5,'left')
    operators['*'] = Operator('*',4,'left')
    operators['/'] = Operator('/',4,'left')
    operators['+'] = Operator('+',3,'left')
    operators['-'] = Operator('-',3,'left')
    operators['&'] = Operator('&',2,'left')
    operators['='] = Operator('=',1,'left')
    operators['<'] = Operator('<',1,'left')
    operators['>'] = Operator('>',1,'left')
    operators['<='] = Operator('<=',1,'left')
    operators['>='] = Operator('>=',1,'left')
    operators['<>'] = Operator('<>',1,'left')
            
    output = collections.deque()
    stack = []
    were_values = []
    arg_count = []
    
    for t in tokens:
        if t.ttype == "operand":
            output.append(create_node(t, ref))
            if were_values:
                were_values.pop()
                were_values.append(True)
                
        elif t.ttype == "function":
            stack.append(t)
            arg_count.append(0)
            if were_values:
                were_values.pop()
                were_values.append(True)
            were_values.append(False)
            
        elif t.ttype == "argument":

            while stack and (stack[-1].tsubtype != "start"):
                output.append(create_node(stack.pop(), ref))   
            
            if were_values.pop(): arg_count[-1] += 1
            were_values.append(False)
            
            if not len(stack):
                raise Exception("Mismatched or misplaced parentheses")
        
        elif t.ttype.startswith('operator'):

            if t.ttype.endswith('-prefix') and t.tvalue =="-":
                o1 = operators['u-']
            else:
                o1 = operators[t.tvalue]

            while stack and stack[-1].ttype.startswith('operator'):
                
                if stack[-1].ttype.endswith('-prefix') and stack[-1].tvalue =="-":
                    o2 = operators['u-']
                else:
                    o2 = operators[stack[-1].tvalue]
                
                if ( (o1.associativity == "left" and o1.precedence <= o2.precedence)
                        or
                      (o1.associativity == "right" and o1.precedence < o2.precedence) ):
                    
                    output.append(create_node(stack.pop(), ref))
                else:
                    break
                
            stack.append(t)
        
        elif t.tsubtype == "start":
            stack.append(t)
            
        elif t.tsubtype == "stop":

            while stack and stack[-1].tsubtype != "start":
                output.append(create_node(stack.pop(), ref))
            
            if not stack:
                raise Exception("Mismatched or misplaced parentheses")
            
            stack.pop()

            if stack and stack[-1].ttype == "function":
                f = create_node(stack.pop(), ref)
                a = arg_count.pop()
                w = were_values.pop()
                if w: a += 1
                f.num_args = a
                #print f, "has ",a," args"
                output.append(f)

    while stack:
        if stack[-1].tsubtype == "start" or stack[-1].tsubtype == "stop":
            raise Exception("Mismatched or misplaced parentheses")
        
        output.append(create_node(stack.pop(), ref))

    #print "Stack is: ", "|".join(stack)
    #print "Output is: ", "|".join([x.tvalue for x in output])
    
    # convert to list
    result = [x for x in output]

    # replacing named_range
    final_result = []
    for x in result:
        if x.tvalue in named_range:
            final_result = final_result + named_range[x.tvalue]
        else:
            final_result.append(x)
    return final_result
   
def build_ast(expression):
    """build an AST from an Excel formula expression in reverse polish notation"""
    #use a directed graph to store the tree
    G = DiGraph()
    
    stack = []
    
    for n in expression:
        # Since the graph does not maintain the order of adding nodes/edges
        # add an extra attribute 'pos' so we can always sort to the correct order
        if isinstance(n,OperatorNode):
            if n.ttype == "operator-infix":
                arg2 = stack.pop()
                arg1 = stack.pop()
                # Hack to write the name of sheet in 2argument address
                if(n.tvalue == ':'):
                    if '!' in arg1.tvalue and '!' not in arg2.tvalue:
                        arg2.tvalue = arg1.tvalue.split('!')[0] + '!' + arg2.tvalue
                    
                G.add_node(arg1,{'pos':1})
                G.add_node(arg2,{'pos':2})
                G.add_edge(arg1, n)
                G.add_edge(arg2, n)
            else:
                arg1 = stack.pop()
                G.add_node(arg1,{'pos':1})
                G.add_edge(arg1, n)
                
        elif isinstance(n,FunctionNode):
            args = [stack.pop() for _ in range(n.num_args)]
            args.reverse()
            for i,a in enumerate(args):
                G.add_node(a,{'pos':i})
                G.add_edge(a,n)
            #for i in range(n.num_args):
            #    G.add_edge(stack.pop(),n)
        else:
            G.add_node(n,{'pos':0})

        stack.append(n)

    return G,stack.pop()



class ExcelCompiler(object):
    """Class responsible for taking cells and named_range and create a graph
       that can be serialized to disk, and executed independently of excel.
    """

    def __init__(self, named_range, cells):
        self.named_range = {name : shunting_yard(named_range[name], named_range) for name in named_range}
        self.cells = cells
        
        
    def cell2code(self, cell, sheet):
        """Generate python code for the given cell"""
        if cell.formula:
            e = shunting_yard(cell.formula or str(cell.value), self.named_range, cell.address())
            ast,root = build_ast(e)
            code = root.emit(ast, context=sheet)
        else:
            ast = None
            code = str('"' + cell.value + '"' if isinstance(cell.value,unicode) else cell.value)
        return code,ast

    def add_node_to_graph(self,G, n):
        G.add_node(n)
        G.node[n]['sheet'] = n.sheet
        
        if isinstance(n,Cell):
            G.node[n]['label'] = n.col + str(n.row)
        else:
            #strip the sheet
            G.node[n]['label'] = n.address()[n.address().find('!')+1:]
            
    def gen_graph(self):
        
        seeds = list(flatten(self.cells.values()))
        
        print "Seeds %s cells" % len(seeds)
        # only keep seeds with formulas or numbers
        seeds = [s for s in seeds if s.formula or isinstance(s.value,(int, float, str))]

        print "%s filtered seeds " % len(seeds)
        
        # cells to analyze: only formulas
        todo = [s for s in seeds if s.formula]

        print "%s cells on the todo list" % len(todo)

        # map of all cells
        cellmap = dict([(x.address(),x) for x in seeds])
        
        # directed graph
        G = nx.DiGraph()

        # match the info in cellmap
        for c in cellmap.itervalues(): self.add_node_to_graph(G, c)

        while todo:
            c1 = todo.pop()
            
            # print "============= Handling ", c1.address()
            cursheet = c1.sheet
            
            # parse the formula into code
            pystr, ast = self.cell2code(c1, cursheet)

            # set the code & compile it (will flag problems sooner rather than later)
            c1.python_expression = pystr
            c1.compile()    
            
            # get all the cells/ranges this formula refers to
            deps = [x.tvalue.replace('$','') for x in ast.nodes() if isinstance(x,RangeNode)]
            # remove dupes
            deps = uniqueify(deps)

            for dep in deps:
                # if the dependency is a multi-cell range, create a range object
                if is_range(dep):
                    # this will make sure we always have an absolute address
                    rng = CellRange(dep, sheet=cursheet)
                    
                    if rng.address() in cellmap:
                        # already dealt with this range
                        # add an edge from the range to the parent
                        G.add_edge(cellmap[rng.address()],cellmap[c1.address()])
                        continue
                    else:
                        # turn into cell objects
                        if "!" in dep:
                            sheet_name, ref = dep.split("!")
                        else:
                            sheet_name = cursheet
                            ref = dep
                        cells_refs = list(rows_from_range(ref))                       
                        cells = [self.cells[sheet_name +"!"+ ref] for ref in list(chain(*cells_refs)) if sheet_name +"!"+ ref in self.cells]

                        # get the values so we can set the range value
                        rng.value = [c.value for c in cells]
                        

                        # save the range
                        cellmap[rng.address()] = rng
                        # add an edge from the range to the parent
                        self.add_node_to_graph(G, rng)
                        G.add_edge(rng,cellmap[c1.address()])
                        # cells in the range should point to the range as their parent
                        target = rng
                else:
                    # not a range, create the cell object
                    if "!" in dep:
                        sheet_name, ref = dep.split("!")
                    else:
                        sheet_name = cursheet
                        ref = dep
                    try:
                        cells = [self.cells[sheet_name +"!"+ ref]]
                        target = cellmap[c1.address()]
                    except:
                        cells = []
                        target = []

                # process each cell                    
                for c2 in flatten(cells):
                    # if we havent treated this cell allready
                    if c2.address() not in cellmap:
                        if c2.formula:
                            # cell with a formula, needs to be added to the todo list
                            todo.append(c2)
                            #print "appended ", c2.address()
                        else:
                            # constant cell, no need for further processing, just remember to set the code
                            pystr,ast = self.cell2code(c2, cursheet)
                            c2.python_expression = pystr
                            c2.compile()     
                            #print "skipped ", c2.address()
                        
                        # save in the cellmap
                        cellmap[c2.address()] = c2
                        # add to the graph
                        self.add_node_to_graph(G, c2)
                        
                    # add an edge from the cell to the parent (range or cell)
                    if(target != []):
                        G.add_edge(cellmap[c2.address()],target)
            
        print "Graph construction done, %s nodes, %s edges, %s cellmap entries" % (len(G.nodes()),len(G.edges()),len(cellmap))

        sp = Spreadsheet(G,cellmap)
        
        return sp

