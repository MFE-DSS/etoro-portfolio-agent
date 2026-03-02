from dataclasses import dataclass
from typing import List

@dataclass
class DataPoint:
    date: str
    value: float

@dataclass
class SeriesData:
    key: str
    data: List[DataPoint]

    @property
    def latest(self) -> float:
        return self.data[-1].value if self.data else 0.0
