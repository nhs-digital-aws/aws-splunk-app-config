# This file contains constants which are used in insights algorithms in AWS App.

[ec2]
ri_recommendation_minimum_sample_days = <int>
* Rerserved Instance Planner dashboard requires at least "ri_recommendation_minimum_sample_days" days of data to be reliable

instance_minimum_sample_days = <int>
* EC2 insights dashboard requires at least "instance_minimum_sample_days" days of data to be reliable

instance_upgrade_threshold_score = <float>
* Recommend "Upgrade" action if instance's score is greater than "instance_upgrade_threshold_score"

instance_downgrade_threshold_score = <float>
* Recommend "Downgrade" action if instance's score is smaller than "instance_downgrade_threshold_score"

instance_threshold_percent = <float>
* Recommend "Upgrade/Downgrade" action if instance's score is in the top "instance_threshold_percent"
