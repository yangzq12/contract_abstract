class AbstractContext:
    def __init__(self, input, storage, input_taint, storage_taint, value):
        self.input = input # 如果是结构体变量就是string数组，如果是简单变量就是string
        self.storage = storage # 如果是结构体变量就是string数组，如果是简单变量就是string
        self.input_taints = input_taint # 如果是结构体变量就是集合数组，如果是简单变量就是集合
        self.storage_taints = storage_taint # 如果是结构体变量就是集合数组，如果是简单变量就是集合
        self.value = value  # 如果是结构体变量就是string数组，如果是简单变量就是string

    def __str__(self):
        return f"Context(input={self.input}, storage={self.storage}, input_taint={self.input_taint}, storage_taint={self.storage_taint}, value={self.value})"

    def setValue(self, value):
        self.value = value