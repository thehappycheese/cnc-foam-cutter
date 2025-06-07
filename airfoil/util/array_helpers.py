from warnings import deprecated
from collections import deque
from itertools import islice, pairwise
from typing import Generator, Iterable, Sequence

import numpy as np
from scipy import ndimage
from scipy.signal.windows import gaussian


def sliding_window[T](iterable:Iterable[T], n:int) -> Generator[tuple[T,...]]:
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


def remove_sequential_duplicates(arr):
    last = arr[0]
    result = [last]
    for item in arr[1:]:
        if not np.allclose(item, last):
            result.append(item)
            last = item
    return np.array(result)


def blur1d(values, count=31, std=6):
    blur_kernel = gaussian(count,std)
    blur_kernel /= blur_kernel.sum()
    return ndimage.convolve1d(values,blur_kernel)


def map_to_range(values:np.ndarray, min:float, max:float):
    target_range = max-min
    current_range = values.max()-values.min()
    return (values-values.min())/current_range*target_range+min