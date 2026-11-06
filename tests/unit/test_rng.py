from talkaudit.core.rng import SeededRng


def draws(rng: SeededRng) -> list[object]:
    return [rng.random(), rng.randint(1, 100), rng.choice(["a", "b", "c"])]


def test_same_seed_same_values() -> None:
    assert draws(SeededRng(42)) == draws(SeededRng(42))


def test_different_seed_different_values() -> None:
    assert draws(SeededRng(42)) != draws(SeededRng(43))


def test_derive_ignores_parent_draws() -> None:
    fresh = SeededRng(42)
    used = SeededRng(42)
    draws(used)
    assert draws(fresh.derive("conv-1")) == draws(used.derive("conv-1"))


def test_derive_keys_are_independent() -> None:
    rng = SeededRng(42)
    assert draws(rng.derive("conv-1")) != draws(rng.derive("conv-2"))


def test_zero_weight_never_chosen() -> None:
    rng = SeededRng(7)
    picks = {rng.choice(["nahi", "nai"], weights=[1.0, 0.0]) for _ in range(200)}
    assert picks == {"nahi"}
