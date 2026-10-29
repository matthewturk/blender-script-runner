"""Find, load and register scripts from the configured folders.

Two kinds of script live in separate folders:

SCRIPTS  define PARAMS and execute(context, params); each gets its own
         operator (script_runner.dynamic_<name>) with a dialog for PARAMS.
NODES    define build(tree, params) and optionally NAME and PARAMS; the
         Build Node Tree operator runs build() inside a nodebpy tree.

Scripts are loaded only when the folders are scanned (at startup, on
Refresh, or when the folder list changes), never while the UI draws.
"""

import importlib.util
import os
import re
import sys

import bpy

from . import params as params_mod

SCRIPTS = "SCRIPTS"
NODES = "NODES"

# Scene property / class prefixes. Kept identical to the original startup
# runner so values saved in existing .blend files are picked up.
PROP_PREFIX = {SCRIPTS: "sr_props", NODES: "nsr_props"}
DEFAULT_SUBDIR = {SCRIPTS: "scripts", NODES: "node_scripts"}
MODULE_PREFIX = "script_runner_loaded"

# name -> loaded module, and the matching EnumProperty items (Blender
# requires the items list to stay referenced while the enum is in use).
modules = {SCRIPTS: {}, NODES: {}}
enum_items = {SCRIPTS: [], NODES: []}
_dynamic_classes = {SCRIPTS: [], NODES: []}


def prop_attr(kind, name):
    return f"{PROP_PREFIX[kind]}_{name.lower()}"


def operator_idname(name):
    return f"script_runner.dynamic_{name.lower()}"


def _safe_name(stem):
    return re.sub(r"\W", "_", stem).lower()


def folders(kind):
    """Folders to scan for `kind`: the extension's own per-user folder, then
    the ones listed in the add-on preferences, without duplicates."""
    found = []
    try:
        found.append(bpy.utils.extension_path_user(__package__, path=DEFAULT_SUBDIR[kind], create=True))
    except (ValueError, AttributeError):
        pass  # not installed as an extension (e.g. loaded by path in tests)
    addon = bpy.context.preferences.addons.get(__package__)
    if addon is not None:
        for entry in addon.preferences.folders:
            if entry.kind == kind and entry.path:
                found.append(bpy.path.abspath(entry.path))
    unique = []
    for path in found:
        path = os.path.realpath(path)
        if os.path.isdir(path) and path not in unique:
            unique.append(path)
    return unique


def _load(kind, path):
    """Execute one script file as a fresh module. Uses a namespaced module
    name so a script called e.g. csv.py can't replace the real csv module."""
    stem = os.path.splitext(os.path.basename(path))[0]
    module_name = f"{MODULE_PREFIX}.{kind.lower()}.{_safe_name(stem)}"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # dataclasses etc. look themselves up here
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def scan(kind):
    """Load every script of `kind`; returns {name: module}. The first folder
    wins when two contain a script with the same name."""
    found = {}
    for folder in folders(kind):
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".py") or filename.startswith(("_", ".")):
                continue
            name = _safe_name(filename[:-3])
            if name in found:
                print(f"[Script Runner] Skipping {os.path.join(folder, filename)}: "
                      f"'{name}' already loaded from another folder")
                continue
            try:
                module = _load(kind, os.path.join(folder, filename))
            except Exception as exc:
                print(f"[Script Runner] Failed to load {filename}: {exc}")
                continue
            if kind == SCRIPTS and hasattr(module, "PARAMS") and hasattr(module, "execute"):
                found[name] = module
            elif kind == NODES and hasattr(module, "build"):
                found[name] = module
    return found


def label(kind, name, module):
    if kind == SCRIPTS:
        return module.PARAMS.get("label", name.replace("_", " ").title())
    return getattr(module, "NAME", name.replace("_", " ").title())


def _unregister_dynamic(kind):
    for cls in reversed(_dynamic_classes[kind]):
        attr = getattr(cls, "_scene_attr", None)
        if attr and hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _dynamic_classes[kind].clear()


def _register_props(kind, name, module):
    attr = prop_attr(kind, name)
    group = type(attr, (bpy.types.PropertyGroup,), {
        "__annotations__": params_mod.blender_props(module.PARAMS),
        "_scene_attr": attr,
    })
    bpy.utils.register_class(group)
    _dynamic_classes[kind].append(group)
    setattr(bpy.types.Scene, attr, bpy.props.PointerProperty(type=group))


def _make_script_operator(name, module):
    attr = prop_attr(SCRIPTS, name)

    def execute(self, context):
        values = params_mod.collect(context, attr, module.PARAMS)
        try:
            return module.execute(context, values)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to run '{name}': {exc}")
            return {"CANCELLED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        params_mod.draw(self.layout, context, attr, module.PARAMS)

    return type(f"SR_OT_dynamic_{name}", (bpy.types.Operator,), {
        "bl_idname": operator_idname(name),
        "bl_label": f"Run {label(SCRIPTS, name, module)}",
        "bl_options": {"REGISTER", "UNDO"},
        "execute": execute,
        "invoke": invoke,
        "draw": draw,
    })


def reload(kind):
    """Rescan `kind`'s folders and rebuild its properties and operators."""
    _unregister_dynamic(kind)
    modules[kind] = scan(kind)
    verb = "Run" if kind == SCRIPTS else "Build"
    enum_items[kind] = [
        (name, label(kind, name, module), f"{verb} {getattr(module, '__file__', name)}")
        for name, module in modules[kind].items()
    ]
    for name, module in modules[kind].items():
        if getattr(module, "PARAMS", None):
            _register_props(kind, name, module)
        if kind == SCRIPTS:
            op = _make_script_operator(name, module)
            bpy.utils.register_class(op)
            _dynamic_classes[kind].append(op)
    print(f"[Script Runner] Loaded {len(modules[kind])} {kind.lower()} "
          f"from {len(folders(kind))} folder(s)")


def reload_all():
    reload(SCRIPTS)
    reload(NODES)


def unregister():
    for kind in (SCRIPTS, NODES):
        _unregister_dynamic(kind)
        modules[kind].clear()
        enum_items[kind].clear()
    for name in [m for m in sys.modules if m.startswith(MODULE_PREFIX + ".")]:
        del sys.modules[name]
