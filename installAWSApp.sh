#!/bin/bash


#The following commands were used to template-ize the previously configured app.
#find . -name "*.conf" -exec sed -i s/XXXXXXXXXXX/###ACCOUNTID###/g {} +
#find . -name "*.conf" -exec sed -i s/mgmt-01-monitoring/###ROLEID###/g {} +

echo "Getting Account ID"
account_id=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | grep -oP '(?<="accountId" : ")[^"]*(?=")')
if [ $account_id != '' ]
then
  echo "Found Account ID:" $account_id
else
  echo "Error - Could not detect account id"
  exit 1
fi

echo "Getting Role ID"

role_id=$(curl -s http://169.254.169.254/latest/meta-data/iam/info | grep -oP '(?<="InstanceProfileArn" : "arn:aws:iam::[0-9]{12}:instance-profile\/)[^"]+')
if [ $role_id != '' ]
then
  echo "Found Role ID:" $role_id
else
  echo "Error - Could not detect role id"
  exit 1
fi

echo "Applying gathered info to Splunk AWS TA Config"
find . -name "*.conf" -exec sed -i s/###ACCOUNTID###/$account_id/g {} +
find . -name "*.conf" -exec sed -i s/###ROLEID###/$role_id/g {} +
find . -name "*.meta" -exec sed -i s/###ACCOUNTID###/$account_id/g {} +
find . -name "*.meta" -exec sed -i s/###ROLEID###/$role_id/g {} +
echo "Done."

echo "Copying Splunk apps to Splunk app directory"
cp -r /home/splunk/AWSApps/* /opt/splunk/etc/apps/

echo "Restarting Splunk"
/opt/splunk/bin/splunk restart

echo "Finished installing AWS Apps"
