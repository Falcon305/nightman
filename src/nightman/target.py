from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class Origin:
    kind: str
    ref: str


@dataclass
class Target:
    spec: str
    origin: Origin
    qualname: str
    func: Any
    module: Any


class TargetError(ValueError):
    pass


def _split_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise TargetError(f"target '{spec}' must be module:function or path/to/file.py:function")
    ref, qualname = spec.rsplit(":", 1)
    if not ref or not qualname:
        raise TargetError(f"target '{spec}' must be module:function or path/to/file.py:function")
    return ref, qualname


def _dotted_from_path(path: str) -> tuple[str, str] | None:
    directory = os.path.dirname(path)
    parts = [os.path.splitext(os.path.basename(path))[0]]
    while os.path.exists(os.path.join(directory, "__init__.py")):
        parts.append(os.path.basename(directory))
        directory = os.path.dirname(directory)
    if len(parts) == 1:
        return None
    return directory, ".".join(reversed(parts))


def _load_module_from_ref(ref: str) -> tuple[Origin, Any]:
    looks_like_path = ref.endswith(".py") or os.sep in ref or os.path.exists(ref)
    if looks_like_path:
        path = os.path.abspath(ref)
        if not os.path.exists(path):
            raise TargetError(f"file not found: {ref}")
        packaged = _dotted_from_path(path)
        if packaged is not None:
            root, dotted = packaged
            if root and root not in sys.path:
                sys.path.insert(0, root)
            module = importlib.import_module(dotted)
            return Origin("path", path), module
        module_name = f"_nightman_target_{abs(hash(path))}"
        directory = os.path.dirname(path)
        if directory not in sys.path:
            sys.path.insert(0, directory)
        spec_obj = importlib.util.spec_from_file_location(module_name, path)
        if spec_obj is None or spec_obj.loader is None:
            raise TargetError(f"could not import file: {ref}")
        module = importlib.util.module_from_spec(spec_obj)
        sys.modules[module_name] = module
        spec_obj.loader.exec_module(module)
        return Origin("path", path), module
    module = importlib.import_module(ref)
    return Origin("module", ref), module


def _resolve_qualname(module: Any, qualname: str) -> Any:
    obj = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            raise TargetError(f"{qualname} not found in {getattr(module, '__name__', module)}")
    if not callable(obj):
        raise TargetError(f"{qualname} is not callable")
    return obj


def load_target(spec: str) -> Target:
    ref, qualname = _split_spec(spec)
    origin, module = _load_module_from_ref(ref)
    func = _resolve_qualname(module, qualname)
    return Target(spec=spec, origin=origin, qualname=qualname, func=func, module=module)


def reload_from_origin(origin_kind: str, origin_ref: str, qualname: str) -> Any:
    _, module = _load_module_from_ref(origin_ref)
    return _resolve_qualname(module, qualname)


def sibling_functions(target: Target) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name in dir(target.module):
        if name.startswith("_"):
            continue
        obj = getattr(target.module, name)
        if callable(obj) and getattr(obj, "__module__", None) == getattr(target.module, "__name__", None):
            found[name] = obj
    return found
