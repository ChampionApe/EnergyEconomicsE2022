from _mixedTools import *
import lpCompiler
from subsetPandas import rc_pd
from lpModels import modelShell
_stdLinProg = ('c', 'A_ub', 'b_ub', 'A_eq', 'b_eq', 'bounds')

# A few basic functions for the energy models:
def fuelCost(db):
    return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'), fill_value=0)

def mc(db):
    return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'])

def fuelConsumption(db, sumOver='id'):
    return pdSum((db['Generation'] * db['FuelMix']).dropna(), sumOver)

def emissionsFuel(db, sumOver='BFt'):
    return pdSum((db['FuelConsumption'] * db['EmissionIntensity']).dropna(), sumOver)

def plantEmissionIntensity(db):
    return (db['FuelMix'] * db['EmissionIntensity']).groupby('id').sum()

class mSimple(modelShell):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    def preSolve(self, recomputeMC=False, **kwargs):
        if ('mc' not in self.db.symbols) or recomputeMC:
            self.db['mc'] = mc(self.db)

    @property
    def globalDomains(self):
        return {'Generation': self.db['id']}

    @property
    def getLoad(self):
        return sum(self.db['Load']) if is_iterable(self.db['Load']) else self.db['Load']

    def initBlocks(self, **kwargs):
        self.blocks['c'] = [{'variableName': 'Generation', 'parameter': self.db['mc']}]
        self.blocks['u'] = [{'variableName': 'Generation', 'parameter': self.db['GeneratingCapacity']}]
        self.blocks['eq'] = [{'constrName': 'equilibrium', 'b': self.getLoad, 'A': [{'variableName': 'Generation', 'parameter': 1}]}]

    def postSolve(self, solution, **kwargs):
        if solution['status'] == 0:
            self.unloadToDb(solution)
            self.db['SystemCosts'] = solution['fun']
            self.db['FuelConsumption'] = fuelConsumption(self.db)
            self.db['Emissions'] = emissionsFuel(self.db)


class mEmissionCap(mSimple):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    def initBlocks(self,**kwargs):
        super().initBlocks(**kwargs)
        self.blocks['ub'] = [{'constrName': 'emissionsCap', 'b': self.db['CO2Cap'], 'A': [{'variableName': 'Generation', 'parameter': plantEmissionIntensity(self.db)}]}]


class mRES(mSimple):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def cleanIds(self):
        s = (self.db['FuelMix'] * self.db['EmissionIntensity']).groupby('id').sum()
        return s[s <= 0].index

    def initBlocks(self, **kwargs):
        super().initBlocks(**kwargs)
        self.blocks['ub'] = [{'constrName': 'RESCapConstraint', 'b': -self.db['RESCap']*self.getLoad, 'A': [{'variableName': 'Generation', 'parameter': -1, 'conditions': self.cleanIds}]}]
