"""Node groups kept as Python files instead of assets.

Export: turn a node group into nodebpy code (one Custom*Group class per
group, nested groups included) with nodebpy.export.to_python.

Define: run every file in the Node Groups folders and create each class's
group in the open .blend if it isn't there yet. This runs at startup and
after every file load, so the groups are always available. Groups that
already exist are left alone; "rebuild" replaces them with what the files
say now, using nodebpy.live.run_source so modifiers, group nodes and their
input values stay attached.
"""

import contextlib
import datetime
import os
import re
import warnings

import bpy

from . import registry
from .registry import GROUPS

# Appended to a file's source for a rebuild: run_source only builds the last
# class of a class-only file, so build every group class the file defines.
_BUILD_ALL = """

for _sr_value in list(globals().values()):
    if (
        isinstance(_sr_value, type)
        and _sr_value.__module__ == __name__
        and getattr(_sr_value, "_name", None)
        and callable(getattr(_sr_value, "create_group", None))
    ):
        _sr_value.create_group()
"""


def _need_nodebpy():
    try:
        import nodebpy  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Node groups need the nodebpy package, which isn't importable") from exc


def group_files():
    """Every .py file in the Node Groups folders (not recursive; files
    starting with _ or . are skipped). The first folder wins on a name clash."""
    found = {}
    for folder in registry.folders(GROUPS):
        for filename in sorted(os.listdir(folder)):
            if filename.endswith(".py") and not filename.startswith(("_", ".")):
                found.setdefault(filename, os.path.join(folder, filename))
    return list(found.values())


def _group_classes(module):
    return [
        value for value in vars(module).values()
        if isinstance(value, type)
        and value.__module__ == module.__name__
        and getattr(value, "_name", None)
        and callable(getattr(value, "create_group", None))
    ]


def define_missing(paths=None):
    """Create every group the files define that the open file lacks.
    Returns (created group names, [(path, error message)])."""
    _need_nodebpy()
    errors = []
    before = {group.session_uid for group in bpy.data.node_groups}
    for path in group_files() if paths is None else paths:
        try:
            module = registry._load(GROUPS, path)
        except Exception as exc:
            errors.append((path, str(exc)))
            continue
        for cls in _group_classes(module):
            if cls._name in bpy.data.node_groups:
                continue
            try:
                cls.create_group()
            except Exception as exc:
                errors.append((path, f"{cls._name}: {exc}"))
    # Nested groups are created along with the groups that use them.
    created = [g.name for g in bpy.data.node_groups if g.session_uid not in before]
    return created, errors


@contextlib.contextmanager
def _compare_array_defaults_by_value(live):
    """Work around nodebpy (530.0.3) live._read_build recording interface
    fields with repr(): a Color socket's default repr is a path containing
    the tree's name, which changes when run_source renames the old tree to
    "<name>.stale", so every group with a Color socket looked edited by hand
    and was kept as "<name> (edited)". Compares those values by value
    instead; does nothing if nodebpy's internals no longer look like this."""
    original = getattr(live, "_read_build", None)
    fields = getattr(live, "_INTERFACE_FIELDS", None)
    build_cls = getattr(live, "_Build", None)
    if original is None or fields is None or build_cls is None:
        yield
        return

    def key(value):
        if type(value).__name__ == "bpy_prop_array":
            return repr(tuple(value))
        return repr(value)

    def read_build(tree):
        build, skips = original(tree)
        interface = [tuple(key(getattr(item, name, None)) for name in fields)
                     for item in tree.interface.items_tree]
        return build_cls(build.nodes, interface), skips

    live._read_build = read_build
    try:
        yield
    finally:
        live._read_build = original


def rebuild(paths=None):
    """Rebuild every group the files define, replacing existing ones in place.
    A group changed by hand since it was built is kept as "<name> (edited)".
    Returns (rebuilt group names, [(path, error message)], [warning messages])."""
    _need_nodebpy()
    from nodebpy import live
    from nodebpy.live import group_names_in_source, run_source

    rebuilt, errors, notes = [], [], []
    for path in group_files() if paths is None else paths:
        try:
            with open(path, encoding="utf-8") as handle:
                code = handle.read()
            with _compare_array_defaults_by_value(live), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_source(code + _BUILD_ALL, filename=path)
        except Exception as exc:
            errors.append((path, f"{type(exc).__name__}: {exc}"))
            continue
        rebuilt.extend(sorted(group_names_in_source(code)))
        notes.extend(str(w.message) for w in caught if w.category.__name__ == "EditedTreeWarning")
    return rebuilt, errors, notes


def _snake(name):
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "node_group"


