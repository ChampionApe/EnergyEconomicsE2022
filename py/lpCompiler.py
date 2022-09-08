import database
from _mixedTools import *
from subsetPandas import rc_pd
from functools import reduce
_stdLinProg = ('c', 'A_ub','b_ub','A_eq','b_eq','bounds')

def emptyArrayIfEmpty(x):
	return [np.hstack(x)] if x else [np.array([])]

def noneInitList(x,FallBackVal):
	return FallBackVal if x is None else [x]

def stdNames(k):
	if isinstance(k,str):
		return [f"_{k}symbol", f"_{k}index"]
	else:
		return [n for l in [stdNames(i) for i in k] for n in l]

def getDomains(x):
	return [] if database.getIndex(x) is None else database.getIndex(x).names

def sortAll(v, order=None):
	return reorderStd(v, order=order).sort_index() if isinstance(v, (pd.Series, pd.DataFrame)) else v

def reorderStd(v, order=None):
	return v.reorder_levels(noneInit(order, sorted(database.getIndex(v).names))) if isinstance(database.getIndex(v), pd.MultiIndex) else v

# 1: Broadcasting:
def broadcast(x,y,fill_value=0):
	""" y is a index or None, x is a scalar or series."""
	if getDomains(y):
		if not getDomains(x):
			return pd.Series(x, index = y)
		elif set(getDomains(x)).intersection(set(getDomains(y))):
			# return pd.merge(x.to_frame('x'), pd.Series(index = y, dtype='object',name='x'), left_index = True, right_index = True, how = 'left')['x_x']
			if set(getDomains(x))-set(getDomains(y)):
				return x.add(pd.Series(0, index = y), fill_value=fill_value)
			else:
				return pd.Series(0, index=y).add(x,fill_value=fill_value)
		else:
			return pd.Series(0, index = cartesianProductIndex([database.getIndex(x),y])).add(x,fill_value=fill_value)
	else:
		return x
def adHocMerge(x,y):
	return pd.merge(x.rename('x'), pd.Series(0, index = y).rename('y'), left_index = True, right_index = True).dropna().sum(axis=1)

def bcAdd(x,y,fill_value=0):
	""" Use broadcasting to robustly add two variables, including if the two are scalars. """
	b = broadcast(x,database.getIndex(y),fill_value=fill_value)
	return b.add(y, fill_value=fill_value) if isinstance(b,pd.Series) else x+y

def asSeriesIfIndex(x,val = 0):
	return pd.Series(val, index = x) if isinstance(x, pd.Index) else x

# 2: GLOBAL INDEX METHODS
def setattrReturn(symbol, k,v):
	symbol.__setattr__(k,v)
	return symbol

def fIndex_Series(variableName, index, btype ='v'):
	return setattrReturn(pd.MultiIndex.from_product([[variableName],reorderStd(index).values], names=stdNames(btype)), '_n', sorted(index.names))

def fIndex(variableName, index, btype = 'v'):
	return setattrReturn(pd.MultiIndex.from_tuples([(variableName,None)], names = stdNames(btype)), '_n', []) if index is None else fIndex_Series(variableName,index, btype = btype)

def fIndexVariable(variableName, v, btype = 'v'):
	return pd.Series(database.getValues(v), index = fIndex(variableName, database.getIndex(v), btype = btype))

def vIndex_Series(f,names):
	return f.index.set_names(names) if len(names)==1 else pd.MultiIndex.from_tuples(f.index.values,names=names)

def vIndexVariable(f, variable, names):
	return pd.Series(f.xs(variable).values, index = vIndex_Series(f.xs(variable),names)) if names else f.xs(variable)[0]

def vIndexSymbol_dual(f, symbol, names):
	keep = f.xs(symbol)
	return pd.Series(keep.values, index = pd.MultiIndex.from_frame(vIndex_Series(keep.droplevel('_type'), names).to_frame(index=False).assign(_type=keep.index.get_level_values('_type')))) if names else keep.droplevel('_sindex')

# 3: Methods on iterator of symbols
def sumIte(ite,fill_value=0):
	""" Sum using broadcasting methods on iterative object """
	return reduce(lambda x,y: bcAdd(x,y,fill_value=fill_value), ite)

