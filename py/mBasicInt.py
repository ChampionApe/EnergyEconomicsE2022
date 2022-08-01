from _mixedTools import *
from databaseAux import appIndexWithCopySeries
from subsetPandas import rc_pd
import lpCompiler
from lpModels import modelShell
_stdLinProg = ('c', 'A_ub', 'b_ub', 'A_eq', 'b_eq', 'bounds')

# A few basic functions for the energy models:
def fuelCost(db):
    return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'), fill_value=0)

def mc(db):
    return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'])

class mBasicInt(modelShell):
    def __init__(self, db, blocks=None, **kwargs):
    	super().__init__(db, blocks=blocks, **kwargs)

    @property
    def hourlyGeneratingCapacity(self):
        return (lpCompiler.broadcast(self.db['GeneratingCapacity'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt')

    @property
    def hourlyLoad(self):
        return pdSum(self.db['LoadVariation'] * self.db['Load'], 'l')

    def preSolve(self, recomputeMC=False, **kwargs):
        if ('mc' not in self.db.symbols) or recomputeMC:
            self.db['mc'] = mc(self.db)

    @property
    def globalDomains(self):
        return {'Generation': pd.MultiIndex.from_product([self.db['h'], self.db['id']]),
                'HourlyDemand': self.db['h'],
                'equilibrium': self.db['h_alias']}

    def initBlocks(self, **kwargs):
        self.blocks['c'] = [{'variableName': 'Generation', 'parameter': lpCompiler.broadcast(self.db['mc'], self.db['h'])},
                            {'variableName': 'HourlyDemand', 'parameter': -self.db['MWP_LoadShedding']}]
        self.blocks['u'] = [{'variableName': 'Generation', 'parameter': self.hourlyGeneratingCapacity},
                            {'variableName': 'HourlyDemand', 'parameter': self.hourlyLoad}]
        self.blocks['eq'] = [{'constrName': 'equilibrium', 'b': None, 
        					'A': [{'variableName': 'Generation', 'parameter'  : appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['Generation']), 'h','h_alias')},
        						  {'variableName': 'HourlyDemand', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['HourlyDemand']), 'h','h_alias')}
        						 ]
        					 }
        					]

    def postSolve(self, solution, **kwargs):
        if solution['status'] == 0:
            self.unloadToDb(solution)
            self.db['Welfare'] = solution['fun']

class mBasicInt_EmissionCap(modelShell):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def hourlyGeneratingCapacity(self):
        return (lpCompiler.broadcast(self.db['GeneratingCapacity'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt')

    @property
    def hourlyLoad(self):
        return pdSum(self.db['LoadVariation'] * self.db['Load'], 'l')

    def preSolve(self, recomputeMC=False, **kwargs):
        if ('mc' not in self.db.symbols) or recomputeMC:
            self.db['mc'] = mc(self.db)

    @property
    def globalDomains(self):
        return {'Generation': pd.MultiIndex.from_product([self.db['h'], self.db['id']]),
                'HourlyDemand': self.db['h'],
                'equilibrium': self.db['h_alias']}

    def initBlocks(self, **kwargs):
        self.blocks['c'] = [{'variableName': 'Generation', 'parameter': lpCompiler.broadcast(self.db['mc'], self.db['h'])},
                            {'variableName': 'HourlyDemand', 'parameter': -self.db['MWP_LoadShedding']}]
        self.blocks['u'] = [{'variableName': 'Generation', 'parameter': self.hourlyGeneratingCapacity},
                            {'variableName': 'HourlyDemand', 'parameter': self.hourlyLoad}]
        self.blocks['eq'] = [{'constrName': 'equilibrium', 'b': None, 
                            'A': [{'variableName': 'Generation', 'parameter'  : appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['Generation']), 'h','h_alias')},
                                  {'variableName': 'HourlyDemand', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['HourlyDemand']), 'h','h_alias')}
                                 ]
                             }
                            ]

    def postSolve(self, solution, **kwargs):
        if solution['status'] == 0:
            self.unloadToDb(solution)
            self.db['Welfare'] = solution['fun']

