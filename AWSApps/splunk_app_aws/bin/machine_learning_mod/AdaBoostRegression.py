__author__ = 'pezhang'

import numpy as np
import recommendation_task.recommendation_consts as const


class AdaBoostRegression(object):
    def __init__(self, regression):
        self.regression = regression
        self.regression.n_estimators = len(regression.estimators_)
        self.remove_unused_estimator_errors_weights()
        self.sample_weights = None

    def predict(self, x):
        prediction = np.zeros(len(x), dtype=float)
        estimator_weights_sum = self.regression.estimator_weights_.sum()
        for i in range(self.regression.n_estimators):
            prediction += self.regression.estimator_weights_[i] * (self.regression.estimators_[i].predict(x))/estimator_weights_sum
        return prediction

    def add_estimator(self, x, y):
        start_iboost = self.regression.n_estimators
        self.regression.n_estimators = const.MAX_ADD_ESTIMATORS
        for iboost in range(start_iboost, const.MAX_ADD_ESTIMATORS):
            sample_weight, estimator_weight, estimator_error = self.regression._boost(iboost,
                                                                                      x,
                                                                                      y,
                                                                                      self.sample_weights)
            # Discard current estimator
            if sample_weight is None:
                sample_weight_reset = True
                # current estimator error bigger than 0.5, worse than random guess
                break
            else:
                # Stop if error is zero
                self.regression.estimator_errors_ = np.append(self.regression.estimator_errors_, estimator_error)
                self.regression.estimator_weights_ = np.append(self.regression.estimator_weights_, estimator_weight)

                if estimator_error == 0:
                    # estimator error is 0
                    break

                sample_weight_sum = np.sum(sample_weight)

                # Stop if the sum of sample weights has become non-positive
                if sample_weight_sum <= 0:
                    # sample weight sum smaller than zero
                    break

                if iboost < const.MAX_ADD_ESTIMATORS - 1:
                    # Normalize
                    self.sample_weights = sample_weight / sample_weight_sum

        self.regression.n_estimators = len(self.regression.estimators_)

    def remove_bad_estimators(self, x, y):
        if self.regression.n_estimators * const.MIN_ESTIMATOR_PRESERVE_PERCENTAGE <= const.MIN_ESTIMATORS:
            return
        sorted_idx = np.argsort(self.regression.estimator_errors_)
        estimator_errors_copy = np.copy(self.regression.estimator_errors_)
        estimator_errors_copy.sort()
        cut_off = min(const.MAX_ESTIMATORS, self.regression.n_estimators) * const.MIN_ESTIMATOR_PRESERVE_PERCENTAGE
        if np.max(estimator_errors_copy) > const.MAX_ESTIMATOR_ERROR:
            cut_off = min(np.argmax(estimator_errors_copy > const.MAX_ESTIMATOR_ERROR), cut_off)
        cut_off = int(cut_off)
        remove_indexes = [sorted_idx[i] for i in range(cut_off, self.regression.n_estimators)]
        for index in sorted(remove_indexes, reverse=True):
            del self.regression.estimators_[index]
        self.regression.estimator_errors_ = np.delete(self.regression.estimator_errors_, remove_indexes)
        self.regression.estimator_weights_ = np.delete(self.regression.estimator_weights_, remove_indexes)
        self.regression.n_estimators -= len(remove_indexes)

    def remove_unused_estimator_errors_weights(self):
        index = 0
        while index < len(self.regression.estimator_errors_):
            if self.regression.estimator_weights_[index] != 0:
                index += 1
            else:
                self.regression.estimator_weights_ = np.delete(self.regression.estimator_weights_, [index])
                self.regression.estimator_errors_ = np.delete(self.regression.estimator_errors_, [index])

    def update_sample_weights(self, x, y):
        need_add = True
        self.sample_weights = np.ones(len(x), dtype=float)
        self.sample_weights /= len(x)

        error_vect_sum = np.zeros(len(x))
        for i in range(self.regression.n_estimators):
            error_vect = np.abs(self.regression.estimators_[i].predict(x) - y)
            error_max = error_vect.sum()
            if error_max != 0:
                error_vect /= error_max
            error_vect_sum += error_vect
            if error_vect.sum() < const.MIN_ESTIMATOR_ERROR:
                need_add = False
        if self.regression.n_estimators != 0:
            error_vect_sum /= self.regression.n_estimators
        self.sample_weights *= np.power(np.e, error_vect_sum)
        self.sample_weights /= sum(self.sample_weights)
        return need_add

    def update(self, x, y):
        need_add = self.update_sample_weights(x, y)
        if need_add and len(x) >= const.TRUST_FEEDBACK_CNT:
            self.add_estimator(x, y)
        self.remove_bad_estimators(x, y)