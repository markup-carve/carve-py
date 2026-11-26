# carve-py on Carve 0.2

This `main` branch binds the unreleased Carve 0.2 Rust engine to Python. It is
not a package release. Build a wheel from this branch and its pinned engine git
commit with Rust 1.88 or newer:

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
diagnostics, formatting, HTML import, standard extensions, and available export writers.

## Native extension callbacks

A Python callable can render a declared 0.2 extension node. Use a callable for both modes, or a dictionary with `interactive` and `static` callables to select each channel. Each renderer receives a JSON-shaped node and returns trusted HTML. Ordered transforms receive a JSON-shaped resolved document and return the edited document.

```python
import carve

result = carve.render_with_host(
    "# Guide",
    transforms=[lambda tree: tree],
)
print(result["html"])
```

Pass `tree=` to `render_with_host` for an already declared extension tree. A callback exception or non-string renderer result produces the engine's `extension-renderer-failed` diagnostic and writes the fallback. A failed transform produces `extension-transform-failed` and keeps the prior view.
