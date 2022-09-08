from _mixedTools import *
from databaseAux import appIndexWithCopySeries, offsetLevelS
from subsetPandas import rc_pd, rc_AdjPd
import lpCompiler
from lpModels import modelShell
_stdLinProg = ('c', 'A_ub', 'b_ub', 'A_eq', 'b_eq', 'bounds')

# Functions for all technology types:
def fuelCost(db):
    return db['FuelPrice'].add(pdSum(db['EmissionIntensity'] * db['EmissionTax'], 'EmissionType'), fill_value=0)

def mc(db):
    """ Marginal costs in €/GJ """
    return pdSum((db['FuelMix'] * fuelCost(db)).dropna(), 'BFt').add(db['OtherMC'], fill_value=0)

def fuelConsumption(db):
    return pdSum((db['FuelMix'] * (subsetIdsTech(db['Generation_E'], ('standard_E','BP'), db).add(
                                  subsetIdsTech(db['Generation_H'], 'standard_H', db), fill_value = 0))).dropna(), ['h','id'])

def plantEmissionIntensity(db):
    return pdSum(db['FuelMix'] * db['EmissionIntensity'], 'BFt')

def emissionsFuel(db):
    return pdSum(fuelConsumption(db) * db['EmissionIntensity'], 'BFt')

def marginalSystemCosts(db,market):
    return -rc_AdjPd(db[f'λ_equilibrium_{market}'], alias={'h_alias':'h', 'g_alias2': 'g'}).droplevel('_type')

def meanMarginalSystemCost(db, var, market):
    return pdSum( (var * marginalSystemCosts(db,market)) / pdNonZero(pdSum(var, 'h')), 'h')

def getTechs(techs, db):
    """ Subset on tech types"""
    return rc_pd(db['id2modelTech2tech'].droplevel('tech'), pd.Index(techs if is_iterable(techs) else [techs], name = 'modelTech')).droplevel('modelTech')

def getTechs_i(techs, db):
    """ Subset on tech types"""
    return rc_pd(db['id2modelTech2tech'].droplevel('modelTech'), pd.Index(techs if is_iterable(techs) else [techs], name = 'tech')).droplevel('tech')

def subsetIdsTech(x, techs, db):
    return rc_pd(x, getTechs(techs,db))

def subsetIdsTech_i(x, techs, db):
    return rc_pd(x, getTechs_i(techs,db))

