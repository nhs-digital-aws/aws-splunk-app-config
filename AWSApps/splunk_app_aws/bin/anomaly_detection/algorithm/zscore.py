__author__ = 'pezhang'

import algorithm_const as const
import math


class ZScore(object):

    def __init__(self, strictness):
        self.strictness = const.STRICTNESS_MAP[strictness]

    def get_train_count(self):
        return const.TRAIN_COUNT

    def cal_median(self, data):
        if type(data) is not list or len(data) == 0:
            return 0

        data_copy = data[:]
        data_copy.sort()
        median = data_copy[len(data) / 2]
        if len(data) % 2 == 0:
            median += data_copy[len(data) / 2 - 1]
            median /= 2.0
        return median

    def cal_mean(self, data):
        if type(data) is not list:
            return 0

        return sum(data) / max(float(len(data)), 1.0)

    def cal_stddev(self, data, mean):
        if type(data) is not list:
            return 0

        variance = sum([math.pow((value - mean), 2) for value in data]) / max(float(len(data)), 1.0)
        return math.pow(variance, 0.5)

    def anomaly_detection(self, data):
        """Anomaly detection using normal distribution.
            Args:
                data: data to detect anomaly.
            Returns:
                outlier: outlier index array.
                severity: corresponding severity array.
        """
        outlier = []
        severity = []
        if type(data) is not list or len(data) < const.TRAIN_COUNT:
            return outlier, severity

        for i in xrange(const.TRAIN_COUNT, len(data)):
            train_array = data[i - const.TRAIN_COUNT: i]
            mean = self.cal_mean(train_array)
            std = self.cal_stddev(train_array, mean)
            median = self.cal_median(train_array)

            if data[i] > median + self.strictness * std:
                outlier.append(i)
                deviation = round((data[i] - median) / max(std, 1.0))
                severity.append(const.get_severity(deviation))
        return outlier, severity
