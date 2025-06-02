from typing import Sequence, Iterable

from collections import deque

from itertools import islice, pairwise

def sliding_window(iterable:Iterable, n:int):
    iterator = iter(iterable)
    window = deque(islice(iterator, n - 1), maxlen=n)
    for x in iterator:
        window.append(x)
        yield tuple(window)

def split_indexable[T](arr:Sequence[T],indicies:list[int]) -> list[Sequence[T]]:
    filtered_indices = [index for index in indicies if index>0 and index<len(arr)]
    result = []
    for a,b in pairwise([0]+sorted(filtered_indices)+[len(arr)]):
        result.append(arr[a:b+1])
    return result