class mSimple(modelShell):
    """ This class includes 
        (1) Electricity and heat markets, 
        (2) multiple geographic areas, 
        (3) trade in electricity, 
        (4) intermittency in generation, 
        (5) CHP plants and heat pumps """
    def __init__(self, db, blocks = None, **kwargs):
        db.updateAlias(alias=[('h','h_alias'), ('g','g_alias'),('g','g_alias2'),('id','id_alias')])
        db['gConnected'] = db['lineCapacity'].index
        db['id2modelTech2tech'] = lpCompiler.sortAll(lpCompiler.broadcast(pd.Series(0, index = db['id2tech']), db['tech2modelTech'])).index
        super().__init__(db, blocks=blocks, **kwargs)

    @property
    def modelTech_E(self):
        return ('standard_E','BP','HP')
    @property
    def modelTech_H(self):
        return ('standard_H','BP','HP')
    @property
    def hourlyCapFactors(self):
        return lpCompiler.broadcast(self.db['CapVariation'], self.db['id2hvt']).droplevel('hvt')
    @property
    def hourlyGeneratingCap_E(self):
        return subsetIdsTech( (lpCompiler.broadcast(self.db['GeneratingCap_E'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt'),
                                ('standard_E','BP'), self.db)
    @property
    def hourlyGeneratingCap_H(self):
        return subsetIdsTech( (lpCompiler.broadcast(self.db['GeneratingCap_H'], self.db['id2hvt']) * self.db['CapVariation']).dropna().droplevel('hvt'),
                                ('standard_H','HP'), self.db)
    @property
    def hourlyLoad_E(self):
        return pdSum(lpCompiler.broadcast(self.db['Load_E'] * self.db['LoadVariation_E'], self.db['c_E2g']), 'c_E')
    @property
    def hourlyLoad_H(self):
        return pdSum(lpCompiler.broadcast(self.db['Load_H'] * self.db['LoadVariation_H'], self.db['c_H2g']), 'c_H')

    def preSolve(self, recomputeMC=False, **kwargs):
            if ('mc' not in self.db.symbols) or recomputeMC:
                self.db['mc'] = mc(self.db)

    @property
    def globalDomains(self):
        return {'Generation_E': cartesianProductIndex([subsetIdsTech(self.db['id2g'], self.modelTech_E, self.db), self.db['h']]), 
                'Generation_H': cartesianProductIndex([subsetIdsTech(self.db['id2g'], self.modelTech_H, self.db), self.db['h']]),
                'GeneratingCap_E': getTechs(['standard_E','BP'], self.db),
                'GeneratingCap_H': getTechs(['standard_H','HP'], self.db),
                'HourlyDemand_E': pd.MultiIndex.from_product([self.db['g'], self.db['h']]),
                'HourlyDemand_H': pd.MultiIndex.from_product([self.db['g'], self.db['h']]),
                'Transmission_E': cartesianProductIndex([self.db['gConnected'],self.db['h']]),
                'equilibrium_E': pd.MultiIndex.from_product([self.db['g_alias2'], self.db['h_alias']]),
                'equilibrium_H': pd.MultiIndex.from_product([self.db['g_alias2'], self.db['h_alias']]),
                'PowerToHeat': cartesianProductIndex([rc_AdjPd(getTechs(['BP','HP'],self.db), alias = {'id':'id_alias'}), self.db['h_alias']]),
                'ECapConstr': cartesianProductIndex([rc_AdjPd(rc_pd(self.db['id2g'], getTechs(['standard_E','BP'],self.db)), alias = {'id':'id_alias','g':'g_alias'}), self.db['h_alias']]),
                'HCapConstr': cartesianProductIndex([rc_AdjPd(rc_pd(self.db['id2g'], getTechs(['standard_H','HP'],self.db)), alias = {'id':'id_alias','g':'g_alias'}), self.db['h_alias']]),
                'TechCapConstr_E': self.db['TechCap_E'].index,
                'TechCapConstr_H': self.db['TechCap_H'].index}


    def initBlocks(self, **kwargs):
        self.blocks['c'] = [{'variableName': 'Generation_E', 'parameter': lpCompiler.broadcast(self.db['mc'], self.globalDomains['Generation_E']), 'conditions': getTechs(['standard_E','BP'],self.db)},
                            {'variableName': 'Generation_H', 'parameter': lpCompiler.broadcast(self.db['mc'], self.globalDomains['Generation_H']), 'conditions': getTechs(['standard_H','HP'],self.db)},
                            {'variableName': 'HourlyDemand_E', 'parameter': -self.db['MWP_LoadShedding_E']},
                            {'variableName': 'HourlyDemand_H', 'parameter': -self.db['MWP_LoadShedding_H']},
                            {'variableName': 'Transmission_E', 'parameter': lpCompiler.broadcast(self.db['lineMC'], self.db['h'])},
                            {'variableName': 'GeneratingCap_E', 'parameter': lpCompiler.broadcast(self.db['InvestCost_A'], self.db['id2tech']).droplevel('tech').add(self.db['FOM'],fill_value=0)*1000*len(self.db['h'])/8760, 'conditions': getTechs(['standard_E','BP'], self.db)},
                            {'variableName': 'GeneratingCap_H', 'parameter': lpCompiler.broadcast(self.db['InvestCost_A'], self.db['id2tech']).droplevel('tech').add(self.db['FOM'],fill_value=0)*1000*len(self.db['h'])/8760, 'conditions': getTechs(['standard_H','HP'], self.db)}
                           ]
        self.blocks['u'] = [{'variableName': 'HourlyDemand_E', 'parameter': self.hourlyLoad_E},
                            {'variableName': 'HourlyDemand_H', 'parameter': self.hourlyLoad_H},
                            {'variableName': 'Transmission_E', 'parameter': lpCompiler.broadcast(self.db['lineCapacity'], self.db['h'])}
                           ]
        self.blocks['l'] = [{'variableName': 'Generation_E', 'parameter': -np.inf, 'conditions': getTechs('HP',self.db)}]
        self.blocks['eq']= [{'constrName': 'PowerToHeat', 'b': None,
                            'A': [{'variableName': 'Generation_E', 'parameter': appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['Generation_E']), ['id','h'], ['id_alias','h_alias']), 'conditions': getTechs(['BP','HP'],self.db)},
                                  {'variableName': 'Generation_H', 'parameter': appIndexWithCopySeries(lpCompiler.broadcast(-self.db['E2H'], self.globalDomains['Generation_H']), ['id','h'],['id_alias','h_alias']), 'conditions': getTechs(['BP','HP'],self.db)}
                                  ]
                            }
                           ]
        self.blocks['ub'] = [{'constrName': 'equilibrium_E', 'b': None,
                            'A': [{'variableName': 'Generation_E', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['Generation_E']), ['g','h'],['g_alias2','h_alias'])},
                                  {'variableName': 'HourlyDemand_E', 'parameter': appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['HourlyDemand_E']), ['g','h'],['g_alias2','h_alias'])},
                                  {'variableName': 'Transmission_E', 'parameter': appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['Transmission_E']), ['g','h'],['g_alias2','h_alias'])},
                                  {'variableName': 'Transmission_E', 'parameter': appIndexWithCopySeries(pd.Series(self.db['lineLoss']-1, index = self.globalDomains['Transmission_E']), ['g_alias','h'], ['g_alias2','h_alias'])}
                                 ]},
                            {'constrName': 'equilibrium_H', 'b':None,
                                'A': [{'variableName': 'Generation_H', 'parameter': appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['Generation_H']), ['g','h'],['g_alias2','h_alias'])},
                                      {'variableName': 'HourlyDemand_H', 'parameter': appIndexWithCopySeries(pd.Series(1, index = self.globalDomains['HourlyDemand_H']), ['g','h'],['g_alias2','h_alias'])}
                                    ]},
                            {'constrName': 'ECapConstr', 'b': None,
                                'A':[
                                        {'variableName': 'Generation_E', 'parameter': appIndexWithCopySeries(pd.Series(1, index = subsetIdsTech(self.globalDomains['Generation_E'], ['standard_E','BP'],self.db)), ['g','h','id'], ['g_alias','h_alias','id_alias'])},
                                        {'variableName': 'GeneratingCap_E', 'parameter': -appIndexWithCopySeries(rc_AdjPd(subsetIdsTech(lpCompiler.broadcast(self.hourlyCapFactors, self.db['id2g']), ['standard_E','BP'],self.db), alias = {'h':'h_alias', 'g':'g_alias'}), 'id','id_alias')}
                                    ]
                             },
                             {'constrName': 'HCapConstr', 'b': None,
                                'A':[
                                        {'variableName': 'Generation_H', 'parameter': appIndexWithCopySeries(pd.Series(1, index = subsetIdsTech(self.globalDomains['Generation_H'], ['standard_H','HP'],self.db)), ['g','h','id'], ['g_alias','h_alias','id_alias'])},
                                        {'variableName': 'GeneratingCap_H', 'parameter': -appIndexWithCopySeries(rc_AdjPd(subsetIdsTech(lpCompiler.broadcast(self.hourlyCapFactors, self.db['id2g']), ['standard_H','HP'],self.db), alias = {'h':'h_alias', 'g':'g_alias'}), 'id','id_alias')}
                                    ]
                             },
                             {'constrName': 'TechCapConstr_E', 'b': self.db['TechCap_E'],
                                'A':[{'variableName': 'GeneratingCap_E', 'parameter': lpCompiler.adHocMerge(lpCompiler.broadcast(1, self.db['id2tech']), self.db['id2g']), 'conditions': getTechs(['standard_E','BP'],self.db)}]
                             },
                             {'constrName': 'TechCapConstr_H', 'b': self.db['TechCap_H'],
                                'A':[{'variableName': 'GeneratingCap_H', 'parameter': lpCompiler.adHocMerge(lpCompiler.broadcast(1, self.db['id2tech']), self.db['id2g']), 'conditions': getTechs(['standard_H','HP'],self.db)}]
                             }]


    def postSolve(self, solution, **kwargs):
        if solution['status'] == 0:
            self.unloadToDb(solution)
            self.db['Welfare'] = -solution['fun']
            self.db['FuelConsumption'] = fuelConsumption(self.db)
            self.db['Emissions'] = emissionsFuel(self.db)
            self.db['marginalSystemCosts_E'] = marginalSystemCosts(self.db, 'E')
            self.db['marginalSystemCosts_H'] = marginalSystemCosts(self.db, 'H')
            self.db['meanConsumerPrice_E'] = meanMarginalSystemCost(self.db, self.db['HourlyDemand_E'],'E')
            self.db['meanConsumerPrice_H'] = meanMarginalSystemCost(self.db, self.db['HourlyDemand_H'],'H')


