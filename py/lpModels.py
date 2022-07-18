from _mixedTools import *
from scipy import optimize
import lpCompiler
_stdLinProg = ('c', 'A_ub','b_ub','A_eq','b_eq','bounds')

def loopxs(x,l,loopName):
	return x.xs(l,level=loopName) if isinstance(x.index, pd.MultiIndex) else x[l]

def updateFromGrids(db, grids, loop, l):
	[db.addOrMerge(g.name, loopxs(g,l,loop.name), priority='second') for g in grids];

def readSolutionLoop(sol, loop, i, extract, db):
    return pd.concat(list(sol[:,i]),axis=1).set_axis(loop, axis=1).stack() if isinstance(db[extract[i]], pd.Series) else pd.Series(sol[:,i], index = loop)

# A few basic functions for the energy models:
def fuelCost(db):
	return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'),fill_value=0)

def mc(db):
	return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'])

def fuelConsumption(db,sumOver='id'):
	return pdSum((db['Generation'] * db['FuelMix']).dropna(), sumOver)

def emissionsFuel(db, sumOver = 'BFt'):
	return pdSum((db['FuelConsumption'] * db['EmissionIntensity']).dropna(), sumOver)

class modelShell:
	def __init__(self, db, blocks = None, **kwargs):
		self.db = db
		self.blocks = noneInit(blocks, lpCompiler.lpBlock(**kwargs))
		if hasattr(self, 'globalDomains'):
			self.blocks.globalDomains = self.globalDomains

	def solve(self, preSolve = None, initBlocks = None, postSolve = None, printSol = True):
		if hasattr(self, 'preSolve'):
			self.preSolve(**noneInit(preSolve,{}))
		self.initBlocks(**noneInit(initBlocks,{}))
		sol = optimize.linprog(**self.blocks())
		if printSol:
			print(f"Solution status {sol['status']}: {sol['message']}")
		self.postSolve(sol, **noneInit(initBlocks,{}))

	def unloadSolution(self,sol):
		fullVector = pd.Series(sol['x'], index = self.blocks.lp_solutionIndex)
		return {k: lpCompiler.vIndexVariable(fullVector,k,v) for k,v in self.blocks.alldomains.items()}

	def unloadToDb(self,sol):
		[self.db.__setitem__(k,v) for k,v in self.unloadSolution(sol).items()];

	def loopSolveExtract(self, loop, grids, extract, preSolve = None, initBlocks = None, postSolve = None, printSol = False):
		""" Update exogenous parameters in loop, solve, and extract selected variables """
		n = np.array([self.loopSolveExtract_l(loop, grids, extract, l, preSolve=preSolve, initBlocks=initBlocks, postSolve=postSolve, printSol=printSol) for l in loop],dtype=object)
		return {extract[i]: readSolutionLoop(n,loop,i,extract,self.db) for i in range(len(extract))}
		
	def loopSolveExtract_l(self, loop, grids, extract, l, preSolve=None, initBlocks=None, postSolve=None,printSol=False):
		updateFromGrids(self.db, grids, loop,l)
		self.solve(preSolve = preSolve, initBlocks = initBlocks, postSolve = postSolve, printSol = printSol)
		return [self.db[k] for k in extract]

class mBasic(modelShell):
	def __init__(self,db,blocks=None,**kwargs):
		super().__init__(db, blocks = blocks, **kwargs)

	def preSolve(self,recomputeMC = False,**kwargs):
		if ('mc' not in self.db.symbols) or recomputeMC:
			self.db['mc'] = mc(self.db)

	@property
	def globalDomains(self):
		return {'Generation': self.db['id']}

	def initBlocks(self,**kwargs):
		self.blocks['c'] = [{'variableName': 'Generation', 'parameter': self.db['mc']}]
		self.blocks['u'] = [{'variableName': 'Generation', 'parameter': self.db['GeneratingCapacity']}]
		self.blocks['eq']= [{'constrName': 'equilibrium', 'b': self.db['Load'], 'A': [{'variableName': 'Generation','parameter': 1}]}]

	def postSolve(self,solution,**kwargs):
		if solution['status'] == 0:
			self.unloadToDb(solution)
			self.db['SystemCosts'] = solution['fun']
			self.db['FuelConsumption'] = fuelConsumption(self.db)
			self.db['Emissions'] = emissionsFuel(self.db)

