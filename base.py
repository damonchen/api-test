
class TestRequest(object):
    def __init__(self):
        self.method = ""
        self.url = ""
        self.headers = []
        self.body = ""

    def __str__(self):
        return f"method: {self.method}, url: {self.url}, headers: {self.headers}, body: {self.body}"

class TestResponse(object):
    def __init__(self):
        self.body = ""
        self.status_code = 0
        self.headers = []
    
    def __str__(self):
        return f"body: {self.body}, status_code: {self.status_code}, headers: {self.headers}"


class Env(object):
    def __init__(self):
        self.env = {}

    def __str__(self):
        return f"env: {self.env}"
    
    def render(self, content):
        for key, value in self.env.items():
            content = content.replace("${%s}" % key, value)
        return content


class Web(object):
    def __init__(self):
        self.command = None
        self.args = []

    def __str__(self):
        return f"command: {self.command}, args: {self.args}"


class TestCase(object):
    def __init__(self):
        self.title = ""
        self.description = ""

        self.config = ""
        
        self.docker_compose_config = ""
        self.mysql_config = ""
        self.init_sql = ""
        self.env = Env()
        self.web = None

        self.request = ""
        self.response_body = ""
        self.response_body_func = None  # Store eval expression if present
        self.error_code = None
        self.error_code_filter = False  # Flag for chomp modifier


class TestSuite(object):
    def __init__(self):
        self.tests = []

    def __str__(self):
        return f"tests: {self.tests}"
    
    def add_test(self, test):
        self.tests.append(test)
