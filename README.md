# carve (Python binding)

Python bindings for the Carve Rust engine. Version 0.1.12 uses `carve-lang` engine 0.1.13 to process Carve 0.1 documents. See the [Carve documentation](https://markup-carve.github.io/carve/).

## Install

```sh
pip install carve-lang
```

## Usage

```python
import carve
print(carve.to_html("# Hello *world*"))
```

## Documentation

- [Carve documentation](https://markup-carve.github.io/carve/)
- [Guide](docs/guide.md)
- [Documentation index](docs/README.md)

## License

[MIT](LICENSE).
