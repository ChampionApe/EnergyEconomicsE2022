from _mixedTools import *
import database, pandas as pd, numpy as np

def readSets(db, types = None):
	""" Read sets from database symbols """
	[db.addOrMerge(set_, database.getIndex(symbol).get_level_values(set_).unique()) for symbol in db.getTypes(noneInit(types,['variable'])).values() for set_ in database.getIndex(symbol).names];

def applyMult(symbol, mapping):
	""" Apply 'mapping' to a symbol using multiindex """
	if isinstance(symbol,pd.Index):
		return (pd.Series(0, index = symbol).add(pd.Series(0, index = rc_pd(mapping,symbol)))).dropna().index.reorder_levels(symbol.names+[k for k in mapping.names if k not in symbol.names])
	elif isinstance(symbol,pd.Series):
		if symbol.empty:
			return pd.Series([], index = pd.MultiIndex.from_tuples([], names = symbol.index.names + [k for k in mapping.names if k not in symbol.index.names]))
		else: 
			return symbol.add(pd.Series(0, index = rc_pd(mapping,symbol))).reorder_levels(symbol.index.names+[k for k in mapping.names if k not in symbol.index.names])

def grid(v0,vT,index,gridtype='linear',phi=1):
	""" If v0, vT are 1d numpy arrays, returns 2d array. If scalars, returns 1d arrays. """
	if gridtype == 'linear':
		return np.linspace(v0,vT,len(index))
	elif gridtype=='polynomial':
		return np.array([v0+(vT-v0)*((i-1)/(len(index)-1))**phi for i in range(1,len(index)+1)])

def addGrid(v0,vT,index,name,gridtype = 'linear', phi = 1,sort_levels=None, sort_index = False):
	""" NB: Make sure that v0 and vT are sorted similarly (if they are defined over indices) """
	if sort_index:
		v0 = v0.sort_index()
		vT = vT.sort_index()
	if isinstance(v0,pd.Series):
		return pd.DataFrame(grid(v0,vT,index,gridtype=gridtype,phi=phi).T, index = v0.index, columns = index).stack().rename(name).reorder_levels(index.names+v0.index.names if sort_levels is None else sort_levels)
	else:
		return pd.Series(grid(v0,vT,index,gridtype=gridtype,phi=phi), index = index,name=name)

