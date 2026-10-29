import textwrap

import bpy

from . import params as params_mod
from . import registry
from .registry import NODES, SCRIPTS


def _script_items(self, context):
    return registry.enum_items[SCRIPTS]


def _node_items(self, context):
    return registry.enum_items[NODES]


# Scene-level selection state; names match the original startup runner.
class DynamicScriptSettings(bpy.types.PropertyGroup):
    selected_script: bpy.props.EnumProperty(
        name="Select Script",
        description="Choose a script from your script folders",
        items=_script_items,
    )


class NodeScriptSettings(bpy.types.PropertyGroup):
    selected_script: bpy.props.EnumProperty(
        name="Select Node Script",
        description="Choose a node tree generation script",
        items=_node_items,
    )


class NODE_OT_run_script(bpy.types.Operator):
    """Build or rebuild the selected node tree"""
    bl_idname = "node_runner.run_script"
    bl_label = "Build Node Tree"
    bl_options = {"REGISTER", "UNDO"}

    script_name: bpy.props.StringProperty()

    def _module(self):
        return registry.modules[NODES].get(self.script_name)

    def invoke(self, context, event):
        module = self._module()
        if module is not None and getattr(module, "PARAMS", None):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        module = self._module()
        if module is not None:
            params_mod.draw(self.layout, context, registry.prop_attr(NODES, self.script_name), module.PARAMS)

    def execute(self, context):
        module = self._module()
        if module is None:
            self.report({"ERROR"}, f"Script '{self.script_name}' not found")
            return {"CANCELLED"}
        try:
            from nodebpy import geometry as g
        except ImportError:
            self.report({"ERROR"}, "Node scripts need the nodebpy package, which isn't importable")
            return {"CANCELLED"}

        values = params_mod.collect(
            context, registry.prop_attr(NODES, self.script_name), getattr(module, "PARAMS", {})
        )
        tree_name = values.pop("node_group_name", None) or registry.label(NODES, self.script_name, module)

        # Rebuild in place so existing users of the node group keep it.
        existing = bpy.data.node_groups.get(tree_name)
        if existing is not None:
            existing.interface.clear()
            existing.nodes.clear()

        try:
            with g.tree(existing or tree_name) as tree:
                module.build(tree, values)
                group = bpy.data.node_groups[tree_name]
                if not any(
                    item.item_type == "SOCKET" and item.in_out == "OUTPUT"
                    for item in group.interface.items_tree
                ):
                    tree.outputs.geometry("Output")
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to build '{tree_name}': {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Built node tree: {tree_name}")
        return {"FINISHED"}


class SR_OT_reload_scripts(bpy.types.Operator):
    """Rescan the script folders and rebuild each script's parameters"""
    bl_idname = "script_runner.reload_scripts"
    bl_label = "Refresh Script Library"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        registry.reload(SCRIPTS)
        if getattr(context, "area", None) is not None:
            context.area.tag_redraw()
        return {"FINISHED"}


class NODE_OT_reload_node_scripts(bpy.types.Operator):
    """Rescan the node script folders and refresh the list"""
    bl_idname = "node_runner.reload_scripts"
    bl_label = "Refresh Node Scripts"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        registry.reload(NODES)
        if getattr(context, "area", None) is not None:
            context.area.tag_redraw()
        return {"FINISHED"}


def _draw_description(layout, kind, name):
    module = registry.modules[kind].get(name)
    text = registry.description(module) if module is not None else ""
    if not text:
        return
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in textwrap.wrap(text, 60):
        col.label(text=line)


class SCRIPT_OT_browser(bpy.types.Operator):
    """Open the script & node tree browser"""
    bl_idname = "script_runner.browser"
    bl_label = "Script Browser"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        scene = context.scene

        box = self.layout.box()
        box.label(text="Scripts", icon="TEXT")
        row = box.row(align=True)
        row.prop(scene.dynamic_script_runner, "selected_script", text="")
        row.operator(SR_OT_reload_scripts.bl_idname, icon="FILE_REFRESH", text="")
        selected = scene.dynamic_script_runner.selected_script
        if selected in registry.modules[SCRIPTS]:
            _draw_description(box, SCRIPTS, selected)
            box.operator(registry.operator_idname(selected), text="Configure & Run", icon="PLAY")

        box = self.layout.box()
        box.label(text="Node Trees", icon="NODETREE")
        row = box.row(align=True)
        row.prop(scene.node_script_runner, "selected_script", text="")
        row.operator(NODE_OT_reload_node_scripts.bl_idname, icon="FILE_REFRESH", text="")
        selected_node = scene.node_script_runner.selected_script
        if selected_node in registry.modules[NODES]:
            _draw_description(box, NODES, selected_node)
            box.operator(
                NODE_OT_run_script.bl_idname, text="Build Node Tree", icon="PLAY"
            ).script_name = selected_node

        if not registry.modules[SCRIPTS] and not registry.modules[NODES]:
            self.layout.label(text="No scripts found. Add folders in the add-on preferences.", icon="INFO")

    def execute(self, context):
        return {"FINISHED"}


class OBJECT_PT_script_browser_button(bpy.types.Panel):
    """One-line sidebar entry point for the script browser popup"""
    bl_label = "Scripts"
    bl_idname = "OBJECT_PT_script_browser_button"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Script Runner"

    def draw(self, context):
        self.layout.operator(SCRIPT_OT_browser.bl_idname, icon="WINDOW", text="Open Script Browser")


classes = (
    DynamicScriptSettings,
    NodeScriptSettings,
    NODE_OT_run_script,
    SR_OT_reload_scripts,
    NODE_OT_reload_node_scripts,
    SCRIPT_OT_browser,
    OBJECT_PT_script_browser_button,
)
