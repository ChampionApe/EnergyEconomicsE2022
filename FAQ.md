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
You need to update to a newer version of the scipy package (version >=1.8.0). You can update a package using ```conda``` or ```pip```. **NOTE: To update to the most recent scipy version, you have to use the pip version here**. 
Using Anaconda Prompt (Terminal if Mac) and write:
 ```Terminal
pip install scipy --upgrade
```

### Issue with Python version < 3.9 fixed as of (26/9/2022):
Previously, the classes applied the merge operator for dictionaries ```|``` - which was only implemented in Python>=3.9. This has been reversed using the ```{**d1 | **d2}``` syntax instead.   