class mEmissionCap(mSimple):
    def __init__(self, db, blocks = None, commonCap = True, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)
        self.commonCap = commonCap

    def initBlocks(self, **kwargs):
        super().initBlocks(**kwargs)
        if self.commonCap:
            self.blocks['ub'] += [{'constrName': 'emissionsCap', 'b': pdSum(self.db['CO2Cap'], 'g'), 
                                'A': [{'variableName': 'Generation_E', 'parameter': lpCompiler.broadcast(plantEmissionIntensity(self.db).xs('CO2',level='EmissionType'), self.globalDomains['Generation_E']), 'conditions': getTechs(['standard_E','BP'],self.db)},
                                      {'variableName': 'Generation_H', 'parameter': lpCompiler.broadcast(plantEmissionIntensity(self.db).xs('CO2',level='EmissionType'), self.globalDomains['Generation_H']), 'conditions': getTechs('standard_H',self.db)}]
                                }]
        else:
            self.blocks['ub'] += [{'constrName': 'emissionsCap', 'b': rc_pd(self.db['CO2Cap'], alias={'g':'g_alias'}), 
                                'A': [{'variableName': 'Generation_E', 'parameter': appIndexWithCopySeries(lpCompiler.broadcast(plantEmissionIntensity(self.db).xs('CO2',level='EmissionType'), self.globalDomains['Generation_E']),'g','g_alias'), 'conditions': getTechs(['standard_E','BP'],self.db)},
                                      {'variableName': 'Generation_H', 'parameter': appIndexWithCopySeries(lpCompiler.broadcast(plantEmissionIntensity(self.db).xs('CO2',level='EmissionType'), self.globalDomains['Generation_H']),'g','g_alias'), 'conditions': getTechs('standard_H',self.db)}]
                                }]

