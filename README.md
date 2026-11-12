# Script Runner

A Blender extension that runs parameterized Python scripts and
[nodebpy](https://pypi.org/project/nodebpy/) node-tree builders from folders
you choose, and keeps node groups as Python files instead of assets.
Each script declares its inputs in a `PARAMS` dict, and Script
Runner turns that into a dialog, so a script can expose settings without any
UI code.

Open it from the 3D Viewport sidebar: **Script Runner > Open Script Browser**.

## Script folders

Set folders in **Preferences > Add-ons > Script Runner**. Each folder is
*Scripts*, *Node Scripts* or *Node Groups*. Folders are not scanned recursively, and
files starting with `_` are skipped, so shared helpers can live next to the
scripts. When two folders hold a script with the same name, the first one
wins.

The extension's own per-user folders (shown in the preferences) are always
scanned as well.

Scripts are loaded when Blender starts, when you press Refresh in the
browser, and when the folder list changes.

## Scripts

```python
DESCRIPTION = "Fill a collection with a grid of cubes"  # optional, see below
PARAMS = {
    "label": "Generate Grid",  # optional: name in the menu
    "size": {"type": "INT", "default": 10, "min": 1, "name": "Grid Size"},
    "target": {"type": "COLLECTION", "name": "Into Collection"},
}

def execute(context, params):
    ...
    return {"FINISHED"}
```

`DESCRIPTION` is shown under the script in the browser and as the tooltip on
its menu entry and Run button. Without one, the first paragraph of the
script's docstring is used.

Each script gets an operator, `script_runner.dynamic_<file name>`, so it can
also be bound to a key or added to Quick Favorites.

## Node scripts

```python
NAME = "Passthrough"  # node group name (default: from the file name)
DESCRIPTION = "Pass the geometry through unchanged"  # optional
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

## Node groups as scripts

Instead of keeping node groups in an asset library, you can keep them as
Python files that Script Runner defines in every file you open.

**Export:** right-click in a node editor and choose **Export Node Group to
Script**. It exports the selected group node's group, or else the group being
edited, and asks where to save. The file is nodebpy code (via
`nodebpy.export.to_python`) with one class per group, so groups the exported
one uses are written out too. **Keep Layout** stores node positions; without
it the group is arranged automatically when built. Nodes nodebpy can't
convert are written as `# TODO` placeholders, and you get a warning saying
how many.

**Define:** add the folder as a *Node Groups* folder in the preferences (or
save into the extension's own `node_groups/` folder). After Blender starts and
whenever a file is opened, every group those files define that the open file
doesn't have yet is created. Groups that already exist are left alone, so
opening an old file never changes it. Turn this off with **Define Node Groups
on Load**.

**Rebuild:** after editing a file, use **Rebuild All** in the Script
Browser's Node Groups box. Each group is rebuilt with
`nodebpy.live.run_source`: modifiers, group nodes and modifier input values
stay attached to it. A group you changed by hand in Blender since it was
built is kept as `<name> (edited)`. **Add Missing** does the same as the
on-load step.

Defined groups are ordinary local data: a file you save keeps its copy, and
groups nothing uses are dropped when the file is saved, then defined again
on the next load. Needs nodebpy (`to_python` and `nodebpy.live` arrived in
the 520.x series; tested with 530.0.3).

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
