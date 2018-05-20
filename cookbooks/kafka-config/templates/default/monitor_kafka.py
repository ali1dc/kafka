#!/usr/bin/env python

"""
monitor_kafka.py - CLI to maintain a Kafka launch.

This utility configures, launches, and relaunches
as needed a kafka install
"""

# import dns.query
# import dns.tsigkeyring
# import dns.update
# import dns.reversename
# import dns.resolver
import fileinput
import grp
import json
import kazoo
import kazoo.exceptions
import kazoo.handlers.threading
import logging
import os
import pprint
import pwd
import re
import select
import signal
import sys
import time
import traceback

# from dns.exception import DNSException, SyntaxError
from kazoo.client import KazooClient
from kazoo.handlers.threading import KazooTimeoutError
from subprocess import check_output, Popen, PIPE, STDOUT, call
from os import stat

__all__ = []
__version__ = 0.1
__date__ = '2017-02-01'
__updated__ = '2017-02-01'

DEBUG = 1
TESTRUN = 0
PROFILE = 0
DRYRUN = 0

# How often inner loop runs
INNER_LOOP_INTERVAL = 5

# How often ZK checks occur
ZK_CHECK_INTERVAL = 60

ON_POSIX = 'posix' in sys.builtin_module_names

pp = pprint.PrettyPrinter()
logging.basicConfig()
logger = logging.getLogger('monitor_kafka')
run = True
p_kafka = None
# cluster_env = open('/etc/file_env', 'r').read().strip().lower()
cluster_env = 'ExDataLab'

def handler_stop_signals(signum, frame):
    global run
    global p_kafka
    run = False
    if p_kafka is None:
        return
    try:
        logger.debug('Trying to terminate kafka')
        p_kafka.terminate()
        logger.debug('Termination request complete')
    except OSError:
        logger.error('Failed to terminate kafka')
        pass

def get_instance_private_ip():
    """Return ens3 ip."""
    ens3 = check_output(['ip', '-f', 'inet', '-o', 'addr',
                         'show', 'dev', 'eth0'])
    for ens3_line in ens3.split("\n"):
        ens3_fields = ens3_line.split(" ")
        for c in range(len(ens3_fields)):
            if ens3_fields[c] == 'inet':
                return ens3_fields[c + 1].split('/')[0]


def read_available(proc, retval=''):
    while (select.select([proc.stdout], [], [], 0)[0] != []):
        retval += proc.stdout.read(1)
    return retval


def flush_output(process):
    """Flush output for a process if any is waiting."""
    if process.poll() is None:
        # read available output without blocking
        available = read_available(process)
        if available and (available is not None):
            sys.stdout.write(available)  # avoid writing None
            sys.stdout.flush()  # flush output to avoid loss

def drop_privileges(n_uid=None, n_gid=None,
                    new_mask=033, critical=True, target_dir='.'):
    """
    Drop privileges without forking.

    e.g.:
        http://www.charleshooper.net/blog/dropping-privileges-in-python-for-tornado-apps/
        http://antonym.org/2005/12/dropping-privileges-in-python.html

    if uid and gid are not provided, we try and get the info from stat'ing the
    local directory. this default approach app won't work for most deployments
    outside of your home dir. keep that in mind.

    critical: Specifies the return value if the entry point was not root

    alternative conversion approach:
        n_uid = pwd.getpwuid(stat_info.st_uid)[0]
        n_gui = grp.getgrgid(stat_info.st_gid)[0]

    provide your own logger from the (status, msg) return tuple
    """
    try:

        if os.getuid() != 0:
            if critical:
                msg = 'entry uid was not root but %s' % os.getuid()
                raise Exception(msg)
            else:
                return True, 'no drop needed as not root'

        # get a fix on the new uid and  gid
        stat_info = os.stat(target_dir)
        if n_uid is None:
            running_uid = stat_info.st_uid
            if running_uid == 0:
                msg = 'failure to stat uid from current dir, %s'
                vals = (os.path.realpath(__file__), running_uid)
        else:
            running_uid = pwd.getpwnam(n_uid).pw_uid

        if n_gid is None:
            running_gid = stat_info.st_gid
        else:
            running_gid = grp.getgrnam(n_gid).gr_gid

        # remove group privileges
        os.setgroups([])

        # set new uid, gid
        os.setgid(running_gid)
        os.setuid(running_uid)

        # set umask
        os.umask(new_mask)

        # just making sure nothing slipped
        if os.getuid() == 0:
            raise Exception()

        msg = 'dropped root, %s, to %s, %s, %s'
        vals = (os.getuid(), running_uid, running_gid, new_mask)
        return True, msg % vals

    except Exception, e:
        msg = 'drop_privileges failure of %s, %s, %s: %s'
        vals = (n_uid, n_gid, new_mask, e)
        return False, msg % vals