def export_source(tree, keep_layout=False):
    """nodebpy source that recreates `tree` (and the groups it uses) as
    classes, with a header saying where it came from. Returns (source,
    number of nodes nodebpy couldn't convert)."""
    _need_nodebpy()
    import nodebpy
    from nodebpy.export import to_python

    code = to_python(tree, top_level="class", strict=False, snapshot_positions=keep_layout)
    todos = len(re.findall(r"= None  # TODO", code))
    source_file = bpy.data.filepath or "an unsaved file"
    header = [
        f'"""Node group "{tree.name}" as nodebpy code.',
        "",
        f"Exported by Script Runner from {source_file}",
        f"on {datetime.date.today().isoformat()} with nodebpy {getattr(nodebpy, '__version__', '?')}.",
        "Put it in a Script Runner Node Groups folder and its groups are created",
        "in every file that doesn't have them.",
    ]
    if getattr(tree, "description", ""):
        header += ["", tree.description]
    if todos:
        header += ["", f"{todos} node(s) had no nodebpy equivalent; look for '# TODO'."]
    header.append('"""')
    source = "\n".join(header) + "\n\n" + code.rstrip() + "\n"
    compile(source, tree.name, "exec")  # never write a file that can't load
    return source, todos


def _export_target(context, tree_name):
    if tree_name:
        return bpy.data.node_groups.get(tree_name)
    space = getattr(context, "space_data", None)
    if space is None or space.type != "NODE_EDITOR":
        return None
    node = getattr(context, "active_node", None)
    if node is not None and node.select and getattr(node, "node_tree", None) is not None:
        return node.node_tree
    tree = space.edit_tree
    # A material's or the compositor's own tree isn't a node group.
    if tree is not None and not tree.is_embedded_data:
        return tree
    return None


class SCRIPT_RUNNER_OT_export_node_group(bpy.types.Operator):
    """Save this node group as a nodebpy Python file, so it can be defined
    from a Node Groups folder instead of an asset library"""
    bl_idname = "script_runner.export_node_group"
    bl_label = "Export Node Group to Script"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.py", options={"HIDDEN"})
    tree_name: bpy.props.StringProperty(
        name="Node Group",
        description="Group to export (default: the selected group node's, else the one being edited)",
        options={"SKIP_SAVE"},
    )
    keep_layout: bpy.props.BoolProperty(
        name="Keep Layout",
        description="Restore node positions when the group is built, instead of arranging it automatically",
        default=False,
    )

    # No poll(): it can't see tree_name, which lets scripts and other menus
    # name the group. The context menu only shows the entry when there's one.

    def invoke(self, context, event):
        tree = _export_target(context, self.tree_name)
        if tree is None:
            self.report({"ERROR"}, "No node group to export")
            return {"CANCELLED"}
        self.tree_name = tree.name
        folders = registry.folders(GROUPS)
        # Prefer a folder from the preferences over the extension's own one.
        folder = folders[-1] if folders else os.path.expanduser("~")
        self.filepath = os.path.join(folder, _snake(tree.name) + ".py")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        tree = _export_target(context, self.tree_name)
        if tree is None:
            self.report({"ERROR"}, "No node group to export")
            return {"CANCELLED"}
        path = bpy.path.ensure_ext(bpy.path.abspath(self.filepath), ".py")
        try:
            source, todos = export_source(tree, keep_layout=self.keep_layout)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(source)
        except Exception as exc:
            self.report({"ERROR"}, f"Couldn't export '{tree.name}': {type(exc).__name__}: {exc}")
            return {"CANCELLED"}
        if todos:
            self.report({"WARNING"}, f"Saved {path}; {todos} node(s) couldn't be converted (marked # TODO)")
        else:
            self.report({"INFO"}, f"Saved {path}")
        return {"FINISHED"}


class SCRIPT_RUNNER_OT_define_node_groups(bpy.types.Operator):
    """Create the node groups defined in the Node Groups folders"""
    bl_idname = "script_runner.define_node_groups"
    bl_label = "Define Node Groups"
    bl_options = {"REGISTER", "UNDO"}

    rebuild: bpy.props.BoolProperty(
        name="Rebuild Existing",
        description="Replace groups that already exist with what the files define now "
                    "(groups changed by hand are kept as '<name> (edited)')",
        default=False,
    )

    def execute(self, context):
        try:
            if self.rebuild:
                names, errors, notes = rebuild()
            else:
                names, errors = define_missing()
                notes = []
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for path, message in errors:
            self.report({"ERROR"}, f"{os.path.basename(path)}: {message}")
        for note in notes:
            self.report({"WARNING"}, note)
        verb = "Rebuilt" if self.rebuild else "Created"
        self.report({"INFO"}, f"{verb} {len(names)} node group(s)")
        return {"FINISHED"} if names or not errors else {"CANCELLED"}


def define_quietly():
    """Startup / load_post: create missing groups, print problems."""
    try:
        created, errors = define_missing()
    except RuntimeError:
        if group_files():
            print("[Script Runner] Node Groups folders have files, but nodebpy isn't importable")
        return
    for path, message in errors:
        print(f"[Script Runner] {path}: {message}")
    if created:
        print(f"[Script Runner] Defined node groups: {', '.join(created)}")


def draw_context_menu(self, context):
    if _export_target(context, "") is not None:
        self.layout.separator()
        self.layout.operator(SCRIPT_RUNNER_OT_export_node_group.bl_idname, icon="EXPORT")


classes = (
    SCRIPT_RUNNER_OT_export_node_group,
    SCRIPT_RUNNER_OT_define_node_groups,
)
