import base64
import time


import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.state_store as ss


class AWSConfigRuleCheckpointer(object):

    def __init__(self, config):
        self._config = config
        self._state_store = ss.get_state_store(
            config, config[tac.app_name], collection_name="aws_config_rule",
            use_kv_store=config.get(tac.use_kv_store))

    def last_evaluation_time(self, region, datainput, rule_name):
        key = base64.b64encode("{}|{}|{}".format(region, datainput, rule_name))
        state = self._state_store.get_state(key)
        if state:
            return state["last_evaluation_time"]

    def set_last_evaluation_time(self, region, datainput, rule_name, etime):
        key = base64.b64encode("{}|{}|{}".format(region, datainput, rule_name))
        state = {
            "last_evaluation_time": etime,
            "timestamp": time.time(),
            "version": 1,
        }
        self._state_store.update_state(key, state)
