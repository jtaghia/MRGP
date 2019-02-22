
import abc
import numpy as np
import GPy
import gpflow
import warnings
warnings.filterwarnings("ignore")


class RegressionMethod(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.preprocess = True

    def _preprocess(self, data,  train):
        """Zero-mean, unit-variance normalization by default"""
        if train:
            inputs, labels = data
            self.data_mean = inputs.mean(axis=0)
            self.data_std = inputs.std(axis=0)
            self.labels_mean = labels.mean(axis=0)
            self.labels_std = labels.std(axis=0)
            return ((inputs-self.data_mean)/self.data_std, (labels-self.labels_mean)/self.labels_std)
        else:
            return (data-self.data_mean)/self.data_std

    def _reverse_trans_labels(self, labels):
        return labels*self.labels_std+self.labels_mean

    def fit(self, train_data):
        if self.preprocess:
            train_data = self._preprocess(train_data, True)
        return self._fit(train_data)

    def predict(self, test_data):
        if self.preprocess:
            test_data = self._preprocess(test_data, False)
        labels = self._predict(test_data)
        if self.preprocess:
            labels = self._reverse_trans_labels(labels)
        return labels

    @abc.abstractmethod
    def _fit(self, train_data):
        """Fit the model. Return True if successful"""
        return True

    @abc.abstractmethod
    def _predict(self, test_data):
        """Predict on test data"""
        return None


class GP_RBF(RegressionMethod):
    name = 'GP_RBF'

    def _fit(self, train_data):
        inputs, labels = train_data
        k = GPy.kern.RBF(inputs.shape[-1], ARD=False)
        self.model = GPy.models.GPRegression(inputs, labels,  kernel=k)
        self.model.likelihood.variance[:] = labels.var()*0.01
        self.model.optimize()
        return True

    def _predict(self, test_data):
        return self.model.predict(test_data)[0]


class SparseGP_RBF(RegressionMethod):
    name = 'SparseGP_RBF'

    def _fit(self, train_data):
        inputs, labels = train_data
        self.model = GPy.models.SparseGPRegression(inputs, labels,
                                                   kernel=GPy.kern.RBF(inputs.shape[-1], ARD=True) +
                                                   GPy.kern.Linear(inputs.shape[1], ARD=True),
                                                   num_inducing=1000)
        self.model.likelihood.variance[:] = labels.var()*0.01
        self.model.optimize()
        return True

    def _predict(self, test_data):
        return self.model.predict(test_data)[0]


class SVIGP_RBF(RegressionMethod):
    name = 'SVIGP_RBF'

    def _fit(self, train_data):
        X, Y = train_data
        Z = X[np.random.permutation(X.shape[0])[:100]]
        k = GPy.kern.RBF(X.shape[1], ARD=True) + GPy.kern.Linear(X.shape[1], ARD=True) + \
            GPy.kern.White(X.shape[1], 0.01)

        lik = GPy.likelihoods.StudentT(deg_free=3.)
        self.model = GPy.core.SVGP(X, Y, Z=Z, kernel=k, likelihood=lik)
        [self.model.optimize('scg', max_iters=100, gtol=0, messages=0, xtol=0, ftol=0) for i in range(10)]
        self.model.optimize('bfgs', max_iters=1000, gtol=0, messages=0)
        return True

    def _predict(self, test_data):
        return self.model.predict(test_data, include_likelihood=False)[0]


class BGPLVM(RegressionMethod):
    name = 'BGPLVM'

    def _fit(self, train_data):
        inputs, labels = train_data
        Z = inputs[np.random.permutation(inputs.shape[0])[:100]]
        self.model = gpflow.models.BayesianGPLVM(X_mean=inputs, X_var=np.ones_like(inputs)*inputs.var()*0.01, Y=labels,
                                                 kern=gpflow.kernels.RBF(inputs.shape[-1], ARD=True),
                                                 M=100, Z=Z)
        self.model.build()
        return True

    def _predict(self, test_data):
        return self.model.predict_y(test_data)[0]


class SGP_FITC(RegressionMethod):
    name = 'SGP_FITC'

    """
        This implements GP regression with the FITC approximation.
        @inproceedings{Snelson06sparsegaussian,
        author = {Edward Snelson and Zoubin Ghahramani},
        title = {Sparse Gaussian Processes using Pseudo-inputs},
        booktitle = {Advances In Neural Information Processing Systems },
        year = {2006},
        pages = {1257--1264},
        publisher = {MIT press}
        }
    """
    def _fit(self, train_data):
        inputs, labels = train_data
        Z = inputs[np.random.permutation(inputs.shape[0])[:1000]]
        self.model = gpflow.models.GPRFITC(inputs, labels,
                                           kern=gpflow.kernels.RBF(inputs.shape[-1], ARD=True),
                                           Z=Z)
        self.model.likelihood.variance = labels.var()*0.01
        self.model.build()
        return True

    def _predict(self, test_data):
        return self.model.predict_y(test_data)[0]

