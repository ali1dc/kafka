#! /usr/bin/python

from boto import ec2
import boto.utils
import argparse, time, os, json, sys, commands, signal, atexit

def wait_fstab(device_key, expected_status):
    volume_status = 'not present'
    sleep_seconds = 2
    sleep_intervals = 30
    for counter in range(sleep_intervals):
        print 'waiting for fstab - elapsed: %s. status: %s.' % (sleep_seconds * counter, volume_status)
        try:
            os.stat(device_key)
            volume_status = expected_status
        except: OSError
            # mount does not exsit yet
            # try again later
        if volume_status == expected_status:
            break
        time.sleep(sleep_seconds)

    if volume_status != expected_status:
        raise Exception('Unable to get %s status for volume %s' % (expected_status, volume.id))

    print 'volume now in %s state' % expected_status


def wait_volume(conn, volume, expected_status):
    volume_status = 'waiting'
    sleep_seconds = 5
    sleep_intervals = 300
    for counter in range(sleep_intervals):
        print 'waiting for volume - volume_id: %s. elapsed: %s. status: %s.' % (volume.id, sleep_seconds * counter, volume_status)
        conn = ec2.connect_to_region('us-east-1')
        volume_status = conn.get_all_volumes(volume_ids=[volume.id])[0].status
        if volume_status == expected_status:
            break
        time.sleep(sleep_seconds)

    if volume_status != expected_status:
        raise Exception('Unable to get %s status for volume %s' % (expected_status, volume.id))

    print 'volume now in %s state' % expected_status

def wait_snapshot(conn, snapshot, expected_status):
    status = 'waiting'
    sleep_seconds = 5
    sleep_intervals = 300
    for counter in range(sleep_intervals):
        print 'waiting for snapshot - snapshot_id: %s. elapsed: %s. status: %s.' % (snapshot.id, sleep_seconds * counter, status)
        status = conn.get_all_snapshots(snapshot_ids=[snapshot.id])[0].status
        if status == expected_status:
            break
        time.sleep(sleep_seconds)

    if status != expected_status:
        raise Exception('Unable to get %s status for snapshot %s' % (expected_status, volume.id))

    print 'snapshot now in %s state' % expected_status

def check_race_condition(volume):
    if volume.attachment_state() == 'attached':
        print 'Volume %s is already attached which indicates a likely race condition. Exiting attach_ebs.py' % volume.id
        quit()

    if 'Mounting' in volume.tags:
        print 'Volume %s is already being mounted which indicates a likely race condition. Exiting attach_ebs.py' % volume.id
        quit()

def get_volume(conn, region_name, instance_az, tag):
    volumes = conn.get_all_volumes(
            filters={'tag:Name':tag})

    if volumes:
        volume = volumes[0]
        check_race_condition(volume)
        return volume
    else:
        return create_volume(conn, instance_az, tag)

def create_volume(conn, zone, tag):
    volume = conn.create_volume(
            volume_type='st1',
            encrypted='true',
            size='20',
            zone=zone)

    print 'Creating new volume volume_id: %s.' % volume.id
    wait_volume(conn, volume, 'available')
    volume.add_tag('Name', tag)
    return volume

def create_snapshot(conn, volume, description):
    snapshot = conn.create_snapshot(volume.id, description)
    print 'Creating snapshot of volume_id: %s. snapshot_id: %s.' % (volume.id, snapshot.id)
    wait_snapshot(conn, snapshot, 'completed')
    return snapshot

def create_volume_from_snapshot(conn, zone, snapshot, tag):
    volume = conn.create_volume(
            volume_type='st1',
            encrypted='true',
            size='20',
            zone=zone,
            snapshot=snapshot)
    print 'Creating volume volume_id: %s. from snapshot_id: %s.' % (volume.id, snapshot.id)
    wait_volume(conn, volume, 'available')
    volume.add_tag('Name', tag)
    return volume

def attach_volume(conn, instance_id, volume, device_key):
    volume_status = conn.attach_volume(volume.id, instance_id, device_key)
    print 'Attaching volume volume_id: %s.' % volume.id
    wait_volume(conn, volume, 'in-use')
    wait_fstab(device_key, 'present')
    return True

def format_volume(device_key):
    volume_state = commands.getstatusoutput('file -s ' + device_key)
    if device_key + ': data' in volume_state:
        print 'formatting volume'
        commands.getstatusoutput('mkfs -t ext4 ' + device_key)

def mount_volume(device_key, mount_point):
    print 'mounting volume'
    commands.getstatusoutput('mount ' + device_key + ' ' + mount_point)

def delete_volume(conn, volume):
    print 'Deleting volume volume_id: %s.' % volume.id
    conn.delete_volume(volume.id)

def cleanup_tag():
    volume.remove_tag('Mounting')

def handle_sigterm(signal, frame):
    cleanup_tag()
    sys.exit(0)

tag = sys.argv[1]
device_key = sys.argv[2]
mount_point = sys.argv[3]
data = boto.utils.get_instance_identity()
region_name = data['document']['region']
instance_id = data['document']['instanceId']
instance_az = data['document']['availabilityZone']

print 'Running attach_ebs.py - volume_tag: %s. instance_id: %s. region_name: %s. instance_az: %s.' % (tag, instance_id, region_name, instance_az)

conn = ec2.connect_to_region(region_name)
volume = get_volume(conn, region_name, instance_az, tag)
volume.add_tag('Mounting', instance_id)

atexit.register(cleanup_tag)
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

if volume.zone != instance_az:
    snapshot = create_snapshot(conn, volume, tag)
    old_volume = volume
    volume = create_volume_from_snapshot(conn, instance_az, snapshot, tag)
    volume.add_tag('Mounting', instance_id)
    delete_volume(conn, old_volume)

attach_volume(conn, instance_id, volume, device_key)
format_volume(device_key)
mount_volume(device_key, mount_point)

print 'done'
