import random
import string
import glob
import os
import subprocess
import requests
import shutil
from base import TestCase, TestSuite
from parser import parse_test


def generate_folder_name():
    random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    return f"test_{random_str}"

class ControlledProcess(object):

    def __init__(self, command, args, cwd):
        self.command = command
        self.args = args
        self.cwd = cwd
        self.child_pid = None

    def run(self):
        # Fork a child process
        pid = os.fork()
        if pid == 0:
            # In child process
            os.chdir(self.cwd)
            command = shutil.which(self.command)
            print('----', command, self.args)
            os.execv(command, [command] + self.args)
        else:
            # In parent process, store child pid
            self.child_pid = pid
            return pid

    def terminate(self):
        """Kill the child process"""
        if hasattr(self, 'child_pid'):
            try:
                os.kill(self.child_pid, 9)  # SIGKILL
            except OSError:
                # Process may already be dead
                pass

    def join(self):
        if hasattr(self, 'child_pid'):
            os.waitpid(self.child_pid, 0)

    def is_alive(self):
        return os.path.exists(f"/proc/{self.child_pid}")



# class BackgroundProcess(object):
#     def __init__(self, command, args, cwd, close_func=None):
#         self.command = command
#         self.args = args
#         self.cwd = cwd
#         self.close_func = close_func
#         self.proc = None
#         self.thread = threading.Thread(target=self._run, args=[])
#         self.thread.run()

#     def _run(self):
#         bash_filename = generate_folder_name()
#         filename = os.path.join(self.cwd, '%s.sh' %bash_filename) 
#         with open(filename, 'w') as fp:
#             fp.write('#!/usr/bin/env bash\n')
#             fp.write('%s %s\n' %(self.command, ' '.join(self.args)))
#         os.chmod(filename, 0o755)

#         proc = subprocess.Popen([filename], shell=True, cwd=self.cwd)
#         self.proc = proc
#         return proc

#     def join(self):
#         self.thread.join()
    
#     def terminate(self):
#         if self.close_func is not None:
#             self.close_func()

#         self.proc.kill()
#         self.thread.terminate()
    
#     def is_alive(self):
#         return self.thread.is_alive()
    
def evaluate_docker_compose_up(test_case, cwd):

    with open('./my.cnf', 'w') as fp:
        fp.write(test_case.env.render(test_case.mysql_config))

    with open('./init.sql', 'w') as fp:
        fp.write(test_case.env.render(test_case.init_sql))

    with open('./init-database.sh', 'w') as fp:
        fp.write(test_case.env.render('''#!/usr/bin/env bash
mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < "/docker-entrypoint-initdb.d/init.sql"'''))
        
    with open('./docker-compose.yaml', 'w') as fp:
        fp.write(test_case.env.render(test_case.docker_compose_config))

    process = ControlledProcess('docker', ['compose', 'up'], cwd)
    process.run()

    # 需要等待进程完全启动后返回

    with open('./mysql-wait-until.sh', 'w') as fp:
        fp.write('''
while ! mysqladmin ping -h"127.0.0.1" --silent; do
    sleep 1
done
''')

    process2 = ControlledProcess('bash', ['./mysql-wait-until.sh'], cwd)
    process2.run()
    process2.join()

    ControlledProcess('docker-compose', ['exec', 'db', 'bash', '-c', "./docker-entrypoint-initdb.d/init-database.sh"], cwd).run()

    def cleanup():
        ControlledProcess('docker', ['compose', 'down'], cwd).run()
        process.terminate()
        process2.terminate()

    return process, cleanup


def evaluate_request(request, prefix, cwd):
    real_url = prefix + request.url
    if request.method == 'GET': 
        resp = requests.get(real_url)
    elif request.method == 'POST':
        resp = requests.post(real_url, headers=request.headers, data=request.body)
    elif request.method == 'PUT':
        resp = requests.put(real_url, headers=request.headers, data=request.body)
    elif request.method == 'DELETE':
        resp = requests.delete(real_url)
    return resp

def evaluate_api_running(test_case, cwd):
    api_config = test_case.config
    with open('./api.yaml', 'w') as fp:
        fp.write(api_config)

    web = test_case.web

    command = test_case.env.render(web.command)
    args = [test_case.env.render(arg) for arg in web.args]

    process = ControlledProcess(command, args, cwd)
    process.run()

    def cleanup():
        process.terminate()

    return process, cleanup


def evaluate_api_down(api_config):
    subprocess.run(['api-service', 'down'])


def evaluate(test_case, directory, prefix):
    print(f"test_case: {test_case.title}")
    processes = []

    folder_name = generate_folder_name()
    os.makedirs(folder_name, exist_ok=True)
    os.chdir(folder_name)

    cwd = os.getcwd()

    cleanup_funcs = []
    if test_case.docker_compose_config:
        docker_compose_process, cleanup = evaluate_docker_compose_up(test_case, cwd)
        processes.append(docker_compose_process)
        cleanup_funcs.append(cleanup)

        # Wait for docker-compose to start up
        # docker_compose_thread.join()

        # # Run the test case
        # result = test_case.run()

        # # Clean up docker compose
        # subprocess.run(['docker-compose', 'down'])
 
        # return result
    if test_case.config:
        api_running_process, cleanup = evaluate_api_running(test_case, cwd)
        processes.append(api_running_process)
        cleanup_funcs.append(cleanup)

    # run test case
    if test_case.request:
        resp = evaluate_request(test_case.request, prefix, cwd)
    
    if test_case.response_body:
        expected_resp = test_case.response
        if resp.status_code != expected_resp.status_code:
            return False
        if resp.body != expected_resp.body:
            return False

    # for thread in processes:
    #     thread.join()

    # for thread in processes:
    #     thread.terminate()

    return processes, cleanup_funcs

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
