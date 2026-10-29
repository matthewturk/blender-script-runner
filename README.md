# Script Runner

A Blender extension that runs parameterized Python scripts and
[nodebpy](https://pypi.org/project/nodebpy/) node-tree builders from folders
you choose. Each script declares its inputs in a `PARAMS` dict, and Script
Runner turns that into a dialog, so a script can expose settings without any
UI code.

Open it from the 3D Viewport sidebar: **Script Runner > Open Script Browser**.

## Script folders

Set folders in **Preferences > Add-ons > Script Runner**. Each folder is
either *Scripts* or *Node Scripts*. Folders are not scanned recursively, and
files starting with `_` are skipped, so shared helpers can live next to the
scripts. When two folders hold a script with the same name, the first one
wins.

The extension's own per-user folders (shown in the preferences) are always
scanned as well.

Scripts are loaded when Blender starts, when you press Refresh in the
browser, and when the folder list changes.

## Scripts

```python
PARAMS = {
    "label": "Generate Grid",  # optional: name in the menu
    "size": {"type": "INT", "default": 10, "min": 1, "name": "Grid Size"},
    "target": {"type": "COLLECTION", "name": "Into Collection"},
}

def execute(context, params):
    ...
    return {"FINISHED"}
```

Each script gets an operator, `script_runner.dynamic_<file name>`, so it can
also be bound to a key or added to Quick Favorites.

## Node scripts

```python
NAME = "Passthrough"  # node group name (default: from the file name)
PARAMS = {}           # optional, same format as above

def build(tree, params):
    from nodebpy import geometry as g
    geometry = tree.inputs.geometry("Geometry")
    tree.outputs.geometry("Output") >> geometry
```

Building again updates the existing node group in place, so modifiers using
it keep it. A `node_group_name` parameter, if a script defines one, overrides
the group name. Node scripts need nodebpy to be importable in Blender; it is
not bundled.

## Parameter types

| type | extra keys |
|---|---|
| `INT`, `FLOAT` | `min`, `max`; `unit` (FLOAT) |
| `BOOL`, `STRING`, `FILE_PATH`, `DIR_PATH` | |
| `COLOR` | default length sets RGB or RGBA |
| `VECTOR`, `INT_VECTOR` | |
| `OBJECT`, `COLLECTION` | |
| `POINTER` | `target`: a `bpy.types` name, e.g. `"Material"` |
| `ENUM` | `items`; `options: {"ENUM_FLAG"}` for multi-select |

All take `name`, `description` and `default`. Values are stored on the scene
(`Scene.sr_props_<script>` / `Scene.nsr_props_<script>`), so they're saved
with the .blend file.

See `examples/` for a script using every type.

## Moving from the blender-config startup runner

This replaces `scripts/startup/dynamic_script_runner.py` in blender-config.
Operator IDs and scene property names are unchanged, so saved values and key
bindings carry over. The two can't be active at once: remove
`dynamic_script_runner` from that repo's `scripts/startup/__init__.py`, then
add its `user_scripts/` and `node_scripts/` folders in the preferences here.

## Building

```bash
blender --command extension build      # writes script_runner-<version>.zip
blender --command extension validate
```

Pushing a `v*` tag (e.g. `v2.0.1`) builds the zip on GitHub Actions and
attaches it to a GitHub release. The tag has to match `version` in
`blender_manifest.toml`, or the build fails. Pull requests and manual runs
only build the zip, as a downloadable workflow artifact.

License: GPL-3.0-or-later.
