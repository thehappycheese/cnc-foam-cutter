from itertools import islice
from collections import deque

def sliding_window(iterable, n):
    "Collect data into overlapping fixed-length chunks or blocks."
    # sliding_window('ABCDEFG', 4) → ABCD BCDE CDEF DEFG
    iterator = iter(iterable)
    window = deque(islice(iterator, n - 1), maxlen=n)
    for x in iterator:
        window.append(x)
        yield tuple(window)

from typing import Sequence
from itertools import pairwise
def split_indexable[T](arr:Sequence[T],indicies:list[int])->list[Sequence[T]]:
    filtered_indices = [index for index in indicies if index>0 and index<len(arr)]
    result = []
    for a,b in pairwise([0]+sorted(filtered_indices)+[len(arr)]):
        result.append(arr[a:b+1])
    return result