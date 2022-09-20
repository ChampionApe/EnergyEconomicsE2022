import itertools, numpy as np, pandas as pd
from collections.abc import Iterable
from six import string_types
from scipy import sparse

def sparseDF(index, columns, dtype = None):
	return pd.DataFrame.sparse.from_spmatrix(sparse.coo_array( (len(index),len(columns)), dtype=noneInit(dtype, np.int8)), index = index, columns=columns)

def noneInit(x,FallBackVal):
	return FallBackVal if x is None else x

def ifinInit(x,kwargs,FallBackVal):
	return kwargs[x] if x in kwargs else FallBackVal

def is_iterable(arg):
	return isinstance(arg, Iterable) and not isinstance(arg, string_types)

def pdGb(x, by):
	if is_iterable(by):
		return x.groupby([k for k in x.index.names if k not in by])
	else:
		return x.groupby([k for k in x.index.names if k != by])
def pdSum(x,sumby):
	return pdGb(x, sumby).sum() if isinstance(x.index, pd.MultiIndex) else sum(x)	

def pdNonZero(x):
	return x.where(x!=0)

def cartesianProductIndex(indices):
	""" Return the cartesian product of pandas indices; assumes no overlap in levels of indices. """
	if any((i.empty for i in indices)):
		return pd.MultiIndex.from_tuples([], names = [n for l in indices for n in l.names]) 
	else: 
		ndarray = fastCartesianProduct([i.values for i in indices])
		return pd.MultiIndex.from_arrays(concatArrays(ndarray, indices).T, names = [n for l in indices for n in l.names])

# Auxiliary function for cartesianProductIndex
def fastCartesianProduct(arrays):
	la = len(arrays)
	L = *map(len, arrays), la
	dtype = np.result_type(*arrays)
	arr = np.empty(L, dtype=dtype)
	arrs = *itertools.accumulate(itertools.chain((arr,), itertools.repeat(0, la-1)), np.ndarray.__getitem__),
	idx = slice(None), *itertools.repeat(None, la-1)
	for i in range(la-1, 0, -1):
		arrs[i][..., i] = arrays[i][idx[:la-i]]
		arrs[i-1][1:] = arrs[i]
	arr[..., 0] = arrays[0][idx]
	return arr.reshape(-1, la)

# Auxiliary function for cartesianProductIndex
def getndarray(onedarray):
	return pd.MultiIndex.from_tuples(onedarray).to_frame(index=False).values

# Auxiliary function for cartesianProductIndex
def ndarray_or_1darray(ndarray, indices, i):
	return getndarray(ndarray[:,i]) if isinstance(indices[i], pd.MultiIndex) else ndarray[:,i:i+1]

# Auxiliary function for cartesianProductIndex
def concatArrays(ndarray, indices):
	return np.concatenate(tuple(ndarray_or_1darray(ndarray, indices, i) for i in range(len(indices))), axis=1)

class OrdSet:
	def __init__(self,i=None):
		self.v = list(dict.fromkeys(noneInit(i,[])))

	def __iter__(self):
		return iter(self.v)

	def __len__(self):
		return len(self.v)

	def __getitem__(self,item):
		return self.v[item]

	def __setitem__(self,item,value):
		self.v[item] = value

	def __add__(self,o):
		return OrdSet(self.v+list(o))

	def __sub__(self,o):
		return OrdSet([x for x in self.v if x not in o])

	def union(self,*args):
		return OrdSet(self.__add__([x for l in args for x in l]))

	def intersection(self,*args):
		return OrdSet([x for l in self.union(args) for x in l if x in self.v])

	def update(self,*args):
		self.v = self.union(*args).v

	def copy(self):
		return OrdSet(self.v.copy())