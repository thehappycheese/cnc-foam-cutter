from functools import reduce

def compose(*a):
    return lambda x: reduce(lambda x,f: f(x), a, x)
