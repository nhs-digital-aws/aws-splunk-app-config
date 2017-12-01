__author__ = 'pezhang'

import copy
import reserved_instance_const as const
import reserved_instance_helper as helper


class RIUtilizationCalculator(object):
    """
        Calculate RI utilization with giving RI information and instance hour information
    """

    def __init__(self, total_hours, ri_info_search_result, instance_info_search_result, platform, tenancy):
        self.platform = platform
        self.tenancy = tenancy
        # "N/A" means that users didn't configure instance usage input, so instance info is invalid
        self.instance_info_valid = (instance_info_search_result != 'N/A')
        self.purchased_ri_hours = 0
        self.purchased_ri_units = 0
        # if instance info is invalid, then used ri hours/units, purchased instance hours/units
        # and covered instance  hours/units are "N/A", otherwise, they should be zero
        self.used_ri_hours = 0 if self.instance_info_valid else 'N/A'
        self.used_ri_units = 0 if self.instance_info_valid else 'N/A'
        self.purchased_instance_hours = 0 if self.instance_info_valid else 'N/A'
        self.covered_instance_hours = 0 if self.instance_info_valid else 'N/A'  # instance hours could be covered by ri discount
        self.purchased_instance_units = 0 if self.instance_info_valid else 'N/A' # instance units could be covered by ri discount
        self.covered_instance_units = 0 if self.instance_info_valid else 'N/A'
        self.ri_info = {}  # stores ri info (time, placement, instance type and ri count)
        self.instance_info = {}  # stores instance hour info (time, placement, instance type and instance hour)
        self.parse_ri_info(total_hours, ri_info_search_result)
        self.parse_instance_info(instance_info_search_result)

    def parse_ri_info(self, total_hours, ri_info_search_result):
        """
            Calculate total purchased ri hours and parse ri purchased info.

            :param  total_hours: total hours to calculate purchased ri hours
            :param  ri_info_search_result: a search string and its format is "placement,instance type,
                    ri count", placement is "null" for regional ri
        """
        if (not isinstance(ri_info_search_result, basestring)) or len(ri_info_search_result.strip(' ')) <= 0:
            return

        search_result_list = ri_info_search_result.split(' ')
        for search_result in search_result_list:
            if search_result == '':
                continue

            [placement, instance_type, ri_count] = search_result.split(',')
            [family, size] = instance_type.split('.')
            ri_count = float(ri_count)
            if ri_count > 0:
                self.purchased_ri_hours += ri_count * total_hours
                self.purchased_ri_units += ri_count * total_hours * const.NORMAL_FACTOR[size]
                helper.accumulate_to_dict(self.ri_info, [placement, instance_type], ri_count)

    def parse_instance_info(self, instance_info_search_result):
        """
            Parse hourly instance info and update purchased instance hours/units and instance_info dict
            :param  instance_info_search_result: a search string and its format is "time,placement,instance type,
                    used instance hours"
        """
        if not self.instance_info_valid:
            # if invalid instance info, then not need to update
            return
        self.instance_info = {}
        if (not isinstance(instance_info_search_result, basestring)) or len(instance_info_search_result.strip(' ')) <= 0:
            return

        instance_info_search_result_list = instance_info_search_result.split(' ')
        for hourly_instance_info in instance_info_search_result_list:
            if hourly_instance_info == '':
                continue
            [time, placement, instance_type, instance_hour] = hourly_instance_info.split(',')
            [family, size] = instance_type.split('.')
            instance_hour = float(instance_hour)
            if instance_hour > 0:
                self.purchased_instance_hours += instance_hour
                self.purchased_instance_units += instance_hour * const.NORMAL_FACTOR[size]
                helper.accumulate_to_dict(self.instance_info, [time, placement, instance_type], instance_hour)

    def apply_ri_with_az_scope(self, hourly_ri_info, hourly_instance_info):
        """
            Update hourly ri info and instance hour info with applying az RI.
        """
        for placement, hourly_ri_info_by_placement in hourly_ri_info.iteritems():
            if placement == 'null':
                # regional ri
                continue

            for instance_type, ri_hours in hourly_ri_info_by_placement.iteritems():
                [family, size] = instance_type.split('.')
                if (placement in hourly_instance_info) and (instance_type in hourly_instance_info[placement]):
                    used_instance_hours = hourly_instance_info[placement][instance_type]
                    # update used ri hours
                    used_ri = min(ri_hours, used_instance_hours)
                    helper.accumulate_to_dict(hourly_ri_info, [placement, instance_type], -used_ri)
                    helper.accumulate_to_dict(hourly_instance_info, [placement, instance_type], -used_ri)
                    self.used_ri_hours += used_ri
                    self.used_ri_units += used_ri * const.NORMAL_FACTOR[size]
                    self.covered_instance_hours += used_ri
                    self.covered_instance_units += used_ri * const.NORMAL_FACTOR[size]

    def apply_ri_with_region_scope(self, hourly_ri_info, hourly_instance_info):
        """
            Calculate remain ri hours and instances hours with applying regional RI.
        """
        ri_placement = 'null'
        remained_ri_info = {}
        remained_instance_info = {}
        if ri_placement in hourly_ri_info:
            for instance_type in hourly_ri_info[ri_placement].keys():
                [family, size] = instance_type.split('.')
                for instance_placement, hourly_instance_info_by_placement in hourly_instance_info.iteritems():
                    if instance_type in hourly_instance_info_by_placement:
                        used_instance_hours = hourly_instance_info[instance_placement][instance_type]
                        ri_hours = hourly_ri_info[ri_placement][instance_type]
                        if used_instance_hours == 0 or ri_hours == 0:
                            continue
                        # update used ri hours
                        used_ri = min(ri_hours, used_instance_hours)
                        helper.accumulate_to_dict(hourly_ri_info, [ri_placement, instance_type], -used_ri)
                        helper.accumulate_to_dict(hourly_instance_info, [instance_placement, instance_type], -used_ri)
                        self.used_ri_hours += used_ri
                        self.used_ri_units += used_ri * const.NORMAL_FACTOR[size]
                        self.covered_instance_hours += used_ri
                        self.covered_instance_units += used_ri * const.NORMAL_FACTOR[size]

                if hourly_ri_info[ri_placement][instance_type] > 0:
                    helper.accumulate_to_dict(remained_ri_info, [size],
                                              hourly_ri_info[ri_placement][instance_type])

        for instance_placement, hourly_instance_info_by_placement in hourly_instance_info.iteritems():
            for instance_type, remained_instance_hours in hourly_instance_info_by_placement.iteritems():
                if remained_instance_hours > 0:
                    [family, size] = instance_type.split('.')
                    helper.accumulate_to_dict(remained_instance_info, [size], remained_instance_hours)

        return remained_ri_info, remained_instance_info

    def apply_ri_with_size_flexibility(self, remained_ri_info, remained_instance_info):
        """
            Calculate used ri hours considering size flexibility.
        """
        if self.platform != 'Linux/UNIX' or self.tenancy != 'default':
            return

        if len(remained_ri_info.keys()) == 0 or len(remained_instance_info.keys()) == 0:
            return

        remained_instance_unit = 0
        for instance_size, remained_instance_hours in remained_instance_info.iteritems():
            remained_instance_unit += const.NORMAL_FACTOR[instance_size] * remained_instance_hours

        remained_ri_unit = 0
        for ri_size, remained_ri_hours in remained_ri_info.iteritems():
            remained_ri_unit += const.NORMAL_FACTOR[ri_size] * remained_ri_hours

        for ri_size in const.CAL_ORDER:
            if ri_size not in remained_ri_info:
                continue

            remained_ri_hours = remained_ri_info[ri_size]
            if remained_ri_hours == 0:
                continue

            remained_instance_hours = float(remained_instance_unit) / const.NORMAL_FACTOR[ri_size]
            self.used_ri_hours += min(remained_instance_hours, remained_ri_hours)
            self.used_ri_units += min(remained_instance_hours, remained_ri_hours) * const.NORMAL_FACTOR[ri_size]
            if remained_instance_hours <= remained_ri_hours:
                break
            else:
                remained_instance_unit -= const.NORMAL_FACTOR[ri_size] * remained_ri_hours

        for instance_size in const.CAL_ORDER:
            if instance_size not in remained_instance_info:
                continue

            remained_instance_hours = remained_instance_info[instance_size]
            if remained_instance_hours == 0:
                continue

            remained_ri_hours = float(remained_ri_unit) / const.NORMAL_FACTOR[instance_size]
            self.covered_instance_hours += min(remained_ri_hours, remained_instance_hours)
            self.covered_instance_units += min(remained_ri_hours, remained_instance_hours)* const.NORMAL_FACTOR[instance_size]
            if remained_ri_hours <= remained_instance_hours:
                break
            else:
                remained_ri_unit -= const.NORMAL_FACTOR[instance_size] * remained_instance_hours

    def cal_utilization(self):
        if not self.instance_info_valid:
            # if invalid instance info, then not need to calculate ri utilization
            return
        for time, hourly_instance_info in self.instance_info.iteritems():
            hourly_ri_info = copy.deepcopy(self.ri_info)
            # first apply AZ ri, AZ ri cannot be applied to other AZ
            self.apply_ri_with_az_scope(hourly_ri_info, hourly_instance_info)
            # then apply regional ri, it will consider both instance hour not applied with AZ ri and instance hour
            # applied with AZ ri but not fully-cover by AZ ri
            remained_ri_info, remained_instance_info = self.apply_ri_with_region_scope(hourly_ri_info,
                                                                                       hourly_instance_info)
            self.apply_ri_with_size_flexibility(remained_ri_info, remained_instance_info)

    def get_ri_purchased_hours(self):
        return self.purchased_ri_hours

    def get_ri_used_hours(self):
        return self.used_ri_hours

    def get_instance_purchased_hours(self):
        return self.purchased_instance_hours

    def get_instance_covered_hours(self):
        return self.covered_instance_hours

    def get_ri_purchased_units(self):
        return self.purchased_ri_units

    def get_ri_used_units(self):
        return self.used_ri_units

    def get_instance_purchased_units(self):
        return self.purchased_ri_units

    def get_instance_covered_units(self):
        return self.covered_instance_units

    def get_results(self):
        return {
            const.RI_HOURS_PURCHASED: self.purchased_ri_hours, const.RI_HOURS_USED: self.used_ri_hours,
            const.RI_UNITS_PURCHASED: self.purchased_ri_units, const.RI_UNITS_USED: self.used_ri_units,
            const.INSTANCE_HOURS_PURCHASED: self.purchased_instance_hours,
            const.INSTANCE_HOURS_COVERED: self.covered_instance_hours,
            const.INSTANCE_UNITS_PURCHASED: self.purchased_instance_units,
            const.INSTANCE_UNITS_COVERED: self.covered_instance_units
        }