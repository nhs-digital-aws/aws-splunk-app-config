define([
    'underscore',
    'splunkjs/mvc',
    'app/utils/LookupUtil',
    'app/views/dashboard/DataModelChecker',
    'app/views/dashboard/common',
    'splunkjs/mvc/simplexml/ready!'
], function(_, mvc, LookupUtil, DataModelChecker) {
    LookupUtil.generateAccountName();
    DataModelChecker.check('Instance_Hour');
});