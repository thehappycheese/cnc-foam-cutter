from pydantic import BeforeValidator, WrapSerializer
from typing import Annotated
import numpy as np

type NDArray = Annotated[
    np.ndarray,
    WrapSerializer(
        lambda value,next: next(value.tolist())
    ),
    BeforeValidator(lambda v: np.array(v))
]