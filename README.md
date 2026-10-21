# N64-Docs

Shared [Sphinx](https://www.sphinx-doc.org) setup for documentation.

NOTE: I only use this for my own projects to avoid duping code.<br>
This is not intended as a general docs lib.

## Setup

```
docs/
  conf.py
  requirements.txt
  index.rst
  docs/...
  _static/
    logo.png
    favicon.ico
```

`requirements.txt`:
```
n64-docs @ git+https://github.com/HailToDodongo/n64-docs@main
```

`conf.py`:
```python
from n64_docs import setup_project

setup_project(globals(),
  project="MyProject",
  author="Me",
  
  cpp_api={
    "name": "myproject",
    "input": "../src/include",
    "out_dir": "docs/manual/api",
    "intro": "Reference for the public API.",
  },
)
```

## Building

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

n64-docs build

n64-docs serve
```