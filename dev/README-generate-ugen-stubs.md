# UGen Stub Generator

This utility generates `.pyi` stub files for UGen classes in the supriya project.

## Usage

```bash
python dev/generate-ugen-stubs.py
```

This will process all `.py` files in `supriya/ugens/` (excluding `__init__.py`, `core.py`, `compilers.py`, and `factories.py`) and generate corresponding `.pyi` stub files.

## What it does

The generator:

1. Parses each Python file for classes decorated with `@ugen`
2. Extracts decorator parameters (`ar`, `kr`, `ir`, `dr`, `new`, `is_multichannel`, `fixed_channel_count`, `channel_count`)
3. Collects `param()` calls to identify UGen parameters and their properties (`unexpanded`)
4. Generates stub classes with:
   - `__init__` method with proper type hints
   - Property stubs for each parameter
   - Rate class methods (`ar`, `kr`, `ir`, `dr`, `new`) based on decorator arguments

## Generated signatures

The stub generator follows the same logic as `supriya/ext/mypy.py`:

- **`__init__` parameters**:
  - `calculation_rate: CalculationRateLike`
  - `channel_count: int = N` (for multichannel UGens without `fixed_channel_count`)
  - Each param with `UGenScalarInput` or `UGenVectorInput` (if `unexpanded=True`)
  - `**kwargs: Any`

- **Properties**: Return `UGenScalar` or `UGenVector` (if `unexpanded=True`)

- **Rate methods** (`ar`, `kr`, `ir`, `dr`, `new`):
  - Parameters with `UGenRecursiveInput` type
  - `channel_count: int = N` (for multichannel UGens without `fixed_channel_count`)
  - Return `UGenOperable`

## Example

For a UGen like:

```python
@ugen(ar=True, kr=True, is_pure=True)
class SinOsc(UGen):
    frequency = param(440.0)
    phase = param(0.0)
```

The generator produces:

```python
class SinOsc(UGen):
    def __init__(self, *, calculation_rate: CalculationRateLike, frequency: UGenScalarInput = ..., phase: UGenScalarInput = ..., **kwargs: Any) -> None: ...
    @property
    def frequency(self) -> UGenScalar: ...
    @property
    def phase(self) -> UGenScalar: ...
    @classmethod
    def ar(cls, *, frequency: UGenRecursiveInput = ..., phase: UGenRecursiveInput = ...) -> UGenOperable: ...
    @classmethod
    def kr(cls, *, frequency: UGenRecursiveInput = ..., phase: UGenRecursiveInput = ...) -> UGenOperable: ...
```
