from _mixedTools import *
from databaseAux import appIndexWithCopySeries
from subsetPandas import rc_pd
import lpCompiler
from lpModels import modelShell
_stdLinProg = ('c', 'A_ub', 'b_ub', 'A_eq', 'b_eq', 'bounds')

# Functions for all mBasicInt models:
def fuelCost(db):
    return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'), fill_value=0)

def mc(db):
    """ Marginal costs in €/GJ """
    return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'])

def fuelConsumption(db):
    return pdSum((db['Generation'] * db['FuelMix']).dropna(), ['h','id'])

def plantEmissionIntensity(db):
    return pdSum(db['FuelMix'] * db['EmissionIntensity'], 'BFt')

def emissionsFuel(db):
    return pdSum(fuelConsumption(db) * db['EmissionIntensity'], 'BFt')

def fixedCosts(db):
    """ fixed operating and maintenance costs of installed capacity in 1000€. """
    return db['FOM']*db['GeneratingCapacity'] * len(db['h'])/8760

def variableCosts(db):
    """ short run costs in 1000€. """
    return db['mc']*pdSum(db['Generation'], 'h') / 1000

def totalCosts(db):
    """ total electricity generating costs in 1000€ """
    return fixedCosts(db).add(variableCosts(db),fill_value = 0)

def averageCapacityCosts(db):
    return 1000 * totalCosts(db) / pdNonZero(db['GeneratingCapacity'])

def averageEnergyCosts(db):
    return 1000 * totalCosts(db) / pdNonZero(pdSum(db['Generation'], 'h'))

def theoreticalCapacityFactor(db):
    return pdSum( (db['Generation']/pdNonZero(len(db['h']) * db['GeneratingCapacity'])).dropna(), 'h')

def practicalCapacityFactor(model):
    return ( pdSum(model.db['Generation'], 'h')/ pdNonZero(pdSum(model.hourlyGeneratingCapacity, 'h')) ).dropna()

def marginalSystemCosts(db):
    return rc_pd(db['λ_equilibrium'], alias={'h_alias':'h'}).droplevel('_type')

def meanMarginalSystemCost(db, var):
    return pdSum( (var * marginalSystemCosts(db)) / pdNonZero(pdSum(var, 'h')), 'h')

def downlift(db):
    return meanMarginalSystemCost(db, db['HourlyDemand']) - meanMarginalSystemCost(db, db['Generation'])

def marginalEconomicRevenue(model):
    ϑ = model.db['λ_Generation'].xs('u', level = '_type')
    ϑ = ϑ[ϑ!=0]
    return pdSum(marginalSystemCosts(model.db) * rc_pd(model.hourlyCapFactors, ϑ), 'h')

def marginalEconomicValue(model):
    return - pdSum(model.db['λ_Generation'].xs('u',level='_type') * model.hourlyCapFactors, 'h').add( 1000 * model.db['FOM'] * len(model.db['h'])/8760, fill_value = 0)

class mSimple(modelShell):
    def __init__(self, db, blocks=None, **kwargs):
        db.updateAlias(alias=[('h','h_alias')])
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def hourlyGeneratingCapacity(self):
        return (lpCompiler.broadcast(self.db['GeneratingCapacity'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt')

    @property
    def hourlyCapFactors(self):
        return lpCompiler.broadcast(rc_pd(self.db['CapVariation'], self.db['id2hvt']), self.db['id2hvt']).droplevel('hvt')

    @property
    def hourlyLoad(self):
        return pdSum(self.db['LoadVariation'] * self.db['Load'], 'c')

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
            self.db['Welfare'] = -solution['fun']
            self.db['FuelConsumption'] = fuelConsumption(self.db)
            self.db['Emissions'] = emissionsFuel(self.db)
            self.db['capacityFactor'] = theoreticalCapacityFactor(self.db)
            self.db['capacityCosts'] = averageCapacityCosts(self.db)
            self.db['energyCosts'] = averageEnergyCosts(self.db)
            self.db['marginalSystemCosts'] = marginalSystemCosts(self.db)
            self.db['marginalEconomicValue'] = marginalEconomicValue(self)

class mEmissionCap(mSimple):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    def initBlocks(self, **kwargs):
        super().initBlocks(**kwargs)
        self.blocks['ub'] = [{'constrName': 'emissionsCap', 'b': self.db['CO2Cap'], 
                            'A': [{'variableName': 'Generation', 'parameter': lpCompiler.broadcast(plantEmissionIntensity(self.db).xs('CO2',level='EmissionType'), self.db['h'])}]
                            }]

class mRES(mSimple):
    def __init__(self, db, blocks=None, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def cleanIds(self):
        s = (self.db['FuelMix'] * self.db['EmissionIntensity']).groupby('id').sum()
        return s[s <= 0].index

    def initBlocks(self, **kwargs):
        super().initBlocks(**kwargs)
        self.blocks['ub'] = [{'constrName': 'RESCapConstraint', 'b': 0, 'A': [  {'variableName': 'Generation', 'parameter': -1, 'conditions': self.cleanIds},
                                                                                {'variableName': 'HourlyDemand', 'parameter': self.db['RESCap']}]}]