class mRES(mSimple):
    def __init__(self, db, blocks=None, commonCap = True, **kwargs):
        super().__init__(db, blocks=blocks, **kwargs)
        self.commonCap = commonCap

    @property
    def cleanIds(self):
        s = (self.db['FuelMix'] * self.db['EmissionIntensity']).groupby('id').sum()
        return s[s <= 0].index

    def initBlocks(self, **kwargs):
        super().initBlocks(**kwargs)
        if self.commonCap:
            self.blocks['ub'] += [{'constrName': 'RESCapConstraint', 'b': 0, 'A': [ {'variableName': 'Generation_E', 'parameter': -1, 'conditions': ('and', [self.cleanIds, getTechs(['standard_E','BP'],self.db)])},
                                                                                   {'variableName': 'Generation_H', 'parameter': -1, 'conditions': ('and', [self.cleanIds, getTechs(['standard_H','HP'],self.db)])},
                                                                                   {'variableName': 'HourlyDemand_E', 'parameter': self.db['RESCap'].mean()},
                                                                                   {'variableName': 'HourlyDemand_H', 'parameter': self.db['RESCap'].mean()}]}]
        else:
            self.blocks['ub'] += [{'constrName': 'RESCapConstraint', 'b': pd.Series(0, index = self.db['RESCap'].index), 
                                    'A': [  {'variableName': 'Generation_E', 'parameter': 
                                                appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['Generation_E']), 'g','g_alias'), 'conditions': ('and', [self.cleanIds, getTechs(['standard_E','BP'],self.db)])},
                                            {'variableName': 'Generation_H', 'parameter': 
                                                appIndexWithCopySeries(pd.Series(-1, index = self.globalDomains['Generation_H']), 'g','g_alias'), 'conditions': ('and', [self.cleanIds, getTechs(['standard_H','HP'],self.db)])},
                                            {'variableName': 'HourlyDemand_E', 'parameter': 
                                                appIndexWithCopySeries(lpCompiler.broadcast(self.db['RESCap'], self.globalDomains['HourlyDemand_E']), 'g', 'g_alias')},
                                            {'variableName': 'HourlyDemand_H', 'parameter': 
                                                appIndexWithCopySeries(lpCompiler.broadcast(self.db['RESCap'], self.globalDomains['HourlyDemand_H']), 'g', 'g_alias')}
                                         ]
                                 }
                                ]