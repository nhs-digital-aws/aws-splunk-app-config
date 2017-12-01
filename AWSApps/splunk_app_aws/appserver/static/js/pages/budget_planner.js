define([
    'underscore',
    'splunkjs/mvc',
    'app/views/dashboard/MonthSelector',
    'splunkjs/mvc/tokenforwarder',
    'splunkjs/mvc/searchmanager',
    'splunkjs/mvc/tableview',
    'app/views/dashboard/MessageView',
    'splunkjs/mvc/simpleform/formutils',
    'app/utils/SearchUtil',
    'util/moment',
    'appcss/pages/budget_planner/bootstrap.pcss',
    'app/views/dashboard/common',
    'splunkjs/mvc/simplexml/ready!'
], function(_, mvc, MonthSelector, TokenForwarder, SearchManager, TableView, MessageView, FormUtils, SearchUtil, moment) {
    'use strict';

    let tokenModel = mvc.Components.getInstance('default');
    let submitModel = mvc.Components.getInstance('submitted');

    const DEFAULT_FROM = moment().startOf('year').unix() - moment().startOf('year').zone() * 60;
    const DEFAULT_TO = moment().endOf('year').unix() - moment().endOf('year').zone() * 60;

    $('#submitbudget').parent().parent()
        .css('display', 'inline-block');

    if ($('#budgetText input').length === 1) {
        $('#budgetText input').attr('type', 'number');
    }

    createBaseSearches();

    tokenModel.on('change:source', (source) => {
        submitModel.set('billingAccountId', undefined);
        submitModel.set('form.billingAccountId', undefined);

        MessageView.unsetMessage('source');

        if (source === 'detailed') {
            monthSelector.setDatamodel(true);
        } else {
            monthSelector.setDatamodel(false);
        }

        blockInputs();
    });

    tokenModel.on('change:billingAccountId', (model, value) => {
        blockInputs();

        tokenModel.unset('budget');
        tokenModel.unset('form.budget');

        submitModel.unset('budget');
        submitModel.unset('form.budget');
    });

    new TokenForwarder(['$source$'], '$accountSPL$', function(source) {
        if (source === 'cloudwatch') {
            return ` \
                \`aws-cloudwatch-billing("*", "*")\`
                | stats count by LinkedAccountId
                | \`aws-accountid-to-name\`
            `;
        } else if (source === 'monthly') {
            return '`aws-billing-monthly-accounts` | `aws-accountid-to-name`';
        } else if (source === 'detailed') {
            return `
                | tstats summariesonly=t count FROM datamodel=Detailed_Billing by detailed_billing.LinkedAccountId
                | rename detailed_billing.LinkedAccountId as LinkedAccountId
                | \`aws-accountid-to-name\`
            `;
        }
    });

    let monthSelector = new MonthSelector({
        from: $('#timerange-from'),
        to: $('#timerange-to'),
        fromRange: 24,
        toRange: 24,
        fromCurrentMonth: true
    }).render();

    $('#submitbudget').click(() => {
        let accountSPL = tokenModel.get('accountSPL');
        let source = tokenModel.get('source');
        let billingAccountId = tokenModel.get('billingAccountId');
        let from = monthSelector.model.get('from');
        let to = monthSelector.model.get('to');
        let budget = tokenModel.get('budget');

        if (budget === '') {
            return;
        }

        submitBudget(from, to, budget);

        // Save the budget to lookup table.
        let spl = `${accountSPL}
            | join type=outer LinkedAccountId [inputlookup ${source}_budget]
            | fields LinkedAccountId budget from to
            | eval budget=if(LinkedAccountId=${billingAccountId}, ${budget}, budget)
            | eval from=if(LinkedAccountId=${billingAccountId}, ${from}, from)
            | eval to=if(LinkedAccountId=${billingAccountId}, ${to}, to)
            | outputlookup ${source}_budget
        `;

        SearchUtil.search(spl).then(function(lookupData) {
        }, function(err) {
            console.log(err);
        }).done();
    });

    // from timestamp, in UTC
    // to timestamp, in UTC
    function submitBudget(from, to, budget) {
        tokenModel.set('earliest', from);
        tokenModel.set('latest', to + '.999');

        let source = tokenModel.get('source');
        let billingAccountId = tokenModel.get('billingAccountId');
        let monthlyCostSPL = '';

        if (source === 'cloudwatch') {
            monthlyCostSPL =  `
                \`aws-cloudwatch-billing(${billingAccountId}, "*")\`
                | stats sum(Sum) as sum by _time
                | timechart span=1mon last(sum) as cost
            `;
        } else if (source === 'monthly') {
            monthlyCostSPL = `
                \`aws-billing-monthly-total(${billingAccountId}, "*", ${tokenModel.get('monthSpl')})\`
                | eval _time=strptime(BillingPeriodEndDate,"%Y/%m/%d")
                | timechart sum(TotalCost) as cost span=1mon
            `;
        } else if (source === 'detailed') {
            monthlyCostSPL = `
                | tstats summariesonly=t sum(detailed_billing.BlendedCost) as cost FROM datamodel=Detailed_Billing where detailed_billing.LinkedAccountId=${billingAccountId} by _time span=1mon
                | timechart sum(cost) as cost span=1mon
            `;
        }

        // use timestr to filter out shifted months
        monthlyCostSPL += `
            | eval cost = round(cost, 0)
            | fillnull value=0 cost
            | eval budget = round(${budget}, 0)
            | eval timestr = strftime(_time, "%Y-%m")
            | eval cost=if(_time > now(), "", cost)
            | eval cost=if(timestr=strftime(now(), "%Y-%m"), "", cost)
            | where timestr >= "${$('#timerange-from').find('.select2-container').select2('data').text}" AND timestr <= "${$('#timerange-to').find('.select2-container').select2('data').text}"
            | fields - timestr
        `;


        let fromMoment = moment.unix(from).utc();
        let toMoment = moment.unix(to).utc();
        let nowMoment = moment();

        let monthDiff = (toMoment.year() - fromMoment.year()) * 12 + toMoment.month() - fromMoment.month() + 1;
        let remainMonth = (toMoment.year() - nowMoment.year()) * 12 + toMoment.month() - nowMoment.month() + 1;

        tokenModel.set('months', monthDiff);
        tokenModel.set('remainMonth', remainMonth);
        tokenModel.set('monthlyCostSPL', monthlyCostSPL);

        FormUtils.submitForm({replaceState: true});
    }

    function blockInputs() {
        monthSelector.loading(true);
        $('#submitbudget').addClass('disabled');
        $('#budgetText').find('input').val('');
        $('#budgetText').find('input').prop('disabled', true);
    }

    function unBlockInputs() {
        monthSelector.loading(false);
        $('#submitbudget').removeClass('disabled');
        $('#budgetText').find('input').prop('disabled', false);
    }

    function createTableRenderer() {
        let TableBudgetRenderer = TableView.BaseCellRenderer.extend({
            initialize(options) {
                var self = this;
                this.fields = ['Balance', 'Accumulated Balance'];
                TableView.BaseCellRenderer.prototype.initialize.apply(this, arguments);
            },
            canRender(cell) {
                return this.fields.indexOf(cell.field) > -1;
            },
            render($td, cell) {
                try {
                    let balance = parseFloat(cell.value);
                    if (balance >= 0) {
                        $td.addClass('budget-over');
                    } else {
                        $td.addClass('budget-below');
                    }
                } catch (err) {}

                $td.text(cell.value);

                return this;
            }
        });

        // Table renderers
        let monthTable = mvc.Components.get('monthTable');
        monthTable.getVisualization((tableView) => {
            tableView.table.addCellRenderer(new TableBudgetRenderer());
            tableView.table.render();
        });
    }

    function createBaseSearches() {
        let budgetMgr = new SearchManager({
            id: 'budget',
            search: '$accountSPL$ | join type=outer LinkedAccountId [inputlookup $source$_budget] | search LinkedAccountId=$billingAccountId$',
            earliest_time: '0',
            latest_time: 'now',
            preview: false
        }, {tokens: true});

        budgetMgr.on('search:done', () => {
            let resultsModel = budgetMgr.data('results', {
                output_mode: 'json',
                count: 10000
            });

            resultsModel.once('data', function() {
                let result = resultsModel.data().results;

                if (result && result.length > 0) {
                    let {to, from, budget} = result[0];

                    if (!to || !from) {
                        from = DEFAULT_FROM;
                        to = DEFAULT_TO;
                    }

                    monthSelector.model.set('from', from);
                    monthSelector.model.set('to', to);

                    budget = budget || 10000;

                    tokenModel.set('budget', budget);
                    $('#budgetText').find('input').val(budget);

                    submitBudget(from, to, budget);
                }

                unBlockInputs();
            });
        });

        // _time, cost, budget
        let baseMainMgr = new SearchManager({
            id: 'baseBudget',
            search: '$monthlyCostSPL$',
            earliest_time: '$earliest$',
            latest_time: '$latest$',
        }, {tokens: true});

        let accountSearchMgr = new SearchManager({
            id: 'accountSearch',
            search: '$accountSPL$',
            earliest_time: '0',
            latest_time: 'now'
        }, {tokens: true});

        accountSearchMgr.on('search:done', () => {
            if (accountSearchMgr.get('data').resultCount <= 0) {
                MessageView.setMessage('source', 'There isn\'t any data from this data source. Please configure it via Splunk Add-on for Amazon Web Services or switch to another source.');
            }
        });
    }

    createTableRenderer();
    if (tokenModel.get('source')) {
        tokenModel.trigger('change:source');
    }
});