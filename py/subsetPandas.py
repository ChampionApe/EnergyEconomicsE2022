import pandas as pd, numpy as np
from database import getIndex
from _mixedTools import noneInit
_admissable_types = (pd.Index, pd.Series, pd.DataFrame)
_numtypes = (int,float,np.generic)

def tryint(x):
    try:
        return int(x)
    except ValueError:
        return x

def rc_AdjPd(symbol, alias = None, lag = None):
	if isinstance(symbol, pd.Index):
		return AdjAliasInd(AdjLagInd(symbol, lag=lag), alias = alias)
	elif isinstance(symbol, pd.Series):
		return symbol.to_frame().set_index(AdjAliasInd(AdjLagInd(symbol.index, lag=lag), alias=alias),verify_integrity=False).iloc[:,0]
	elif isinstance(symbol, pd.DataFrame):
		return symbol.set_index(AdjAliasInd(AdjLagInd(symbol.index, lag=lag), alias=alias),verify_integrity=False)
	elif isinstance(symbol, _numtypes):
		return symbol
	else:
		raise TypeError(f"rc_AdjPd only uses instances {_admissable_types} (and no scalars). Input was type {type(symbol)}")

def AdjLagInd(index_,lag=None):
	if lag:
		if isinstance(index_,pd.MultiIndex):
			return index_.set_levels([index_.levels[index_.names.index(k)]+tryint(v) for k,v in lag.items()], level=lag.keys())
		elif list(index_.domains)==list(lag.keys()):
			return index_+list(lag.values())[0]
	else:
		return index_

def AdjAliasInd(index_,alias=None):
	alias = noneInit(alias,{})
	return index_.set_names([x if x not in alias else alias[x] for x in index_.names])

# Subsetting methods:
def rc_pd(s=None,c=None,alias=None,lag=None, pm = True, **kwargs):
	if isinstance(s,_numtypes):
		return s
	else:
		return rctree_pd(s=s, c = c, alias = alias, lag = lag, pm = pm, **kwargs)

def rc_pdInd(s=None,c=None,alias=None,lag=None,pm=True,**kwargs):
	if isinstance(s,_numtypes):
		return None
	else:
		return rctree_pdInd(s=s,c=c,alias=alias,lag=lag,pm=pm,**kwargs)

def rctree_pd(s=None,c=None,alias=None,lag =None, pm = True, **kwargs):
	adj = rc_AdjPd(s,alias=alias,lag=lag)
	if pm:
		return adj[point_pm(getIndex(adj), c, pm)]
	else:
		return adj[point(getIndex(adj) ,c)]

def rctree_pdInd(s=None,c=None,alias=None,lag=None,pm=True,**kwargs):
	adj = rc_AdjPd(s,alias=alias,lag=lag)
	if pm:
		return getIndex(adj)[point_pm(getIndex(adj), c, pm)]
	else:
		return getIndex(adj)[point(getIndex(adj),c)]

def point_pm(pdObj,vi,pm):
	if isinstance(vi,_admissable_types):
		return bool_ss_pm(pdObj,getIndex(vi),pm)
	elif isinstance(vi,dict):
		return bool_ss_pm(pdObj,rctree_pdInd(**vi),pm)
	elif isinstance(vi,tuple):
		return rctree_tuple_pm(pdObj,vi,pm)
	elif vi is None:
		return pdObj == pdObj

def point(pdObj, vi):
	if isinstance(vi, _admissable_types):
		return bool_ss(pdObj,getIndex(vi))
	elif isinstance(vi,dict):
		return bool_ss(pdObj,rctree_pdInd(**vi))
	elif isinstance(vi,tuple):
		return rctree_tuple(pdObj,vi)
	elif vi is None:
		return pdObj == pdObj

def rctree_tuple(pdObj,tup):
	if tup[0]=='not':
		return translate_k2pd(point(pdObj,tup[1]),tup[0])
	else:
		return translate_k2pd([point(pdObj,vi) for vi in tup[1]],tup[0])

def rctree_tuple_pm(pdObj,tup,pm):
	if tup[0]=='not':
		return translate_k2pd(point_pm(pdObj,tup[1],pm),tup[0])
	else:
		return translate_k2pd([point_pm(pdObj,vi,pm) for vi in tup[1]],tup[0])

def bool_ss(pdObjIndex,ssIndex):
	o,d = overlap_drop(pdObjIndex,ssIndex)
	return pdObjIndex.isin([]) if len(o)<len(ssIndex.names) else pdObjIndex.droplevel(d).isin(reorder(ssIndex,o))

def bool_ss_pm(pdObjIndex,ssIndex,pm):
	o = overlap_pm(pdObjIndex, ssIndex)
	if o:
		return pdObjIndex.droplevel([x for x in pdObjIndex.names if x not in o]).isin(reorder(ssIndex.droplevel([x for x in ssIndex.names if x not in o]),o))
	else:
		return pdObjIndex==pdObjIndex if pm is True else pdObjIndex.isin([])

def overlap_drop(pdObjIndex,index_):
	return [x for x in pdObjIndex.names if x in index_.names],[x for x in pdObjIndex.names if x not in index_.names]

def overlap_pm(pdObjIndex,index_):
	return [x for x in pdObjIndex.names if x in index_.names]

def reorder(index_,o):
	return index_ if len(index_.names)==1 else index_.reorder_levels(o)

def translate_k2pd(l,k):
	if k == 'and':
		return sum(l)==len(l)
	elif k == 'or':
		return sum(l)>0
	elif k == 'not' and isinstance(l,(list,set)):
		return ~l[0]
	elif k == 'not':
		return ~l

