from _mixedTools import *
from scipy import optimize
_stdLinProg = ('c', 'A_ub','b_ub','A_eq','b_eq','bounds')

def tryOptions(options, k):
	try:
		return options[k]
	except KeyError:
		return {}

def fuelCost(db):
	return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'),fill_value=0)

def MC(db):
	return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'])

def FuelConsumption(db,sumOver='id'):
	return pdSum((db['Generation'] * db['FuelMix']).dropna(), sumOver)

def EmissionsFuel(db, sumOver = 'BFt'):
	return pdSum((db['FuelConsumption'] * db['EmissionIntensity']).dropna(), sumOver)

class modelShell:
	def __init__(self, db, options = None, **kwargs):
		self.db = db
		self.options = noneInit(options, {})

	def solve(self,**kwargs):
		if hasattr(self, 'preSolve'):
			self.preSolve(**kwargs)
		sol = optimize.linprog(**self.compileLinprogOptions,**kwargs)
		self.postSolve(sol)

	@property
	def compileLinprogOptions(self):
		return {k: getattr(self,k)(**tryOptions(self.options,k)) for k in _stdLinProg if hasattr(self,k)}

	def loopSolveAndExtract(self, loop, symbols, extract, **kwargs):
		""" Update exogenous parameters in loop, solve, and extract selected variables """
		

class mBasic(modelShell):
	def __init__(self,db,options=None,**kwargs):
		super().__init__(db, options = options, **kwargs)

	def preSolve(self,recomputeMC = True,**kwargs):
		if ('mc' not in self.db.symbols) or recomputeMC:
			self.db['mc'] = MC(self.db)

	def c(self,**kwargs):
		return self.db['mc'].values

	def A_eq(self,**kwargs):
		return np.ones((1, len(self.db['mc'])))

	def b_eq(self,**kwargs):
		return self.db['Load']

	def bounds(self,**kwargs):
		return np.stack((np.zeros(len(self.db['GeneratingCapacity'])), self.db['GeneratingCapacity'].values),axis=1)

	def postSolve(self,solution):
		print(f"Solution status {solution['status']}: {solution['message']}")
		if solution['status'] == 0:
			self.db['Generation'] = pd.Series(solution['x'], index = self.db['mc'].index, name = 'Generation')
			self.db['SystemCosts'] = solution['fun']
			self.db['FuelConsumption'] = FuelConsumption(self.db)
			self.db['Emissions'] = EmissionsFuel(self.db)

