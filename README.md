# carve-py on Carve 0.2

This `next2` branch binds the unreleased Carve 0.2 Rust engine to Python. It is
not a package release. Build a wheel from this branch and its pinned engine git
commit with Rust 1.85 or newer:

```sh
python -m pip install maturin
maturin build --release --out dist
python -m pip install dist/*.whl
```

```python
import carve

result = carve.render("# Hello *world*")
print(result["html"])

tree = carve.parse("# Hello")["tree"]
print(carve.write(tree)["output"])

diagnostics = carve.lint("# Hello")["diagnostics"]
```

Options use the Carve 0.2 names in a dictionary. Raw HTML is disabled by
default. See the [guide](docs/guide.md) for safe rendering, include roots,
diagnostics, formatting, HTML import, standard extensions, and pending writers.
