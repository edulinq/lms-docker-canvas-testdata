#!/usr/bin/env python3

"""
Verify test data using the LMS Toolkit.
"""

import argparse
import os
import sys

import edq.util.dirent
import lms.procedure.verify_test_data

THIS_DIR: str = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TEST_DATA_DIR: str = os.path.join(THIS_DIR, 'testdata', 'http')

DEFAULT_CONTAINER_NAME: str = 'canvas-verify-test-data'
DEFAULT_IMAGE_NAME: str = 'ghcr.io/edulinq/lms-docker-canvas-testdata'
DEFAULT_PORT: int = 3000

def run_cli(args):
    args = {
        'server': f"127.0.0.1:{args.port}",
        'backend_type': 'canvas',
        'server_start_command': f"docker run --rm -p {args.port}:3000 --name '{args.container_name}' '{args.image_name}'",
        'server_stop_command': f"docker kill '{args.container_name}'",
        'test_data_dir': args.test_data_dir,
    }

    lms.procedure.verify_test_data.run(args)

    return 0

def main():
    return run_cli(_get_parser().parse_args())

def _get_parser():
    parser = argparse.ArgumentParser(description = __doc__.strip())

    parser.add_argument('--test-data-dir', dest = 'test_data_dir',
        action = 'store', type = str, default = TEST_DATA_DIR,
        help = 'The directory with test data to verify (default: %(default)s).')

    parser.add_argument('--container-name', dest = 'container_name',
        action = 'store', type = str, default = DEFAULT_CONTAINER_NAME,
        help = 'The name for the container(s) that will be created and run (default: %(default)s).')

    parser.add_argument('--image-name', dest = 'image_name',
        action = 'store', type = str, default = DEFAULT_IMAGE_NAME,
        help = 'The name of the image to run (default: %(default)s).')

    parser.add_argument('--port', dest = 'port',
        action = 'store', type = int, default = DEFAULT_PORT,
        help = 'The name of the image to run (default: %(default)s).')

    return parser

if (__name__ == '__main__'):
    sys.exit(main())
