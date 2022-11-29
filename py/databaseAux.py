from _mixedTools import *
from subsetPandas import rc_pd
import database, pandas as pd, numpy as np

def readSets(db, types = None):
	""" Read sets from database symbols """
	[db.addOrMerge(set_, database.getIndex(symbol).get_level_values(set_).unique()) for symbol in db.getTypes(noneInit(types,['variable'])).values() for set_ in database.getIndex(symbol).names];


def applyMult(symbol, mapping):
	""" Apply 'mapping' to a symbol using multiindex """
	if isinstance(symbol,pd.Index):
		try: 
			return (pd.Series(0, index = symbol).add(pd.Series(0, index = rc_pd(mapping,symbol)))).dropna().index.reorder_levels(symbol.names+[k for k in mapping.names if k not in symbol.names])
		except KeyError:
			return adhocFix_pandasRemovesIndexLevels(symbol,mapping)
	elif isinstance(symbol,pd.Series):
		if symbol.empty:
			return pd.Series([], index = pd.MultiIndex.from_tuples([], names = symbol.index.names + [k for k in mapping.names if k not in symbol.index.names]))
		else:
			s = symbol.add(pd.Series(0, index = rc_pd(mapping,symbol)))
			try: 
				return s.reorder_levels(symbol.index.names+[k for k in mapping.names if k not in symbol.index.names])
			except KeyError:
				s.index = adhocFix_pandasRemovesIndexLevels(s.index, mapping)
				return s

def adhocFix_pandasRemovesIndexLevels(symbol, mapping):
	""" When multiindices are matched, redundant index levels are dropped automatically - this keeps them """
	s1,s2 = pd.Series(0, index = symbol), pd.Series(0, index = rc_pd(mapping,symbol))
	x,y = s1.add(s2).dropna().index, s2.add(s1).dropna().index
	x_df, y_df = x.to_frame().set_index(list(set(x.names).intersection(y.names))), y.to_frame().set_index(list(set(x.names).intersection(y.names)))
	return pd.MultiIndex.from_frame(pd.concat([x_df, y_df], axis =1).reset_index())

def appIndexWithCopySeries(s, copyLevel, newLevel):
	s.index = appendIndexWithCopy(s.index,copyLevel,newLevel)
	return s

def appendIndexWithCopy(index, copyLevel, newLevel):
	if is_iterable(copyLevel):
		return pd.MultiIndex.from_frame(index.to_frame(index=False).assign(**{newLevel[i]: index.get_level_values(copyLevel[i]) for i in range(len(copyLevel))}))
	else: 
		return pd.MultiIndex.from_frame(index.to_frame(index=False).assign(**{newLevel: index.get_level_values(copyLevel)}))

def rollLevelS(s, level, offset):
	s.index = rollLevel(s.index, level, offset)
	return s

def rollLevel(index, level, offset):
	if is_iterable(level):
		return index.set_levels([np.roll(index.levels[index.names.index(level[i])],offset[i]) for i in range(len(level))], level = level)
	else:
		return index.set_levels(np.roll(index.levels[index.names.index(level)], offset), level = level)

def offsetLevelS(s, level, offset):
	s.index = offsetLevel(s.index, level, offset)
	return s

def offsetLevel(index, level, offset):
	if is_iterable(level):
		return index.set_levels([index.levels[index.names.index(level[i])]+offset[i] for i in range(len(level))], level = level)
	else:
		return index.set_levels(index.levels[index.names.index(level)]+offset, level = level)

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
