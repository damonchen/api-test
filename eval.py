from base import TestCase, TestSuite
import random
import string
import glob
import os
import threading
import subprocess
import requests

def generate_folder_name():
    random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    return f"test_{random_str}"


def background_run(func, args):
    thread = threading.Thread(target=func, args=args)
    thread.run()

    return thread

    
def evaluate_docker_compose_up(test_case):
    folder_name = generate_folder_name()
    os.makedirs(folder_name, exist_ok=True)
    os.chdir(folder_name)

    with open('./my.cnf', 'w') as fp:
        fp.write(test_case.env.render(test_case.mysql_config))

    with open('./init.sql', 'w') as fp:
        fp.write(test_case.env.render(test_case.init_sql))

    with open('./init-database.sh', 'w') as fp:
        fp.write(test_case.env.render('''#!/usr/bin/env bash
mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < "/docker-entrypoint-initdb.d/init.sql"'''))
        
    with open('./docker-compose.yaml', 'w') as fp:
        fp.write(test_case.env.render(test_case.docker_compose_config))

    p = None
    def run_docker_compose():
        p = subprocess.run(['docker-compose', 'up'])
        return p
    
    def close_docker_compose():
        p.terminate()

    # background running
    thread = background_run(run_docker_compose,[])

    return thread


def evaluate_docker_compose_down(docker_compose_config):
    subprocess.run(['docker-compose', 'down'])


def evaluate_request(request):
    if request.method == 'GET': 
        resp = requests.get(request.url)
    elif request.method == 'POST':
        resp = requests.post(request.url, headers=request.headers, data=request.body)
    elif request.method == 'PUT':
        resp = requests.put(request.url, headers=request.headers, data=request.body)
    elif request.method == 'DELETE':
        resp = requests.delete(request.url)
    return resp

def evaluate_api_running(api_config):
    with open('./api.yaml', 'w') as fp:
        fp.write(api_config)

    p = None
    def run_api():
        p = subprocess.run(['api-service', '-c', './api.yaml'])
        return p
    
    def close_api():
        p.terminate()

    # background running
    thread = background_run(run_api,[])

    return thread


def evaluate_api_down(api_config):
    subprocess.run(['api-service', 'down'])


def evaluate(test_case):
    print(f"test_case: {test_case.title}")
    threads = []
    if test_case.docker_compose_config:
        docker_compose_thread = evaluate_docker_compose_up(test_case)
        threads.append(docker_compose_thread)

        # Wait for docker-compose to start up
        # docker_compose_thread.join()

        # # Run the test case
        # result = test_case.run()

        # # Clean up docker compose
        # subprocess.run(['docker-compose', 'down'])

        # return result
    if test_case.config:
        api_running = evaluate_api_running(test_case.config)
        threads.append(api_running)

    if test_case.main_config:
        pass

    if test_case.env:
        pass

    # run test case
    if test_case.request:
        resp = evaluate_request(test_case.request)
    if test_case.response_body:
        expected_resp = test_case.response
        if resp.status_code != expected_resp.status_code:
            return False
        if resp.body != expected_resp.body:
            return False

    for thread in threads:
        thread.join()

    return True

def parse_test_from_file(file_path):
    with open(file_path, 'r') as fp:
        test_content = fp.read()
    return parse_test(test_content)

def run_test_from_file(file_path):
    test_case = parse_test_from_file(file_path)
    return evaluate(test_case)


def parse_test_suite_from_dir(dir_path):
    test_suite = TestSuite()
    files = glob.glob(os.path.join(dir_path, "*.t"))
    for file in files:
        test_suite.add_test(parse_test_from_file(os.path.join(dir_path, file)))
    return test_suite

def test_suite_from_dir(dir_path):
    test_suite = parse_test_suite_from_dir(dir_path)
    for test_case in test_suite.tests:
        evaluate(test_case)

if __name__ == '__main__':
    from parser import parse_test, print_test_case
    test_content1 = """=== TEST 1: hello, world
    This is just a simple demonstration
--- env
    MY_TEST = "hello, world!"
    MYSQL_ROOT_PASSWORD = "root"
    MYSQL_USER = "api_test"
    MYSQL_PASSWORD = "api_test"
    MYSQL_DATABASE = "api_test"
--- config
    location = /t {
        echo "hello, world!";
    }

--- mysql_config
[mysqld]
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci

[client]
default-character-set=utf8mb4

--- init_sql
CREATE DATABASE ${MYSQL_DATABASE};
CREATE USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${MYSQL_DATABASE}.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;

--- docker_compose_config 
version : '3'
services:
db:
    image: mysql:8.0
    ports:
    - "3306:3306"
    command: mysqld --default-authentication-plugin=mysql_native_password --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    environment:
    - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
    - MYSQL_DATABASE=${MYSQL_DATABASE}
    - MYSQL_USER=${MYSQL_USER}
    - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    - MYSQL_ALLOW_EMPTY_PASSWORD=yes
    - MYSQL_PORT=3306
    volumes:
    # - './docker/db/data:/var/lib/mysql'
    - './my.cnf:/etc/mysql/conf.d/my.cnf'
    - './init.sql:/docker-entrypoint-initdb.d/init.sql'
    restart: always

--- request
    GET /t
    
--- response_body
    hello, world!

--- error_code: 200"""

    test_case = parse_test(test_content1)
    # print_test_case(test_case)
    
    print(evaluate(test_case))