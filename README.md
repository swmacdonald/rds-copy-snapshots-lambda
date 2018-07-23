# rds-copy-snapshots-lambda
Makes a copy of the most recent auto snapshot and deletes ones older than the set retention period.

There are three versions of the script: a weekly, monthly , and an aurora cluster monthly version.
You can choose to use only weekly, monthly, cluster or all of them as you see fit.

Weekly and Monthly Snapshots are named and tagged differently to allow for filtering by type as well as to prevent inadvertent deletion.

## Usage
This python script is a meant to be run as a scheduled AWS Lamdba function. You should have auto snapshots enabled on your RDS instances and this script will copy an auto snapshot so that it will not be deleted.  You will need to configure the following variables at the top of the scripts:

INSTANCES - List of database identifiers, or "all" for all databases
eg. ["db-name1", "db-name2"] or ["all"]

MONTHS or WEEKS - The number of months/weeks to retain snapshots. (e.g the retention period)

SNAP_NAME_PREFX - The text prefix to use for snapshot names. - e.g. "wk-" for weekly or "mo-" for monthly snaps.

REGION - AWS region in which the db instances exist
eg. "us-east-1"

## Configure Lambda function
### IAM Role Policy
Go to the IAM service in the AWS Management console. Click on Roles and click the Create Role button. Choose Lambda and click next. On the Attach permissions policies page, don't check any boxes and just click Next Step. Name the role rds-copy-snapshots-role and click Create role. Click on the newly created role and click where it says Add inline policy. Switch to JSON tab. Copy the contents of the iam_role_policy.json file and paste it in the Policy Document box. Name the policy rds-copy-snapshots-policy and click Create policy.

### Create Lambda function
#### Configure function
Go to the Lambda service in the AWS Management console. Create a new function and in the 'Author from Scratch' section fill in the following:

* Name: rds-copy-snapshots-TYPE - e.g. rds-copy-snapshots-weekly
* Runtime: Python 2.7
* Role: rds-copy-snapshots-role

Click 'Create function'. Then on the next pagefill in the following details:
* Description: An AWS Lambda function that makes a copy of the most recent auto snapshot and deletes ones older than a set number of [months/weeks]
* Code box: paste the contents of the rds-copy-snapshots-lambda-<BACKUPTYPE>.py file
* Handler: lambda_function.main
* Memory: 128
* Timeout: 10 sec
In the Code tab, configure the variables at the top of the script to your desired configuration. Click Save.

#### Configure Triggers
In the left navigator of Designer, at the top, choose CloudWatch Events and fill in the following details in Configure triggers:
* Rule: Create a new rule
* Rule name: rds-copy-snapshots-rule
* Description: Run script [monthly/weekly]
* Rule Type: Schedule expression
* Schedule Expression (Monthly): `cron(30 11 1 * ? *)`  = Your function will run on the first day of every month at 11:30 UTC.
	or
* Schedule Expression (Weekly):	 `cron(40 09 ? * SUN *)` = Your function will run on the Sunday every week at 09:40 UTC.
* Check that Enable trigger is checked
* Click Add.

You should change the time to be after your backup window configured on your db instances.

#### Test function
You can test the function from the Lambda console. Click the Actions button and select Configure test event. Choose Scheduled Event from the drop down.  Configure the time of the simulated scheduled event to the current time in UTC.  Add the following parameter to the structure "noop": "True".  This will tell the script to not actually delete any snapshots, but to print that it would have. Now you can press the Save and Test button and you will see the results of the script running in the Lambda console.

#### CloudWatch logs
You will be able to see the output when the script runs in the CloudWatch logs. Go to the CloudWatch service in the AWS Management console. Click on Logs and you will see the rds-copy-snapshots log group. Click in it and you will see a Log Stream for every time the script is executed which contains all the output of the script. Go back to the Log Group and click the Never Expire link in the Expire Events After column of the log group row. Change the Retention period to what you feel comfortable with.

### CloudWatch Alarms
You can configure a SNS Topic and CloudWatch Alarms to monitor the Lambda functions for errors. Go to the SNS console and create a topic and subscription (email, SMS, etc). Next, go to the CloudWatch console and create an alarm for the Lambda functions error event.  Set the alarm "Whenever" event to =>1 for 1 consectutive periods over a 1 day period. Set the Statistic to standard and sum, and set the notification to the SNS topic ARN.
