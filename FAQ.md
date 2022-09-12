# Frequently Asked Questions

### The pandas dataframe does not have any attribute "sparse". 
You need to update to a newer version of the pandas package. You can update a package using ```conda``` or ```pip```. Using Anaconda Prompt (Terminal if Mac) and write:
 ```Terminal
 conda update pandas
 ```
 or 
 ```Terminal
pip install pandas --upgrade
```
You should at least have pandas 1.3.4 version installed. 

### module 'scipy.sparse' has no attribute 'coo_array'
You need to update to a newer version of the scipy package (version >=1.8.0). You can update a package using ```conda``` or ```pip```. Using Anaconda Prompt (Terminal if Mac) and write:
 ```Terminal
 conda update scipy
 ```
 or 
 ```Terminal
pip install scipy --upgrade
```
