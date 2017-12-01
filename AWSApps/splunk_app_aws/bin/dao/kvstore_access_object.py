__author__ = 'frank'

import splunk.rest as rest
import splunk.entity as entity
import json
import utils.app_util as util
import time

logger = util.get_logger()

TIMESTAMP_ATTRIBUTE_NAME = 'timestamp'

CONF_WEB = 'configs/conf-web'

class KVStoreAccessObject(object):
    def __init__(self, collection = None, session_key = None, owner = 'nobody'):
        app_name = util.APP_NAME
        splunkd_uri = entity.getEntity(CONF_WEB, 'settings', sessionKey=session_key, namespace=app_name, owner=owner).get('mgmtHostPort', '127.0.0.1:8089')
        self.url = 'https://%s/servicesNS/nobody/%s/storage/collections/data/%s' % (splunkd_uri, app_name, collection)
        self.session_key = session_key

    def get_item_by_key(self, key):
        """
        Get an item of kvstore.
        :param key: key id in kvstore
        :return: response
        """
        request_url = '%s/%s' % (self.url, key)
        response, content = rest.simpleRequest(request_url, sessionKey = self.session_key, method = 'GET', raiseAllErrors = True)
        return content

    def update_item_by_key(self, key, updated_item):
        """
        Update an item of kvstore.
        :param key: key id in kvstore
        :param updated_item: a json object containing new values of ALL attributes
        :return: response
        """
        json_args = json.dumps(updated_item)
        post_url = '%s/%s' % (self.url, key)
        rest.simpleRequest(post_url, sessionKey = self.session_key, jsonargs = json_args, method = 'POST', raiseAllErrors = True)
        return

    def delete_item_by_key(self, key):
        """
        Delete an item of kvstore.
        :param key: key id in kvstore
        :return: response
        """
        delete_url = '%s/%s' % (self.url, key)
        rest.simpleRequest(delete_url, sessionKey = self.session_key, method = 'DELETE', raiseAllErrors = True)
        return

    def query_items(self, query_conditions={}, sort_by=None, sort_direction=-1, from_timestamp=0):
        """
        Query items in an order from kvstore by query conditions.
        :param query_conditions: a json object containing all the field conditions, {name:value} format
        :param sort_by: field name
        :param sort_direction: an integer, asc: 1, desc: -1
        :param from_timestamp: a timestamp
        :return: response
        """
        if from_timestamp > 0:
            query_conditions[TIMESTAMP_ATTRIBUTE_NAME] = {'$gt': from_timestamp}
        get_args = {'query': json.dumps(query_conditions)}
        if sort_by is not None:
            get_args['sort'] = '%s:%d' % (sort_by, sort_direction)

        response, content = rest.simpleRequest(self.url, sessionKey = self.session_key, method = 'GET', getargs = get_args, raiseAllErrors = True)
        return content

    def delete_items(self):
        """
        Delete all items.
        :return: response
        """
        response, content = rest.simpleRequest(self.url, sessionKey = self.session_key, method = 'DELETE', raiseAllErrors = True)
        return content

    def delete_staled_items(self, expired_time):
        """
        Delete all items by a given expired time
        :param expired_time: a timestamp
        :return:
        """
        timestamp_before = int(time.time()) - expired_time
        delete_args = {'query': '{"%s": {"$lt": %d}}' % (TIMESTAMP_ATTRIBUTE_NAME, timestamp_before)}
        response, content = rest.simpleRequest(self.url, sessionKey = self.session_key, method = 'DELETE', getargs = delete_args, raiseAllErrors = True)
        return content

    def delete_items_by_condition(self, delete_conditions = {}):
        """
        Delete items from kvstore by given conditions
        :param expired_time: a timestamp
        :return:
        """
        delete_args = {'query': json.dumps(delete_conditions)}
        response, content = rest.simpleRequest(self.url, sessionKey = self.session_key, method = 'DELETE', getargs = delete_args, raiseAllErrors = True)
        return content

    def insert_single_item(self, new_item):
        """
        Insert an item into kvstore.
        :param new_item: a json object, indicating the new item
        :return: response (attribute "_key" stands for the key id of new item)
        """
        json_args = json.dumps(new_item)
        response, content = rest.simpleRequest(self.url, sessionKey = self.session_key, jsonargs = json_args, method = 'POST', raiseAllErrors = True)
        return content

    def batch_insert_items(self, new_item_array):
        """
        Batch insert items into kvstore
        :param new_item_array: an array of new items
        :return: response (attribute "_key" stands for the key id of new item)
        """
        post_url = self.url + '/batch_save'
        json_args = json.dumps(new_item_array)
        response, content = rest.simpleRequest(post_url, sessionKey = self.session_key, jsonargs = json_args, method = 'POST', raiseAllErrors = True)
        return content