def exponential_backoff(tries):
    if tries == 5:
        raise
    else:
        delay = 2**tries
        print "Trying again in %s seconds" % delay
        time.sleep(delay)
        tries += 1

    return tries

def get_broker_id_from_zk(zk_hosts):
    zk = KazooClient(hosts=zk_hosts, logger=logger)

    tries = 1
    while True:
        try:
            print "Trying to connect to ZK"
            zk.start()
            zk_broker_ids = zk.get_children('/brokers/ids')
            zk.stop()
            zk.close()

            if cluster_env == 'prod':
                max_broker_count = 5
            else:
                max_broker_count = 3

            set_broker_ids = set(map(int, zk_broker_ids))
            possible_broker_ids = set(range(max_broker_count))
            broker_id = sorted(possible_broker_ids - set_broker_ids)[0]
        except (kazoo.exceptions.NoNodeError):
            broker_id = 0
            logger.debug('no node on ZK - set broker id to 0')
            break;
            # tries = exponential_backoff(tries)
            # continue
        except (kazoo.handlers.threading.KazooTimeoutError):
            logger.debug("Unable to connect to ZK at %s" % zk_hosts)

            tries = exponential_backoff(tries)
            continue

        except IndexError:
            logger.debug('No available broker ids for assignment')

            tries = exponential_backoff(tries)
            continue
        else:
            break

    return broker_id

def get_zk_hosts():

    return '10.100.1.100:2181,10.100.2.100:2181,10.100.3.100:2181'

def get_broker_id():
    """Return broker id for node."""
    logs_metadata = '/kafkalogs/logs/meta.properties'
    broker_id = 0
    zk_hosts = get_zk_hosts()
    # Determine if /kafkalogs/logs/meta.properties exists
    if (os.path.isdir(os.path.dirname(logs_metadata)) and
            os.path.isfile(logs_metadata)):
        # If an existing meta.properties exists, read broker id
        # from it
        with open(logs_metadata, 'r') as f:
            for line in f:
                m = re.match('^broker\.id=(.*)$', line)
                if m is not None:
                    broker_id = m.group(1)
    else:
        # If no meta.properties, use zk to determine appropriate broker id
        broker_id = get_broker_id_from_zk(zk_hosts)

    return str(broker_id)


def get_rack_id(broker_id):
    if int(broker_id) <= 2:
        return broker_id
    else:
        return str(int(broker_id) - 3)

def check_zk(broker_id):
    """Check zookeeper and verify we're in it."""
    zk_hosts = get_zk_hosts()

    zk = KazooClient(hosts=zk_hosts, logger=logger)
    try:
        zk.start()
        zk_broker_ids = zk.get_children('/brokers/ids')
        zk.stop()
        zk.close()

        if broker_id not in zk_broker_ids:
            # broker_id not in list of current brokers,
            # fail check
            logger.debug('check_zk broker_id(%s) not in ids(%s)' %
                         (broker_id, pp.pformat(zk_broker_ids)))
            return False
    except kazoo.exceptions.NoNodeError:
        # /brokers/ids is missing, no kafka is connected
        logger.debug('check_zk /broker/ids not found')
        return False
    except kazoo.handlers.threading.KazooTimeoutError:
        # zk timed out on connection. Unknown source of problem,
        # assume zk is okay
        logger.debug('check_zk kazoo timeout')
        return True

    # Retrieved broker list and this broker_id was in it,
    # check is okay
    return True