def maxIte(ite):
	""" Returns max of symbols in ite; ignores NaN unless all columns use it. """
	return pd.concat(ite, axis=1).max(axis=1) if isinstance(ite[0], pd.Series) else max([noneInit(x,np.nan) for x in ite])

def minIte(ite):
	return pd.concat(ite, axis=1).min(axis=1) if isinstance(ite[0], pd.Series) else min([noneInit(x,np.nan) for x in ite])

def stackValues(ite):
	return np.hstack([f.values for f in ite])

def stackIndex(ite,names):
	return pd.MultiIndex.from_tuples(np.hstack([f.index.values for f in ite]), names = names)

def stackSeries(ite, names):
	return pd.Series(stackValues(ite), index = stackIndex(ite,names))

def stackIte(varsDict,fill_value=0, btype = 'v', addFullIndex= True):
	""" Returns stacked variable with global index"""
	fvars = [fIndexVariable(k, varsDict[k]) for k in varsDict] if addFullIndex else varsDict.values()
	return stackSeries(fvars, names = stdNames(btype))

class lpBlock:
	def __init__(self, globalDomains=None, **kwargs):
		self.globalDomains=noneInit(globalDomains, {})
		self.blocks = {k: ifinInit(k,kwargs,None) for k in ('c','eq','ub','u','l')}
		self.parameters = {}
		self.compiled = {}
		self.broadcasted = {}

	def get(self, item, attr='parameters'):
		return getattr(self,attr)[item]

	def set(self, item, value, attr='parameters'):
		getattr(self,attr)[item] = value

	def getIte(self, k, par = None, var = None, constr = None, attr = 'parameters'):
		""" return generator of types k (block type), var (variable type), constr (constraint type). """
		if k in ('c','l','u'):
			return (v for kk,v in getattr(self,attr).items() if (kk[0] == k) and (kk[1] in noneInitList(var, self.getVariables(attr=attr))))
		elif k in ('eq','ub'):
			if par == 'b':
				return (v for kk,v in getattr(self,attr).items() if (kk[0:2] == (k,par)) and (kk[-1] in noneInitList(constr, self.getConstraints(k))))
			elif par == 'A':
				return (v for kk,v in getattr(self,attr).items() if (kk[0:2] == (k,par)) and (kk[3] in noneInitList(var, self.getVariables(attr=attr))) and (kk[2] in noneInitList(constr, self.getConstraints(k))))
		elif is_iterable(k) and par is None:
			return (v for kk,v in getattr(self,attr).items() if (kk[0] in k) and (kk[1] in noneInitList(var, self.getVariables(attr=attr))))
		elif is_iterable(k) and par == 'b':
			return (v for kk,v in getattr(self,attr).items() if (kk[0] in k and kk[1] == par) and (kk[-1] in noneInitList(constr, self.getConstraints(k))))
		elif is_iterable(k) and par == 'A':
			return (v for kk,v in getattr(self,attr).items() if (kk[0] in k and kk[1] == par) and (kk[3] in noneInitList(var,self.getVariables(attr=attr))) and (kk[2] in noneInitList(constr, self.getConstraints(k))))
		else:
			raise KeyError(f"Invalid combination of k = {k} and par = {par}.")

	def __getitem__(self,item):
		return self.blocks[item]

	def __setitem__(self, item, value):
		self.blocks[item] = value

	def readConstraintsFromBlocks_A(self,t):
		return set([k['constrName'] for k in self[t] if 'A' in k])
	def getConstraints(self, t):
		return set([k[-1] for k in  self.parameters if k[0:2] == (t,'b')]) if not is_iterable(t) else set([k[-1] for k in self.parameters if (k[0] in t) and (k[1] == 'b')])
	def getVariables(self, attr = 'parameters'):
		return set([k[-1] for k in  getattr(self,attr) if (k[0] == 'c') or (k[0] in ('eq','ub') and k[1] == 'A')])
	def getVariables_t(self, t, attr = 'parameters'):
		return set([k[-1] for k in getattr(self,attr) if (k[0] == t)])
	def getVariables_i(self, t, constr, attr = 'parameters'):
		return set([k[-1] for k in  getattr(self,attr) if (k[0:2] == (t,'A')) and (k[2] == constr)])

	# 0: Methods:
	def readParameters(self):
		if self['c'] is not None:
			[self.set(('c',k), v) for k,v in self.coefficient(self['c']).items()];
		if self['eq'] is not None:
			[self.set(('eq','b',k), v) for k,v in self.coefficient([i for i in self['eq'] if 'b' in i],name='constrName',pname='b').items()];
			[self.set(('eq','A',k,kk), v) for k in self.readConstraintsFromBlocks_A('eq') for kk,v in self.readAconstr_i('eq',k).items()];
		if self['ub'] is not None:
			[self.set(('ub','b',k), v) for k,v in self.coefficient([i for i in self['ub'] if 'b' in i],name='constrName',pname='b').items()];
			[self.set(('ub','A',k,kk), v) for k in self.readConstraintsFromBlocks_A('ub') for kk,v in self.readAconstr_i('ub',k).items()];
		if self['u'] is not None:
			[self.set(('u',k), v) for k,v in self.coefficientMin(self['u']).items()];
		if self['l'] is not None:
			[self.set(('l',k), v) for k,v in self.coefficientMax(self['l']).items()];

	def readAconstr_i(self, t, constr):
		blocks = [self.coefficient(i['A']) for i in self[t] if ('A' in i) and (i['constrName'] == constr)];
		return {kk: sumIte((v for b in blocks for k,v in b.items() if k == kk)) for kk in set.union(*[set(b) for b in blocks])}

	# 1: Simple Coefficient Block:
	def coefficient(self, blocks, name = 'variableName', pname = 'parameter'):
		return {k: sumIte((self.c_readdict(d, name = name, pname = pname) for d in blocks if d[name] == k)) for k in set([x[name] for x in blocks])}

	def coefficientMax(self, blocks, name = 'variableName', pname = 'parameter', defaultValue = 0):
		return {k: maxIte([self.c_readdict(d, name = name, pname = pname, defaultValue=defaultValue) for d in blocks if d[name] == k]) for k in set([x[name] for x in blocks])}

	def coefficientMin(self, blocks, name = 'variableName', pname = 'parameter', defaultValue = None):
		return {k: minIte([self.c_readdict(d, name = name, pname = pname, defaultValue=defaultValue) for d in blocks if d[name] == k]) for k in set([x[name] for x in blocks])}

	def c_readdict(self, d, name = 'variableName', pname = 'parameter', defaultValue=0):
		return rc_pd(self.checkGD(d[name], d[pname],defaultValue=defaultValue), c = None if 'conditions' not in d else d['conditions'])

	def checkGD(self, key, value, defaultValue = 0):
		if key in self.globalDomains and not isinstance(value, pd.Series):
			return pd.Series(noneInit(value, defaultValue), index = self.globalDomains[key])
		else:
			return noneInit(value, defaultValue)

	# 2: Map variables to full index:
	def compileParameters(self):
		[self.set((t, v), fIndexVariable(v, self.get((t,v))),attr='compiled') for t in ('c','l','u') for v in self.getVariables_t(t)];
		[self.set((t,'b',constr), fIndexVariable(constr, self.get((t,'b',constr)),btype=t).sort_index(), attr='compiled') for t in ('eq','ub') for constr in self.getConstraints(t)];
		[self.set(('eq','A',constr,v),self.fIndexVariable_Ai('eq',v,constr,self.get(('eq','A',constr,v)), self.get(('eq','b',constr))),attr='compiled') for constr in self.getConstraints('eq') for v in self.getVariables_i('eq',constr)];
		[self.set(('ub','A',constr,v),self.fIndexVariable_Ai('ub',v,constr,self.get(('ub','A',constr,v)), self.get(('ub','b',constr))),attr='compiled') for constr in self.getConstraints('ub') for v in self.getVariables_i('ub',constr)];

	def fIndexVariable_Ai(self, t, v, constr, Ai, b):
		overlap = set(getDomains(Ai)).intersection(getDomains(b))
		onlyA = set(getDomains(Ai))-overlap
		if not overlap:
			full = broadcast(fIndexVariable(v,Ai), fIndex(constr, database.getIndex(b), btype=t))
		else:
			full = broadcast(Ai, database.getIndex(b))
			if not onlyA:
				full.index = cartesianProductIndex([fIndex(v, None), fIndex(constr, full.index, btype=t)])
			else:
				f1, f2 = fIndex(v, full.index.droplevel(list(set(getDomains(Ai))-onlyA)) ), fIndex(constr, full.index.droplevel(list(onlyA)), btype=t)
				full.index = pd.MultiIndex.from_arrays(np.concatenate([f1.to_frame(index=False).values, f2.to_frame(index=False)], axis=1).T, names = stdNames('v')+stdNames(t))
		full.index._nA, full.index._nb = sorted(onlyA), sorted(getDomains(b))
		return full

	# 3: Infer global index from compiled parameters
	def inferGlobalDomains(self):
		self.gIndex = {k: fIndex(k, self.domains_var(k)) for k in self.getVariables(attr='compiled')}
		return self.gIndex

	def readIndexNames(self, k):
		try:
			return next(self.getIte(('c','l','u'),var=k,attr='compiled')).index._n
		except StopIteration:
			return next(self.getIte(('eq','ub'),par='A',var=k,attr='compiled')).index._nA

	def readConstrIndexNames(self, k):
		return next(self.getIte(('eq','ub'), par='A', constr=k ,attr='compiled')).index._nb
		
	def domains_var(self, k):
		index = reduce(pd.Index.union, [self.get((t,k),attr='compiled').index.levels[1] for t in ('c','u','l') if (t,k) in self.compiled]+[s.index.levels[1] for s in self.getIte('eq',par='A',var=k,attr='compiled')]+[s.index.levels[1] for s in self.getIte('ub',par='A',var=k,attr='compiled')])
		return None if index.empty else index

	# 4: Broadcast and sort variables to full domain:
	def settingsFromCompiled(self):
		self.allvars = sorted(self.getVariables(attr='compiled'))
		self.allconstr = {t: sorted(self.getConstraints(t)) for t in ('eq','ub')}
		self.alldomains = {k: self.readIndexNames(k) for k in self.allvars}
		self.allconstrdomains = {k: self.readConstrIndexNames(k) for k in self.allconstr['eq']+self.allconstr['ub']}

	def broadcastAndSort(self):
		[self.set((t,k), self.broadcastAndSort_i(t,k),attr='broadcasted') for t in ('c','l') for k in self.allvars];
		[self.set(('u',k), self.broadcastAndSort_i('u',k,val=None), attr='broadcasted') for k in self.allvars];
		[self.set((t,'A',constr,k), self.broadcastAndSort_Ai(t,constr,k,self.get((t,'b',constr),attr='compiled').index), attr='broadcasted') for t in ('eq','ub') for constr in self.allconstr[t] for k in self.allvars];

	def broadcastAndSort_i(self, t, k, val=0):
		return broadcast(self.get((t,k),attr='compiled') if k in self.getVariables_t(t,attr='compiled') else val, self.gIndex[k], fill_value = val).sort_index()

	def broadcastAndSort_Ai(self,t,constr,k,bindex):
		if k in self.getVariables_i(t,constr,attr='compiled'):
			return sparseDF(self.gIndex[k], bindex.get_level_values(f'_{t}index')).add(self.get((t,'A',constr,k),attr='compiled').droplevel(f'_{t}symbol').unstack(level=-1).fillna(0), fill_value=0)
		else:
			return sparseDF(self.gIndex[k], bindex.get_level_values(f'_{t}index'))

	# def broadcastAndSort_Ai(self,t,constr,k,bindex):
	# 	if k in self.getVariables_i(t,constr,attr='compiled'):
	# 		return pd.DataFrame(0, index = self.gIndex[k], columns = bindex.get_level_values(f'_{t}index')).add(self.get((t,'A',constr,k),attr='compiled').droplevel(f'_{t}symbol').unstack(level=-1).fillna(0), fill_value=0)
	# 	else:
	# 		return pd.DataFrame(0, index = self.gIndex[k], columns = bindex.get_level_values(f'_{t}index'))

	# 5: Methods to get the stacked numpy arrays:
	def __call__(self, execute=None):
		[getattr(self, k)() for k in noneInit(execute, ['readParameters','compileParameters','settingsFromCompiled','inferGlobalDomains','broadcastAndSort'])];
		return self.lp_args

	@property
	def lp_args(self):
		return {k: getattr(self, 'lp_'+k) for k in _stdLinProg}
	@property
	def lp_solutionIndex(self):
		return stackIndex([self.get(('c',k),attr='broadcasted') for k in self.allvars], names = stdNames('v'))
	@property
	def lp_c(self):
		return stackValues([self.get(('c',k),attr='broadcasted') for k in self.allvars])
	@property
	def lp_l(self): 
		return stackValues([self.get(('l',k),attr='broadcasted') for k in self.allvars])
	@property
	def lp_u(self): 
		return stackValues([self.get(('u',k),attr='broadcasted') for k in self.allvars])
	@property
	def lp_bounds(self):
		return np.vstack([self.lp_l, self.lp_u]).T
	@property
	def lp_A_eq(self):
		return np.hstack([np.vstack([self.get(('eq','A',constr,k),attr='broadcasted').values for k in self.allvars]) for constr in self.allconstr['eq']]).T if self.allconstr['eq'] else None
	@property
	def lp_A_ub(self):
		return np.hstack([np.vstack([self.get(('ub','A',constr,k),attr='broadcasted').values for k in self.allvars]) for constr in self.allconstr['ub']]).T if self.allconstr['ub'] else None
	@property
	def lp_b_eq(self):
		return stackValues([self.get(('eq','b',k),attr='compiled') for k in self.allconstr['eq']]) if self.allconstr['eq'] else None
	@property
	def lp_b_ub(self):
		return stackValues([self.get(('ub','b',k),attr='compiled') for k in self.allconstr['ub']]) if self.allconstr['ub'] else None

	# CHECKING LOWER/UPPER BOUNDS: Returns index where lower and upper bounds are equal.
	# In these instances, the solver does not distinguish between the two, and may ascribe the dual variable to either.
	# The following two functions ascribe the dual variable to the UPPER bound, if the two bounds are the same (scalar bounds)
	def scalarDualLower(self, sol):
		return np.where(self.lp_bounds[:,0]==self.lp_bounds[:,1], 0, sol['lower']['marginals'])

	def scalarDualUpper(self, sol):
		return np.where(self.lp_bounds[:,0]==self.lp_bounds[:,1], np.add(sol['lower']['marginals'], sol['upper']['marginals']), sol['upper']['marginals'])

	# Get dual solutions:
	def dual_solution(self, sol, scalarDual = True):
		return pd.Series(self.dual_solutionValues(sol, scalarDual=scalarDual), index = self.dual_solutionIndex)

	@property
	def dual_solutionIndex(self):
		ite = ( emptyArrayIfEmpty([self.get(('eq','b',k),attr='compiled').index.values for k in self.allconstr['eq']])+
				emptyArrayIfEmpty([self.get(('ub','b',k),attr='compiled').index.values for k in self.allconstr['ub']])+
				[self.lp_solutionIndex.values]+
				[self.lp_solutionIndex.values])
		return pd.MultiIndex.from_frame(pd.MultiIndex.from_tuples(np.hstack(ite), names = stdNames('s')).to_frame(index=False).assign(_type=self.typeVector(ite)))

	def typeVector(self, ite):
		return np.hstack([['eq']*len(ite[0]), ['ub']*len(ite[1]), ['l']*len(ite[2]), ['u']*len(ite[3])])

	def dual_solutionValues(self, sol, scalarDual = True):
		if scalarDual:
			return np.hstack([sol['eqlin']['marginals'], sol['ineqlin']['marginals'], self.scalarDualLower(sol), self.scalarDualUpper(sol)])
		else:
			return np.hstack([sol['eqlin']['marginals'], sol['ineqlin']['marginals'], sol['lower']['marginals'], sol['upper']['marginals']])
