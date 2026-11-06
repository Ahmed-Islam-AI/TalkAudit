import random
from collections.abc import Sequence


class SeededRng:
    """The only source of randomness in core. Same seed and same calls give the same values."""

    def __init__(self, seed: int | str) -> None:
        self._seed = str(seed)
        # A str seed is hashed with SHA-512, so it is stable across runs and platforms.
        self._random = random.Random(self._seed)

    def random(self) -> float:
        return self._random.random()

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def choice[T](self, options: Sequence[T], weights: Sequence[float] | None = None) -> T:
        return self._random.choices(options, weights=weights)[0]

    def derive(self, key: str) -> "SeededRng":
        # Depends only on the seed and key, not on how much the parent has drawn, so a
        # conversation's randomness doesn't change with run order, concurrency or resume.
        return SeededRng(f"{self._seed}/{key}")