def configure_kafka():
    logger.debug('Reconfiguring kafka...')
    """Perform launch-time configuration of Kafka."""
    broker_id = get_broker_id()
    broker_rack = get_rack_id(broker_id)
    private_ip = get_instance_private_ip()
    kafka_config = '/etc/kafka/server.properties'
    # keystore_path = '/opt/kafka/ssl/'
    # keystore_name = '%s-kafka-%s.jks' % (cluster_env, broker_id)

    # if cluster_env == 'preview' or cluster_env == 'prod':
    #     replication_factor = 5
    #     truststore_name = 'vdm_truststore_prod.jks'
    # else:
    #     replication_factor = 3
    #     truststore_name = 'vdm_truststore_nonprod_new.jks'

    # logger.debug('symlinking %s to %s' % (
    #     keystore_path + keystore_name,
    #     keystore_path + 'keystore.jks')
    # )

    # with open('/opt/kafka/config/monitor.json', 'r') as f:
    #     d_config = json.load(f)

    # brokers = kafka_brokers(d_config, '9092')
    zk_hosts = get_zk_hosts()

    # try:
    #     os.symlink(keystore_path + keystore_name, keystore_path + 'keystore.jks')
    # except OSError:
    #     logger.debug('keystore symlink already exists')

    # try:
    #     os.symlink(keystore_path + truststore_name, keystore_path + 'truststore.jks')
    # except OSError:
    #     logger.debug('truststore symlink already exists')

    for line in fileinput.input(kafka_config, inplace=True, backup='.bak'):
        if re.match('^broker\.id=', line) is not None:
            print 'broker.id=%s' % broker_id
            print 'broker.rack=%s' % broker_rack
        elif re.match('^broker\.rack=', line) is not None:
            #remove from file to prevent dups
            line=''
        elif re.match('^advertised\.listeners=', line) is not None:
            print 'advertised.listeners=PLAINTEXT://%s:9092' % private_ip
        elif re.match('^listeners=', line) is not None:
            print 'listeners=PLAINTEXT://%s:9092' % private_ip
        elif re.match('^zookeeper\.connect=', line) is not None:
            print 'zookeeper.connect=%s' % (zk_hosts)
        # elif re.match('^offsets\.topic\.replication\.factor=', line) is not None:
        #     print 'offsets.topic.replication.factor=%d' % replication_factor
        # elif re.match('^default\.replication\.factor=', line) is not None:
        #     print 'default.replication.factor=%d' % replication_factor
        # elif re.match('^confluent\.metrics\.reporter\.bootstrap\.servers=', line) is not None:
        #     print 'confluent.metrics.reporter.bootstrap.servers=%s' % brokers
        else:
            sys.stdout.write(line)
    sys.stdout.flush()
    fileinput.close()

    return broker_id


