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
# import fileinput
import grp
import json
# import kazoo
# import kazoo.exceptions
# import kazoo.handlers.threading
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
# from kazoo.client import KazooClient
# from kazoo.handlers.threading import KazooTimeoutError
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

    logger.debug('kafka is running')


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