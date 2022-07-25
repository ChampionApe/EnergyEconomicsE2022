from _mixedTools import *
from copy import deepcopy
_numtypes = (int,float,np.generic)

def type_(s):
	if isinstance(s, pd.Index):
		return 'set'
	elif isinstance(s, pd.Series):
		return 'variable'
	elif isinstance(s,_numtypes):
		return 'scalar'
	else:
		return 'other'
def getIndex(symbol):
	""" Defaults to None if no index is defined. """
	if isinstance(symbol,(pd.Series,pd.DataFrame)):
		return symbol.index
	elif isinstance(symbol, pd.Index):
		return symbol
	elif not is_iterable(symbol):
		return None
def getValues(symbol):
	""" Default to None if no values are defined """
	if isinstance(symbol, (pd.Series, pd.DataFrame)):
		return symbol.values
	elif isinstance(symbol, pd.Index):
		return None
	elif not is_iterable(symbol):
		return symbol
def mergeVals(s1,s2):
	if isinstance(s1,pd.Series):
		return s1.combine_first(s2)
	elif isinstance(s1,pd.Index):
		return s1.union(s2)
	else:
		return s1
def symbols_(db_i):
	""" return dictionary of symbols """
	return db_i.symbols if isinstance(db_i, db) else db_i	


class db:
	""" Collection of data """
	def __init__(self,name='name',symbols=None,alias=None):
		self.name = name
		self.symbols = noneInit(symbols,{})
		self.updateAlias(alias=alias)

	def updateAlias(self,alias=None):
		self.alias = self.alias.union(pd.MultiIndex.from_tuples(noneInit(alias,[]), names = ['from','to'])) if hasattr(self,'alias') else pd.MultiIndex.from_tuples(noneInit(alias,[]), names = ['from','to'])

	def __iter__(self):
		return iter(self.symbols.values())

	def __len__(self):
		return len(self.symbols)

	def __getitem__(self,item):
		try:
			return self.symbols[item]
		except KeyError:
			try:
				return self.symbols[self.getAlias(item)].rename(item)
			except TypeError:
				raise TypeError(f"Symbol {item} not in database")

	def __setitem__(self,item,value):
		if item in self.symbols:
			if not is_iterable(value) and is_iterable(self[item]):
				value = pd.Series(value,index=self[item].index,name=self[item].name)
		self.symbols[item] = value

	def __delitem__(self,item):
		del(self.symbols[item])

	def copy(self):
		obj = type(self).__new__(self.__class__,None)
		obj.__dict__.update(deepcopy(self.__dict__).items())
		return obj

	def getTypes(self,types=['variable']):
		return {k:v for k,v in self.symbols.items() if type_(v) in types}

	def variableDomains(self,set_,types=['variable']):
		""" Return 'types' defined over 'set_'"""
		return {k:v for k,v in self.getTypes(types).items() if set_ in getIndex(v)}

	@property
	def aliasDict(self):
		return {k: self.alias.get_level_values(1)[self.alias.get_level_values(0) == k] for k in self.alias.get_level_values(0).unique()}

	@property
	def aliasDict0(self):
		return {key: self.aliasDict[key].insert(0,key) for key in self.aliasDict}

	def getAlias(self,x,index_=0):
		if x in self.alias.get_level_values(0):
			return self.aliasDict0[x][index_]
		elif x in self.alias.get_level_values(1):
			return self.aliasDict0[self.alias.get_level_values(0)[self.alias.get_level_values(1)==x][0]][index_]
		elif x in self.getTypes(['set']) and index_==0:
			return x
		else:
			raise TypeError(f"{x} is not aliased")

	def addOrMerge(self, name, symbol, priority = 'first'):
		if name in self.symbols:
			self[name] = mergeVals(self.symbols[name],symbol) if priority == 'first' else mergeVals(symbol, self.symbols[name])
		else:
			self[name] = symbol

	def mergeDbs(self, dbOther, priority='first'):
		""" Merge all symbols in two databases """
		[self.addOrMerge(name, symbol, priority=priority) for name,symbol in symbols_(dbOther).items()];

