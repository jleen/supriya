# UGen Stub Generator

This utility generates `.pyi` stub files for UGen classes in the supriya project.

## Usage

```bash
python dev/generate-ugen-stubs.py
```

This will process all `.py` files in `supriya/ugens/` (excluding `__init__.py`, `core.py`, `compilers.py`, and `factories.py`) and generate corresponding `.pyi` stub files.

## What it does

The generator:

1. Parses each Python file for classes (both `@ugen` decorated and regular classes)
2. For `@ugen` classes:
   - Extracts decorator parameters (`ar`, `kr`, `ir`, `dr`, `new`, `is_multichannel`, `fixed_channel_count`, `channel_count`)
   - Collects `param()` calls to identify UGen parameters and their properties (`unexpanded`)
   - Generates stub classes with:
     - `__init__` method with proper type hints
     - Property stubs for each parameter
     - Rate class methods (`ar`, `kr`, `ir`, `dr`, `new`) based on decorator arguments
3. For non-`@ugen` classes (like `Envelope`, `Mix`, `CompanderD`):
   - Generates stubs by parsing the AST directly
   - Preserves type annotations where present
   - Includes public methods, properties, and special methods
   - Handles `@property`, `@staticmethod`, and `@classmethod` decorators

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

## Examples

### @ugen decorated class

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

### Non-@ugen class

For a regular class like:

```python
class Envelope:
    def __init__(
        self,
        amplitudes: Sequence[UGenOperable | float] = (0, 1, 0),
        durations: Sequence[UGenOperable | float] = (1, 1),
        # ... more parameters
    ) -> None:
        # implementation

    @property
    def duration(self) -> UGenOperable | float:
        # implementation

    @classmethod
    def percussive(cls, attack_time: float = 0.01, release_time: float = 1.0) -> 'Envelope':
        # implementation
```

The generator produces:

```python
class Envelope:
    def __init__(self, amplitudes: Sequence[UGenOperable | float] = (0, 1, 0), durations: Sequence[UGenOperable | float] = (1, 1), ...) -> None: ...
    @property
    def duration(self) -> UGenOperable | float: ...
    @classmethod
    def percussive(cls, attack_time: float = 0.01, release_time: float = 1.0) -> Envelope: ...
```
