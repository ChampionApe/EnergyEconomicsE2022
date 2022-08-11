import numpy as np

def BoundedMultivariateNormalDist(means, cov_matrix, dim_bounds=None, size=1, rng=None):
    means = np.array(means)
    cov_matrix = np.array(cov_matrix)
    ndims = means.shape[0]

    # if no dim_bounds if provided make a dim_bounds with np.nans
    if dim_bounds is None:
        dim_bounds = np.tile((np.nan),(ndims,2)) # make a ndims x 2 array of np.nan values
    
    # define a local size
    local_size = size

    # create an empty array
    return_samples = np.empty([0,ndims])

    # generate new samples while the needed size is not reached
    while not return_samples.shape[0] == size:

        # get 'size' number of samples
        samples = rng.multivariate_normal(means, cov_matrix,size=local_size)
        for dim, bounds in enumerate(dim_bounds):

            # keep only the samples that are bigger than the lower bound
            if not np.isnan(bounds[0]): # bounds[0] is the lower bound
                samples = samples[(samples[:,dim] > bounds[0])]  # samples[:,dim] is the column of the dim

            # keep only the samples that are smaller than the upper bound
            if not np.isnan(bounds[1]): # bounds[1] is the upper bound
                samples = samples[(samples[:,dim] < bounds[1])]   # samples[:,dim] is the column of the dim


        # input the samples into the retun samples
        return_samples = np.vstack([return_samples, samples])

        # get new size which is the difference between the requested size and the size so far.
        local_size = size - return_samples.shape[0]
    
    # return a single value when the requested size is 1 (or not specified)
    if return_samples.shape[0] == 1:
        return return_samples[0]
    # otherwise 
    else:
        return return_samples