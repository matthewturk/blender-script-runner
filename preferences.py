import bpy

from . import registry


def _folders_changed(self, context):
    # Rescan after the property update finishes rather than registering
    # classes from inside an RNA update callback.
    bpy.app.timers.register(_deferred_reload, first_interval=0.1)


def _deferred_reload():
    registry.reload_all()
    return None


class SCRIPT_RUNNER_PG_folder(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(
        name="Folder",
        description="Folder of scripts to scan (not recursive; files starting with _ are skipped)",
        subtype="DIR_PATH",
        update=_folders_changed,
    )
    kind: bpy.props.EnumProperty(
        name="Kind",
        items=(
            (registry.SCRIPTS, "Scripts", "Scripts with PARAMS and execute(context, params)"),
            (registry.NODES, "Node Scripts", "nodebpy builders with build(tree, params)"),
        ),
        update=_folders_changed,
    )


class SCRIPT_RUNNER_OT_folder_add(bpy.types.Operator):
    """Add a script folder"""
    bl_idname = "script_runner.folder_add"
    bl_label = "Add Folder"
    bl_options = {"INTERNAL"}

    kind: bpy.props.StringProperty(default=registry.SCRIPTS)

    def execute(self, context):
        entry = context.preferences.addons[__package__].preferences.folders.add()
        entry.kind = self.kind
        return {"FINISHED"}


class SCRIPT_RUNNER_OT_folder_remove(bpy.types.Operator):
    """Remove this script folder"""
    bl_idname = "script_runner.folder_remove"
    bl_label = "Remove Folder"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty()

    def execute(self, context):
        context.preferences.addons[__package__].preferences.folders.remove(self.index)
        registry.reload_all()
        return {"FINISHED"}


class ScriptRunnerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    folders: bpy.props.CollectionProperty(type=SCRIPT_RUNNER_PG_folder)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Script folders (scanned in order; the first script of a name wins):")
        for index, entry in enumerate(self.folders):
            row = layout.row(align=True)
            row.prop(entry, "kind", text="")
            row.prop(entry, "path", text="")
            row.operator(SCRIPT_RUNNER_OT_folder_remove.bl_idname, text="", icon="X").index = index
        row = layout.row(align=True)
        row.operator(SCRIPT_RUNNER_OT_folder_add.bl_idname, text="Add Script Folder", icon="ADD").kind = registry.SCRIPTS
        row.operator(SCRIPT_RUNNER_OT_folder_add.bl_idname, text="Add Node Script Folder", icon="ADD").kind = registry.NODES

        box = layout.box()
        box.label(text="Always scanned as well:")
        for kind in (registry.SCRIPTS, registry.NODES):
            for folder in registry.folders(kind)[:1]:
                box.label(text=f"{kind.title()}: {folder}")


classes = (
    SCRIPT_RUNNER_PG_folder,
    SCRIPT_RUNNER_OT_folder_add,
    SCRIPT_RUNNER_OT_folder_remove,
    ScriptRunnerPreferences,
)
