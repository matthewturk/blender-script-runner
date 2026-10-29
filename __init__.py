"""Script Runner: run parameterized Python scripts and nodebpy node-tree
builders from folders you choose, with a generated dialog for each script's
PARAMS. See README.md for the script format."""

import bpy

from . import operators, preferences, registry

_classes = preferences.classes + operators.classes


def _reload_on_startup():
    registry.reload_all()
    return None


def register():
    # Operator and scene-property names match the original startup-script
    # runner (so saved values carry over); two copies can't both register.
    if "dynamic_script_runner" in bpy.types.Scene.bl_rna.properties:
        raise RuntimeError(
            "Script Runner: another script runner is already registered "
            "(the dynamic_script_runner startup script?). Disable it first."
        )
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dynamic_script_runner = bpy.props.PointerProperty(type=operators.DynamicScriptSettings)
    bpy.types.Scene.node_script_runner = bpy.props.PointerProperty(type=operators.NodeScriptSettings)
    # Scan after startup finishes, once preferences are loaded.
    bpy.app.timers.register(_reload_on_startup, first_interval=0.5)


def unregister():
    if bpy.app.timers.is_registered(_reload_on_startup):
        bpy.app.timers.unregister(_reload_on_startup)
    registry.unregister()
    del bpy.types.Scene.dynamic_script_runner
    del bpy.types.Scene.node_script_runner
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
