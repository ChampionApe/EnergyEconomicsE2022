# Energy Economics of the Green Transition, Fall 2022
Code repository for core models and exercises for the course "Energy Economics of the Green Transition" at UCPH. As this is the first time the course is running resources will be made available as it progresses. 

A few comments on the structure:
- Models are written as Python classes stored in the "py" folder. 
- Each model has a short, technical documentation in a notebook "M_X.ipynb" with X being the specific model.
- Exercises that interact with the model classes are stored as "Ei_Problem.ipynb" with i being the specific exercise. Suggested solutions to the exercises can be found in "Ei_SolutionGuide.ipynb".
- The model classes are getting progressingly more complex in the following order:
  1. ```mBasic```
  2. ```mBasicInt```
  3. ```mBasicTrade```
  4. ```mBasicPH```
  5. ```mBasicPH_storage```
  6. ```mGF_Trade```
  7. ```mGF_PH```
  8. ```mGF_PH_storage```

## Installation guide:
The models require installation of Python (e.g. through *Anaconda*), some type of git tool (e.g. *Github Desktop*, Git, Tortoise), and an editor for python code (e.g. *VSCode* or Sublime). The course *Introduction to Programming and Numerical Analysis* provides some pretty detailed guides for setting up Python and VSCode: https://numeconcopenhagen.netlify.app/guides/. We do, however, rely on different packages in this course, so you will need to supplement the installation with a few extra steps.

#### Requirements (after installation):
* Open "Anaconda Prompt" ("Terminal" for Mac) and write: ```conda install jupyterlab nodejs pandas openpyxl scipy```.
* Also from "Anaconda Prompt" ("Terminal" for Mac): ```pip install seaborn```.
