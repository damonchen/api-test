#!/usr/bin/env python3

import os
import sys
import glob
import signal
import subprocess
import click
from base import TestSuite, TestCase
from evaluate import parse_test_from_file, evaluate

def scan_test_files(directory):
    """Scan for .t test files in the specified directory's 't' subdirectory"""
    test_dir = os.path.join(directory, 't')
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        return []
    return glob.glob(os.path.join(test_dir, '*.t'))

def cleanup(processes):
    """Cleanup function to terminate processes and remove config files"""
    for process in processes:
        try:
            process.terminate()
            process.wait()
        except:
            pass

@click.command()
@click.option('--directory', '-d', default='.', help='directory of running test')
@click.option('--prefix', '-p', default='http://127.0.0.1', help='prefix of the api test')
def main(directory, prefix):
    # List to track processes and resources that need cleanup
    processes = []

    # Set up signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\nCleaning up and exiting...")
        cleanup(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    test_files = scan_test_files(directory)
    if not test_files:
        print("No test files found")
        sys.exit(1)

    def wait_thread_stop(threads):
        for thread in threads:
            thread.join()

    test_suite = TestSuite()
    
    try:
        # Process each test file
        for test_file in test_files:
            print(f"\nProcessing test file: {test_file}")
            # TODO: Parse test file and create TestCase objects
            # Add test cases to test_suite
            test_case = parse_test_from_file(test_file)
            test_suite.add_test(test_case)

        # Execute tests
        for test in test_suite.tests:
            print(f"\nExecuting test: {test.title}")
            # TODO: Execute test case and validate results
            processes, cleanup_funcs = evaluate(test, directory, prefix)

            # for cleanup in cleanup_funcs:
            #     cleanup()

            # wait_thread_stop(threads)

    except Exception as e:
        print(f"Error during test execution: {str(e)}")
        raise
    finally:
        # Cleanup
        cleanup(processes)

if __name__ == "__main__":
    main()
