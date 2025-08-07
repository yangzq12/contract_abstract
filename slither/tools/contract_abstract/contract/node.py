class StartNode:
    def __init__(self, function, arguments_contexts):
        self.function = function
        self.arguments_contexts = arguments_contexts

class EndNode:
    def __init__(self, function, call_operation):
        self.function = function
        self.call_operation = call_operation

class RemainNode:
    def __init__(self, irs):
        self.irs = irs