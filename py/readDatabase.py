import pandas as pd, database
import openpyxl,io

def dbFromWB(workbook, read, spliton='/'):
	""" 'read' should be a dictionary with keys = method, value = list of sheets to apply this to."""
	wb = simpleLoad(workbook) if isinstance(workbook,str) else workbook
	db = database.db()
	for function,sheets in read.items():
		for sheet in sheets:
			db.mergeDbs(eval(f"{function}(wb[sheet],spliton=spliton)"))
	return db

def simpleLoad(workbook):
	with open(workbook,"rb") as file:
		in_mem_file = io.BytesIO(file.read())
	return openpyxl.load_workbook(in_mem_file,read_only=True,data_only=True)

def sheetnames_from_wb(wb):
	return (sheet.title for sheet in wb._sheets)

def sets(sheet, **kwargs):
	""" Return a dictionary with keys = set names and values = pandas objects. na entries are removed. 
		The name of each set is defined as the first entry in each column. """
	pd_sheet = pd.DataFrame(sheet.values)
	return {pd_sheet.iloc[0,i]: pd.Index(pd_sheet.iloc[1:,i].dropna(),name=pd_sheet.iloc[0,i]) for i in range(pd_sheet.shape[1])}

def subsets(sheet,spliton='/'):
	pd_sheet = pd.DataFrame(sheet.values)
	return {pd_sheet.iloc[0,i].split(spliton)[0]: pd.Index(pd_sheet.iloc[1:,i].dropna(),name=pd_sheet.iloc[0,i].split(spliton)[1]) for i in range(pd_sheet.shape[1])}

def aux_map(sheet,col,spliton):
	pd_temp = sheet[col]
	pd_temp.columns = [x.split(spliton)[1] for x in pd_temp.iloc[0,:]]
	return pd.MultiIndex.from_frame(pd_temp.dropna().iloc[1:,:])

def maps(sheet,spliton='/'):
	pd_sheet = pd.DataFrame(sheet.values)
	pd_sheet.columns = [x.split(spliton)[0] for x in pd_sheet.iloc[0,:]]
	return {col: aux_map(pd_sheet,col,spliton) for col in set(pd_sheet.columns)}

def aux_var(sheet,col,spliton):
	pd_temp = sheet[col].dropna()
	pd_temp.columns = [x.split(spliton)[1] for x in pd_temp.iloc[0,:]]
	if pd_temp.shape[1]==2:
		index = pd.Index(pd_temp.iloc[1:,0])
	else:
		index = pd.MultiIndex.from_frame(pd_temp.iloc[1:,:-1])
	return pd.Series(pd_temp.iloc[1:,-1].values,index=index,name=col)

def variables(sheet,spliton='/'):
	pd_sheet = pd.DataFrame(sheet.values)
	pd_sheet.columns = [x.split(spliton)[0] for x in pd_sheet.iloc[0,:]]
	return {col: aux_var(pd_sheet,col,spliton) for col in set(pd_sheet.columns)}

def scalars(sheet,**kwargs):
	pd_sheet = pd.DataFrame(sheet.values)
	return {pd_sheet.iloc[i,0]: pd_sheet.iloc[i,1] for i in range(pd_sheet.shape[0])}

def variable2D(sheet,spliton='/',**kwargs):
	""" Read in 2d variable arranged in matrix; Note, only reads 1 variable per sheet."""
	pd_sheet = pd.DataFrame(sheet.values)
	domains = pd_sheet.iloc[0,0].split(spliton)
	var = pd.DataFrame(pd_sheet.iloc[1:,1:].values, index = pd.Index(pd_sheet.iloc[1:,0],name=domains[1]), columns = pd.Index(pd_sheet.iloc[0,1:], name = domains[2])).stack()
	var.name = domains[0]
	return {domains[0]: var}