def run_kafka(broker_id):
  """Run Kafka, looping."""
  global p_kafka
  global logger
  logger.debug('run_kafka')
  drop_privileges('kafka', 'kafka')
  while run:
    logger.debug('run_kafka starting loop')

    command = ['/usr/bin/kafka-server-start',
               '/etc/kafka/server.properties']
    p_kafka = Popen(command,
                    bufsize=1,  # Line buffered
                    close_fds=ON_POSIX,  # close non-std fds on Unix
                    # Redirect stderr to stdout
                    stdout=PIPE, stderr=STDOUT)
    kafka_start = time.time()
    zk_checked = 0

    while run and p_kafka.poll() is None:
      logger.debug('run_kafka inner loop, kafka running')

      if ((time.time() - kafka_start > 30) and
              (time.time() - zk_checked > ZK_CHECK_INTERVAL)):
        logger.debug('Ensuring kafka broker ' + broker_id + ' is in ZK')
        zk_checked = time.time()
        if not check_zk(broker_id):
          logger.error('ZK check failed!')

      flush_output(p_kafka)
      time.sleep(INNER_LOOP_INTERVAL)

    logger.debug('inner loop completed.')
    p_kafka.wait()

def ensure_ebs_volume_is_mounted(volume):
    root = '/kafkalogs'

    if (os.path.ismount(root)):
        logger.debug(root + ' is already mounted.')
    else:
        logger.debug('Mounting EBS volume /dev/xvdg to ' + root)
        return_code = call(['/usr/local/bin/attach_ebs.py', volume, '/dev/xvdg', root])

        if return_code != 0 or not os.path.ismount(root):
            return False

        logger.debug('EBS volume successfully mounted!')
        finish_directory_setup(root)

    return True

def finish_directory_setup(root):
    if not os.path.isdir(root + '/logs'):
        os.mkdir(root + '/logs')

    # UID 9050, GID 1250 is kafka
    owner = stat(root).st_uid
    if owner == 9050:
        print "Owner of %s is kafka. No need to change." % root
    else:
        print "Changing ownership of %s to kafka" % root
        recursive_chown(root, 9050, 1250)

def recursive_chown(path, uid, gid):
    os.chown(path, uid, gid)

    for root, dirs, files in os.walk(path):
        for dirname in dirs:
            os.chown(os.path.join(root, dirname), uid, gid)
        for filename in files:
            os.chown(os.path.join(root, filename), uid, gid)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    log_handler = logging.StreamHandler()
    if DEBUG:
        log_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    log_handler.setFormatter(formatter)

    logger.addHandler(log_handler)

    program_name = os.path.basename(sys.argv[0])

    if (not os.path.exists('/kafkalogs') and
            not os.path.isdir('/kafkalogs')):
        logger.error('Kafka logdir missing')
        return 3

    signal.signal(signal.SIGINT, handler_stop_signals)
    signal.signal(signal.SIGTERM, handler_stop_signals)

    try:
        broker_id = configure_kafka()

        ebs_mounted = False
        while not ebs_mounted:
          ebs_mounted = ensure_ebs_volume_is_mounted('KAFKA-' + broker_id)
          if not ebs_mounted:
              logger.debug('Failed attempting to mount EBS volume. Trying again in 5 seconds...')
              time.sleep(5)
              broker_id = configure_kafka()

        # logger.debug('main() updating DNS')
        # update_dns(broker_id, d_config)
        run_kafka(broker_id) if not DRYRUN else None
        logger.debug('run complete')
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt occurred!')
        handler_stop_signals(None, None)
        return 0
    except Exception, e:
        logger.debug('An Exception occurred!')
        handler_stop_signals(None, None)
        sys.stderr.write(traceback.format_exc())
        if DEBUG or TESTRUN:
            raise(e)
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write("  for help use --help")
        return 2

    logger.debug('End of main() reached. Nothing else to do!')
    handler_stop_signals(None, None)


if __name__ == "__main__":
    if TESTRUN:
        import doctest
        doctest.testmod()
    if PROFILE:
        import cProfile
        import pstats
        profile_filename = 'cfn.helper.AppEnv_profile.txt'
        cProfile.run('main()', profile_filename)
        statsfile = open("profile_stats.txt", "wb")
        p = pstats.Stats(profile_filename, stream=statsfile)
        stats = p.strip_dirs().sort_stats('cumulative')
        stats.print_stats()
        statsfile.close()
        sys.exit(0)
    sys.exit(main())
