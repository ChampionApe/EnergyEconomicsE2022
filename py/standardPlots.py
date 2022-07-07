import matplotlib as mpl, matplotlib.pyplot as plt, seaborn, os, pandas as pd, numpy as np
from _mixedTools import *
plt.style.use('seaborn-whitegrid')
mpl.style.use('seaborn')
plt.rcParams['font.family'] = 'Palatino Linotype'
prop_cycle = plt.rcParams["axes.prop_cycle"]
colors = prop_cycle.by_key()["color"]
long_colors = ['#1f78b4','#a6cee3','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00','#cab2d6','#6a3d9a','#ffff99','#b15928']
def one_graph():
    SMALL_SIZE = 16
    MEDIUM_SIZE = 19
    BIGGER_SIZE = 22
    plt.rc('font', size=SMALL_SIZE)          # controls default text sizes
    plt.rc('axes', titlesize=BIGGER_SIZE)     # fontsize of the axes title
    plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
    plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
    plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
    plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
    plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title
def mult_graphs():
    SMALL_SIZE = 13
    MEDIUM_SIZE = 16
    BIGGER_SIZE = 19
    plt.rc('font', size=SMALL_SIZE)          # controls default text sizes
    plt.rc('axes', titlesize=BIGGER_SIZE)     # fontsize of the axes title
    plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
    plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
    plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
    plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
    plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title    


def meritOrderCurve(mc, production, figsize = None, **kwargs):
	one_graph()
	fig, ax = plt.subplots(1,1, figsize = noneInit(figsize, (14,8)))
	meritOrderCurve_df(mc, production, **kwargs).plot(linewidth=2, ax=ax)
	fig.tight_layout()
	ax.set_ylabel("€/GJ" ,labelpad=10)


def meritOrderCurve_df(mc, production, minX = 0, minY = 0, DeltaMaxX = 1):
	df = pd.DataFrame({'c': mc, 'q': production}).sort_values(by='c')
	df['q'] = df['q'].cumsum()
	df.loc['_01'] = [df['c'].iloc[0], minY]
	df.loc['_0E'] = [df['c'].iloc[-2], df['q'][-2]+DeltaMaxX]
	df = df.sort_values(by=['c','q'])
	df['aux'] = df.apply(lambda x, shift: np.roll(x,shift)+np.finfo(float).eps, shift=1)['q']
	df = pd.concat([df[['c','q']], df[['c','aux']].iloc[1:].rename(columns={'aux':'q'})]).sort_values(by=['c','q']).set_index('q').rename_axis(index={'q': '$\sum_i E_i$'}).rename(columns={'c': '$Supply$'})
	df.loc[minX] = minY
	return df