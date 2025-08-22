import copy

class AbstractContext:
    def __init__(self, input, storage, input_taint, storage_taint, value):
        # input表示其实该变量就是指向的最外层函数的某个input的值
        self.input = input # 如果是结构体变量、tuple就是string数组，如果是简单变量就是string
        # storage表示其实该变量就是指向的最外层合约的某个storage的值
        self.storage = storage # 如果是结构体变量、tuple就是string数组，如果是简单变量就是string
        # input_taints表示该变量受到某些input值的taint
        self.input_taints = input_taint # 如果是结构体变量、tuple就是集合数组，如果是简单变量就是集合
        # storage_taints表示该变量受到某些storage值的taint
        self.storage_taints = storage_taint # 如果是结构体变量、tuple就是集合数组，如果是简单变量就是集合
        # value表示该变量当前的值的表示
        if value is None:
            self.value = "$unknown$"
        else:
            self.value = value  # 如果是结构体变量、tuple就是string数组，如果是简单变量就是string

    def __str__(self):
        return f"Context(input={self.input}, storage={self.storage}, input_taint={self.input_taint}, storage_taint={self.storage_taint}, value={self.value})"

    def setValue(self, value):
        self.value = value
    
    def copy(self):
        return AbstractContext(copy.deepcopy(self.input), copy.deepcopy(self.storage), copy.deepcopy(self.input_taints), copy.deepcopy(self.storage_taints), copy.deepcopy(self.value))