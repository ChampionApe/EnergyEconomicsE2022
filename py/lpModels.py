from _mixedTools import *
from databaseAux import appIndexWithCopySeries
from scipy import optimize
import lpCompiler
_stdLinProg = ('c', 'A_ub', 'b_ub', 'A_eq', 'b_eq', 'bounds')

def loopxs(x, l, loopName):
    return x.xs(l, level=loopName) if isinstance(x.index, pd.MultiIndex) else x[l]

def updateFromGrids(db, grids, loop, l):
    [db.addOrMerge(g.name, loopxs(g, l, loop.name), priority='second')
     for g in grids]

def readSolutionLoop(sol, loop, i, extract, db):
	return pd.concat(sol[i:len(loop)*len(extract):len(extract)], axis=1).set_axis(loop, axis=1).stack() if isinstance(db[extract[i]], pd.Series) else pd.Series(sol[i:len(loop)*len(extract):len(extract)], index=loop)

class modelShell:
    def __init__(self, db, blocks=None, method = 'highs', scalarDualAtUpper = True, computeDual = True, **kwargs):
        self.db = db
        self.method = method
        self.scalarDualAtUpper = True
        self.computeDual = computeDual
        self.blocks = noneInit(blocks, lpCompiler.lpBlock(**kwargs))
        if hasattr(self, 'globalDomains'):
            self.blocks.globalDomains = self.globalDomains

    def solve(self, preSolve=None, initBlocks=None, postSolve=None, printSol=True, solkwargs = None, solOptions = None):
        if hasattr(self, 'preSolve'):
            self.preSolve(**noneInit(preSolve, {}))
        self.initBlocks(**noneInit(initBlocks, {}))
        sol = optimize.linprog(method = self.method, **self.blocks(**noneInit(solkwargs,{})), **noneInit(solOptions, {}))
        if printSol:
            print(f"Solution status {sol['status']}: {sol['message']}")
        self.postSolve(sol, **noneInit(postSolve, {}))

    def adjustInitBlocks(self,**kwargs):
        [self.addBlock_i(k,v) for k,v in kwargs.items()];

    def addBlock_i(self,k,v):
        if self.blocks[k] is None:
            self.blocks.__setitem__(k,v)
        else:
            self.blocks[k] += v

    def unloadSolution(self, sol):
        fullVector = pd.Series(sol['x'], index=self.blocks.lp_solutionIndex)
        return {k: lpCompiler.vIndexVariable(fullVector, k, v) for k, v in self.blocks.alldomains.items()}

    def unloadDualSolution(self, sol):
    	fullVector = self.blocks.dual_solution(sol, scalarDual = self.scalarDualAtUpper)
    	return {**self.unloadShadowValuesConstraints(fullVector), **self.unloadShadowValuesBounds(fullVector)}

    def unloadShadowValuesBounds(self, fullVector):
    	return {'λ_'+k: lpCompiler.vIndexSymbol_dual(fullVector, k, v) for k, v in self.blocks.alldomains.items()}

    def unloadShadowValuesConstraints(self, fullVector):
    	return {'λ_'+k: lpCompiler.vIndexSymbol_dual(fullVector, k, v) for k,v in self.blocks.allconstrdomains.items()}

    def unloadToDb(self, sol):
        [self.db.__setitem__(k, v) for k, v in self.unloadSolution(sol).items()]
        if self.computeDual:
        	[self.db.__setitem__(k,v) for k,v in self.unloadDualSolution(sol).items()];

    def loopSolveExtract(self, loop, grids, extract, preSolve=None, initBlocks=None, postSolve=None, printSol=False):
        """ Update exogenous parameters in loop, solve, and extract selected variables """
        n = list(itertools.chain.from_iterable((self.loopSolveExtract_l(loop, grids, extract, l, preSolve = preSolve, initBlocks = initBlocks, postSolve = postSolve, printSol = printSol) for l in loop)))
        return {extract[i]: readSolutionLoop(n, loop, i, extract, self.db) for i in range(len(extract))}

    def loopSolveExtract_l(self, loop, grids, extract, l, preSolve=None, initBlocks=None, postSolve=None, printSol=False):
        updateFromGrids(self.db, grids, loop, l)
        self.solve(preSolve=preSolve, initBlocks=initBlocks,
                   postSolve=postSolve, printSol=printSol)
        return [self.db[k] for k in extract]

    def decomposeObjective(self):
        return {v: sum((self.db[v] * self.blocks.get(('c',v), attr='parameters')).dropna()) for v in self.blocks.allvars}