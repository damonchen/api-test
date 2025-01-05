from base import TestCase, TestRequest, TestResponse, Env

def parse_response_body(content):
    """
    Parse response body content, handling eval expressions
    
    Args:
        content (str): Response body content
        
    Returns:
        tuple: (response_body, eval_expression)
    """
    content = content.strip()
    if content.startswith('eval'):
        # Extract the eval expression
        eval_expr = content.replace('eval', '').strip()
        # Handle quoted strings
        if eval_expr.startswith('"') and eval_expr.endswith('"'):
            eval_expr = eval_expr[1:-1]
        # Parse the multiplication if present
        if 'x' in eval_expr:
            parts = eval_expr.split('x')
            if len(parts) == 2:
                try:
                    char = parts[0].strip()
                    count = int(parts[1].strip())
                    return (char * count, content)
                except ValueError:
                    return (eval_expr, content)
        return (eval_expr, content)
    return (content, None)

def parse_request(content):
    request = TestRequest()
    request.method = content.split(' ')[0]
    request.url = content.split(' ')[1]
    return request


def parse_response(content):
    response = TestResponse()
    response.body = content.split(' ')[0]
    response.status_code = content.split(' ')[1]
    return response


def parse_error_code(content):
    """
    Parse error code, handling chomp modifier
    
    Args:
        content (str): Error code content
        
    Returns:
        tuple: (error_code, is_chomped)
    """
    content = content.strip()
    is_chomped = False
    if 'chomp' in content:
        is_chomped = True
        content = content.replace('chomp', '').strip()
    try:
        return (int(content), is_chomped)
    except ValueError:
        return (None, is_chomped)

def parse_main_config(content):
    lines = content.split('\n')
    env = []
    for line in lines:
        line = line.strip()
        if line.startswith('env'):
            line = line.replace('env', '').strip()
            env.append(line)

    return env

def parse_env(content):
    env = Env()
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        line = line.split('=', 1)   
        if len(line) == 2:
            line[1] = line[1].strip().strip('"').strip("'")
            env.env[line[0].strip()] = line[1]
    return env

def parse_test(test_content):
    """
    Parse test case content into a structured format.
    
    Args:
        test_content (str): Raw test case content
        
    Returns:
        TestCase: Parsed test case object
    """
    test_case = TestCase()
    current_section = None
    lines = test_content.split('\n')
    
    # Buffer to store multi-line content
    section_content = []
    
    for line in lines:
        # Handle section headers
        if line.startswith('=== TEST'):
            test_case.title = line.replace('=== TEST', '').strip()
            current_section = 'description'
            continue
            
        if line.startswith('--- '):
            # Save content from previous section
            if current_section == 'description':
                test_case.description = '\n'.join(section_content).strip()
            elif current_section == 'mysql_config':
                test_case.mysql_config = '\n'.join(section_content).strip()
            elif current_section == 'init_sql':
                test_case.init_sql = '\n'.join(section_content).strip()
            elif current_section == 'config':
                test_case.config = '\n'.join(section_content).strip()
            elif current_section == 'docker_compose_config':
                test_case.docker_compose_config = '\n'.join(section_content).strip()
            elif current_section == 'request':
                test_case.request = parse_request('\n'.join(section_content).strip())
            elif current_section == 'response_body':
                response_content = '\n'.join(section_content).strip()
                test_case.response_body, test_case.response_body_eval = parse_response_body(response_content)
            elif current_section == 'env':
                env_content = '\n'.join(section_content).strip()
                env = parse_env(env_content)
                test_case.env = env
                
            # Clear buffer and set new section
            section_content = []
            
            # Handle error code section specially
            if 'error_code' in line:
                error_content = line.split(':', 1)[1] if ':' in line else ''
                test_case.error_code, test_case.error_code_chomp = parse_error_code(error_content)
                current_section = None
            else:
                current_section = line.replace('---', '').strip()
            continue
            
        # Accumulate content for current section
        if current_section:
            section_content.append(line)
            
    # Handle last section if needed
    if current_section and section_content:
        if current_section == 'response_body':
            response_content = '\n'.join(section_content).strip()
            test_case.response_body, test_case.response_body_eval = parse_response_body(response_content)
            
    return test_case

# Example usage and testing
def print_test_case(test_case):
    """Print the parsed test case in a readable format"""
    print(f"Test Title: {test_case.title}")
    print(f"\nDescription:\n{test_case.description}")
    print(f"\nConfig:\n{test_case.config}")
    print(f"\nMySQL Config:\n{test_case.mysql_config}")
    print(f"\nInit SQL:\n{test_case.init_sql}")
    print(f"\nRequest:\n{test_case.request}")
    print(f"\nResponse Body:\n{test_case.response_body}")
    # if test_case.response_body_eval:
    #     print(f"Response Body Eval Expression: {test_case.response_body_eval}")
    print(f"\nError Code: {test_case.error_code}")
    print(f"\nEnv: {test_case.env}")

# # Test with regular content
test_content1 = """=== TEST 1: hello, world
    This is just a simple demonstration
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
    CREATE DATABASE api_test;
    CREATE USER 'api_test'@'%' IDENTIFIED BY 'api_test';
    GRANT ALL PRIVILEGES ON api_test.* TO 'api_test'@'%';
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
            - MYSQL_ROOT_PASSWORD=root
            - MYSQL_DATABASE=api_test
            - MYSQL_USER=api_test
            - MYSQL_PASSWORD=api_test
            - MYSQL_ALLOW_EMPTY_PASSWORD=yes
            - MYSQL_PORT=3306
            volumes:
            # - './docker/db/data:/var/lib/mysql'
            - './my.cnf:/etc/mysql/conf.d/my.cnf'
            - './init.sql:/docker-entrypoint-initdb.d/init.sql'
            restart: always

--- main_config 
    env MY_TEST

--- request
    GET /t

    
--- response_body
    hello, world!

--- error_code: 200"""

# # Test with eval and chomp
# test_content2 = """=== TEST 2: repeated content
# Testing eval response
# --- config
# location = /t {
#     echo "aaaa";
# }
# --- request
# GET /t
# --- response_body eval "a" x 4096
# --- error_code chomp 200"""

# # Run tests
# print("=== Test Case 1 ===")
# test_case1 = parse_test(test_content1)
# print_test_case(test_case1)

# print("\n=== Test Case 2 ===")
# test_case2 = parse_test(test_content2)
# print_test_case(test_case2)
