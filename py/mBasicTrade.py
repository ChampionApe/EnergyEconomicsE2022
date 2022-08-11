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
    return (1000 * totalCosts(db) / pdNonZero(db['GeneratingCapacity'])).droplevel('g')

def averageEnergyCosts(db):
    return (1000 * totalCosts(db) / pdNonZero(pdSum(db['Generation'], 'h'))).droplevel('g')

def theoreticalCapacityFactor(db):
    return pdSum( (db['Generation']/pdNonZero(len(db['h']) * db['GeneratingCapacity'])).dropna(), 'h').droplevel('g')

def practicalCapacityFactor(model):
    return ( pdSum(model.db['Generation'], 'h')/ pdNonZero(pdSum(model.hourlyGeneratingCapacity, 'h')) ).dropna().droplevel('g')

def marginalSystemCosts(db):
    return rc_pd(db['λ_equilibrium'], alias={'h_alias':'h', 'g_alias2': 'g'}).droplevel('_type')

def meanMarginalSystemCost(db, var):
    return pdSum( (var * marginalSystemCosts(db)) / pdNonZero(pdSum(var, 'h')), 'h')

def downlift(db):
    return meanMarginalSystemCost(db, db['HourlyDemand']) - meanMarginalSystemCost(db, db['Generation'])

def marginalEconomicRevenue(model):
    ϑ = model.db['λ_Generation'].xs('u', level = '_type')
    ϑ = ϑ[ϑ!=0]
    return pdSum(marginalSystemCosts(model.db) * rc_pd(model.hourlyCapFactors, ϑ), 'h')

def marginalEconomicValue(model):
    return (- pdSum(model.db['λ_Generation'].xs('u',level='_type') * model.hourlyCapFactors, 'h').add( 1000 * model.db['FOM'] * len(model.db['h'])/8760, fill_value = 0)).droplevel('g')

def priceDifferences(db):
    pe = rc_pd(db['marginalSystemCosts'], db['Transmission'].index.droplevel('g_alias'))
    return lpCompiler.sortAll(pd.Series(0,index=db['gConnected']).add(-pe).add(pe.rename_axis(index={'g':'g_alias'})))

def congestionRent(db):
    return priceDifferences(db) * db['Transmission']

class mBasicTrade(modelShell):
    def __init__(self, db, blocks=None, **kwargs):
        db.updateAlias(alias=[('h','h_alias'), ('g','g_alias'),('g','g_alias2')])
        db['gConnected'] = db['lineCapacity'].index
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def hourlyGeneratingCapacity(self):
        return (lpCompiler.broadcast(self.db['GeneratingCapacity'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt')

    @property
    def hourlyCapFactors(self):
        return lpCompiler.broadcast(rc_pd(self.db['CapVariation'], self.db['id2hvt']), self.db['id2hvt']).droplevel('hvt')

    @property
    def hourlyLoad(self):
        return pdSum(lpCompiler.broadcast(self.db['Load'] * self.db['LoadVariation'], self.db['c2g']), 'c')

    def preSolve(self, recomputeMC=False, **kwargs):
        if ('mc' not in self.db.symbols) or recomputeMC:
            self.db['mc'] = mc(self.db)

    @property
    def globalDomains(self):
        return {'Generation': cartesianProductIndex([self.db['id2g'], self.db['h']]),
                'HourlyDemand': pd.MultiIndex.from_product([self.db['g'], self.db['h']]),
                'equilibrium': pd.MultiIndex.from_product([self.db['g_alias2'], self.db['h_alias']]),
                'Transmission': cartesianProductIndex([self.db['gConnected'],self.db['h']])}

    def initBlocks(self, **kwargs):
        self.blocks['c'] = [{'variableName': 'Generation', 'parameter': lpCompiler.broadcast(self.db['mc'], self.globalDomains['Generation'])},
                            {'variableName': 'HourlyDemand', 'parameter': -self.db['MWP_LoadShedding']},
                            {'variableName': 'Transmission', 'parameter': lpCompiler.broadcast(self.db['lineMC'], self.db['h'])}]
        self.blocks['u'] = [{'variableName': 'Generation',   'parameter': lpCompiler.broadcast(self.hourlyGeneratingCapacity, self.globalDomains['Generation'])},
                            {'variableName': 'HourlyDemand', 'parameter': self.hourlyLoad},
                            {'variableName': 'Transmission', 'parameter': lpCompiler.broadcast(self.db['lineCapacity'], self.db['h'])}]
        self.blocks['eq'] = [{'constrName': 'equilibrium', 'b': None, 
        					'A': [
                                    {'variableName': 'Generation', 'parameter'  : appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['Generation']), ['g','h'],['g_alias2','h_alias'])},
                                    {'variableName': 'HourlyDemand', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['HourlyDemand']), ['g','h'],['g_alias2','h_alias'])},
                                    {'variableName': 'Transmission', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['Transmission']), ['g','h'],['g_alias2','h_alias'])},
                                    {'variableName': 'Transmission', 'parameter': appIndexWithCopySeries(pd.Series(1-self.db['lineLoss'], index = self.globalDomains['Transmission']), ['g_alias','h'], ['g_alias2','h_alias'])}
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
            self.db['congestionRent'] = congestionRent(self.db)
