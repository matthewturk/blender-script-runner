"""Script Runner: run parameterized Python scripts and nodebpy node-tree
builders from folders you choose, with a generated dialog for each script's
PARAMS, and keep node groups as Python files that are defined in every file
you open. See README.md for the script format."""

import bpy
from bpy.app.handlers import persistent

from . import node_groups, operators, preferences, registry

_classes = preferences.classes + operators.classes + node_groups.classes


def _define_groups_enabled():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon is None or addon.preferences.define_node_groups_on_load


def _reload_on_startup():
    registry.reload_all()
    if _define_groups_enabled():
        node_groups.define_quietly()
    return None


@persistent
def _define_groups_on_load(*_args):
    if _define_groups_enabled():
        node_groups.define_quietly()


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
    bpy.types.NODE_MT_context_menu.append(node_groups.draw_context_menu)
    bpy.app.handlers.load_post.append(_define_groups_on_load)
    # Scan after startup finishes, once preferences are loaded.
    bpy.app.timers.register(_reload_on_startup, first_interval=0.5)


def unregister():
    if bpy.app.timers.is_registered(_reload_on_startup):
        bpy.app.timers.unregister(_reload_on_startup)
    if _define_groups_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_define_groups_on_load)
    bpy.types.NODE_MT_context_menu.remove(node_groups.draw_context_menu)
    registry.unregister()
    del bpy.types.Scene.dynamic_script_runner
    del bpy.types.Scene.node_script_runner
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
