"""Turn a script's PARAMS dict into Blender properties, and read them back.

PARAMS maps a key to a spec: {"type": ..., "name": ..., "description": ...,
"default": ..., plus type-specific fields}. Supported types: INT, FLOAT
(both accept "min", "max" and "unit"), BOOL, STRING, FILE_PATH, DIR_PATH,
COLOR, VECTOR, INT_VECTOR, OBJECT, COLLECTION, POINTER ("target": a
bpy.types name) and ENUM ("items", optionally "options": {"ENUM_FLAG"}).
A "label" key, if present, names the script in the menu and isn't a property.
"""

import bpy

INT_MIN, INT_MAX = -2147483648, 2147483647
FLOAT_MAX = 3.402823e38


def _enum_property(name, desc, spec):
    raw_options = spec.get("options", set())
    options = set(raw_options) if isinstance(raw_options, (list, tuple, set)) else set()
    items = spec.get("items", [])

    if "ENUM_FLAG" in options:
        raw_default = spec.get("default", set())
        if isinstance(raw_default, (list, tuple, set)):
            default = set(raw_default)
        else:
            default = {str(raw_default)} if raw_default else set()
        return bpy.props.EnumProperty(
            name=name, description=desc, items=items, options=options, default=default
        )

    default = spec.get("default", "")
    if isinstance(default, (set, list, tuple)):
        default = list(default)[0] if default else ""
    if not default and items:
        default = items[0][0]
    return bpy.props.EnumProperty(name=name, description=desc, items=items, default=str(default))


def blender_props(params):
    """{key: bpy.props.*} for every spec in PARAMS with a known type."""
    props = {}
    for key, spec in params.items():
        if key == "label":
            continue
        p_type = spec.get("type")
        name = spec.get("name", key)
        desc = spec.get("description", "")

        if p_type in {"INT", "FLOAT"}:
            is_int = p_type == "INT"
            kwargs = {
                "name": name,
                "description": desc,
                "default": spec.get("default", 0 if is_int else 0.0),
                "min": spec.get("min", INT_MIN if is_int else -FLOAT_MAX),
                "max": spec.get("max", INT_MAX if is_int else FLOAT_MAX),
            }
            if "unit" in spec and not is_int:
                kwargs["unit"] = spec["unit"]
            props[key] = (bpy.props.IntProperty if is_int else bpy.props.FloatProperty)(**kwargs)
        elif p_type == "BOOL":
            props[key] = bpy.props.BoolProperty(
                name=name, description=desc, default=spec.get("default", False)
            )
        elif p_type in {"STRING", "FILE_PATH", "DIR_PATH"}:
            subtype = {"STRING": "NONE"}.get(p_type, p_type)
            props[key] = bpy.props.StringProperty(
                name=name, description=desc, default=spec.get("default", ""), subtype=subtype
            )
        elif p_type == "COLOR":
            default = spec.get("default", (1.0, 1.0, 1.0, 1.0))
            props[key] = bpy.props.FloatVectorProperty(
                name=name, description=desc, default=default, size=len(default),
                subtype="COLOR", min=0.0, max=1.0,
            )
        elif p_type == "VECTOR":
            props[key] = bpy.props.FloatVectorProperty(
                name=name, description=desc,
                default=spec.get("default", (0.0, 0.0, 0.0)), subtype="TRANSLATION",
            )
        elif p_type == "INT_VECTOR":
            default = spec.get("default", (0, 0, 0))
            props[key] = bpy.props.IntVectorProperty(
                name=name, description=desc, default=default, size=len(default)
            )
        elif p_type in {"OBJECT", "COLLECTION", "POINTER"}:
            target = {"OBJECT": "Object", "COLLECTION": "Collection"}.get(
                p_type, spec.get("target", "Object")
            )
            props[key] = bpy.props.PointerProperty(
                name=name, description=desc, type=getattr(bpy.types, target, bpy.types.Object)
            )
        elif p_type == "ENUM":
            props[key] = _enum_property(name, desc, spec)
        else:
            print(f"[Script Runner] Ignoring PARAMS['{key}']: unknown type {p_type!r}")
    return props


def collect(context, prop_attr, params):
    """Current values from the scene's property group, defaults otherwise."""
    values = {}
    container = getattr(context.scene, prop_attr, None)
    for key, spec in params.items():
        if key == "label":
            continue
        if container is not None and hasattr(container, key):
            value = getattr(container, key)
            if spec.get("type") in {"COLOR", "VECTOR", "INT_VECTOR"}:
                value = tuple(value)
            values[key] = value
        else:
            values[key] = spec.get("default")
    return values


def draw(layout, context, prop_attr, params):
    container = getattr(context.scene, prop_attr, None)
    if container is None:
        layout.label(text="Error loading parameters.", icon="ERROR")
        return
    for key in params:
        if key != "label" and hasattr(container, key):
            layout.prop(container, key)
