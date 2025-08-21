from collections import deque
from itertools import islice, pairwise
from typing import Generator, Iterable, Sequence, Callable
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


def remove_sequential_duplicates[T](arr:np.ndarray) -> np.ndarray:
    last = arr[0]
    result = [last]
    for item in arr[1:]:
        if not np.allclose(item, last):
            result.append(item)
            last = item
    return np.array(result)


def blur1d(values, count:int=31, std:int=6):
    blur_kernel = gaussian(count, std)
    blur_kernel /= blur_kernel.sum()
    return ndimage.convolve1d(values,blur_kernel)


def map_to_range(values:np.ndarray, min:float, max:float):
    target_range = max-min
    current_range = values.max()-values.min()
    return (values-values.min())/current_range*target_range+min




def create_array_interpolator[T](
    arrays:list[tuple[float, np.ndarray]]
) -> Callable[[float], np.ndarray]:
    first_position = arrays[0][0]
    last_position = arrays[-1][0]
    def _inner_create_array_interpolator(f:float):
        if f<=first_position:
            return arrays[0][1]
        if f>=last_position:
            return arrays[-1][1]
        for (pos_a, array_a), (pos_b, array_b) in pairwise(arrays):
            if f <= pos_b:
                ratio = (f-pos_a)/(pos_b-pos_a)
                return array_a + ratio*(array_b-array_a)
    return _inner_create_array_interpolator
