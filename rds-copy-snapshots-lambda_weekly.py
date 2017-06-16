from __future__ import print_function
from dateutil import parser, relativedelta
from boto3 import client

# List of database identifiers, or "all" for all databases
# eg. ["db-name1", "db-name2"] or ["all"]
INSTANCES = ["db-name-01"]

# The number of weeks to keep ONE snapshot per week
WEEKS = 14

# three character prefix for snapshot naming : "mo-" = monthly "wk-" = weekly
SNAP_NAME_PREFX = "wk-"

# AWS region in which the db instances exist
REGION = "us-east-1"


def copy_snapshots(rds, snaps, dbarn):
    newest = snaps[-1]
    response = rds.list_tags_for_resource(ResourceName=dbarn)
    rdstags = response['TagList']
    rdstags.append({'Key': 'backup_type', 'Value': 'weekly'})
    rds.copy_db_snapshot(
        SourceDBSnapshotIdentifier=newest['DBSnapshotIdentifier'],
        TargetDBSnapshotIdentifier=SNAP_NAME_PREFX + newest['DBSnapshotIdentifier'][4:],
        Tags=rdstags)
    print("Snapshot {} copied to {}".format(
          newest['DBSnapshotIdentifier'],
          SNAP_NAME_PREFX + newest['DBSnapshotIdentifier'][4:])
          )


def purge_snapshots(rds, id, snaps, counts):
    newest = snaps[-1]
    prev_start_date = None
    delete_count = 0
    keep_count = 0

    print("---- RESULTS FOR {} ({} snapshots) ----".format(id, len(snaps)))

    for snap in snaps:
        snap_date = snap['SnapshotCreateTime']
        snap_age = NOW - snap_date
        # Weekly
        type_str = "week"
        start_date_str = snap_date.strftime("%Y-%m-%d")
        if (start_date_str != prev_start_date and
                snap_date > DELETE_BEFORE_DATE):
            # Keep it
            prev_start_date = start_date_str
            print("Keeping {}: {}, {} days old - {} of {}".format(
                  snap['DBSnapshotIdentifier'], snap_date, snap_age.days,
                  type_str, start_date_str)
                  )
            keep_count += 1
        else:
            # Never delete the newest snapshot
            if snap['DBSnapshotIdentifier'] == newest['DBSnapshotIdentifier']:
                print(("Keeping {}: {}, {} hours old - will never"
                      " delete newest snapshot").format(
                      snap['DBSnapshotIdentifier'], snap_date,
                      snap_age.seconds/3600)
                      )
                keep_count += 1
            else:
                # Delete it
                print("- Deleting{} {}: {}, {} days old".format(
                      NOT_REALLY_STR, snap['DBSnapshotIdentifier'],
                      snap_date, snap_age.days)
                      )
                if NOOP is False:
                    rds.delete_db_snapshot(
                        DBSnapshotIdentifier=snap['DBSnapshotIdentifier']
                        )
                delete_count += 1
    counts[id] = [delete_count, keep_count]


def get_snaps_filtered(rds, instance, snap_type):
    str_status_type = "avail"
    if len(INSTANCES) == INSTANCES.count("all"):
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type)['DBSnapshots']
    else:
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type,
                    DBInstanceIdentifier=instance)['DBSnapshots']
    snapshots = filter(lambda x: x['Status'].startswith(str_status_type), snapshots)  # filter snaps based on status=available - returning only snaps that not creating or deleting
    snapshots = filter(lambda x: x['DBSnapshotIdentifier'].startswith(SNAP_NAME_PREFX), snapshots)  # filter the snapshots based on the the first letters of the DBSnapshotIdentifier
    return sorted(snapshots, key=lambda x: x['SnapshotCreateTime'])


def get_snaps(rds, instance, snap_type):
    if len(INSTANCES) == INSTANCES.count("all"):
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type)['DBSnapshots']
    else:
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type,
                    DBInstanceIdentifier=instance)['DBSnapshots']
    snapshots = filter(lambda x: x['Status'].startswith('avail'), snapshots)  # filter snaps based on status=available - returning only snaps that not creating or deleting
    return sorted(snapshots, key=lambda x: x['SnapshotCreateTime'])


def print_summary(counts):
    print("\nSUMMARY:\n")
    for id, (deleted, kept) in counts.iteritems():
        print("{}:".format(id))
        print("  deleted: {}{}".format(
              deleted, NOT_REALLY_STR if deleted > 0 else "")
              )
        print("  kept:    {}".format(kept))
        print("-------------------------------------------\n")


def main(event, context):
    global NOW
    global DELETE_BEFORE_DATE
    global NOOP
    global NOT_REALLY_STR

    NOW = parser.parse(event['time'])
    DELETE_BEFORE_DATE = (NOW - relativedelta.relativedelta(weeks=WEEKS))
    NOOP = event['noop'] if 'noop' in event else False
    NOT_REALLY_STR = " (not really)" if NOOP is not False else ""
    rds = client("rds", region_name=REGION)

    if INSTANCES:
        for instance in INSTANCES:
            instance_counts = {}
            snapshots_auto = get_snaps(rds, instance, 'automated')
            if snapshots_auto:
                print("Processing Snapshots for instance: {} ".format(instance))
                response = rds.describe_db_instances(DBInstanceIdentifier=instance)
                dbins = response['DBInstances']
                dbin = dbins[0]
                dbarn = dbin['DBInstanceArn']
                print("The instance arn is:  {} ".format(dbarn))
                copy_snapshots(rds, snapshots_auto, dbarn)
            else:
                print("No auto snapshots found for instance: {}".format(
                      instance)
                      )
            snapshots_manual = get_snaps_filtered(rds, instance, 'manual')
            if snapshots_manual:
                print("\nNumber of Weekly Snaps to retain = ",WEEKS," \n")
                print("Script start time is: ",NOW," \n")
                print("Snapshots will be deleted prior to: ",DELETE_BEFORE_DATE," \n")
                purge_snapshots(rds, instance,
                                snapshots_manual, instance_counts)
                print_summary(instance_counts)
            else:
                print("No manual snapshots found for instance: {}".format(
                      instance)
                      )
    else:
        print("You must populate the INSTANCES variable.")
