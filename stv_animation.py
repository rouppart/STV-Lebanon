from math import pi
import bpy
import bmesh

from blender_interface import BucketG, VoteBaseG, VoteFractionG, build_from_cli


def build_first_mesh(name, width, heightratio, zoffset, materialname):
    bpy.ops.mesh.primitive_cube_add(size=width)
    obj = bpy.context.object  # Assign Object
    obj.data.name = name
    obj.scale[2] = heightratio
    obj.location[2] = width * heightratio / 2 + zoffset
    bpy.ops.object.transform_apply(location=True, scale=True)
    obj.data.materials.append(bpy.data.materials[materialname])
    return obj


def add_driver(obj, path, path_index, var_data_path, expression):
    driver = obj.driver_add(path, -1 if path_index is None else path_index).driver
    var = driver.variables.new()
    vart = var.targets[0]
    vart.id = obj
    vart.data_path = '["{}"]'.format(var_data_path)
    driver.expression = expression


def build_location_animation(obj, ref):
    for frame, location in ref.animation_location.items():
        obj.location = location
        obj.keyframe_insert(data_path='location', frame=frame)


def build_fill_animation(obj, ref):
    lastframe = 0
    lasthide = None
    for frame in sorted(ref.animation_fill.keys()):
        fill = float(ref.animation_fill[frame])
        obj['Votes'] = fill
        obj.keyframe_insert(data_path='["Votes"]', frame=frame)

        hide = fill < 0.0001
        if lasthide is None or hide != lasthide:
            hframe = frame - .25 if hide else lastframe + .25
            obj.hide_viewport = hide
            obj.keyframe_insert(data_path='hide_viewport', frame=hframe)
            obj.hide_render = hide
            obj.keyframe_insert(data_path='hide_render', frame=hframe)

        lastframe = frame
        lasthide = hide


def build_bucket(buck: BucketG):
    objname = 'Bucket ' + buck.candidatecode
    if 'Bucket' not in bpy.data.meshes:
        obj = build_first_mesh('Bucket', buck.width, buck.heightratio, buck.border, 'Bucket Glass')
        obj.name = objname

        # Remove top face
        bpy.ops.object.editmode_toggle()
        for f in bmesh.from_edit_mesh(obj.data).faces:
            f.select = f.index == 5
        bpy.ops.mesh.delete(type='FACE')
        bpy.ops.object.editmode_toggle()

        # Add Solidify Modifier and apply
        bpy.ops.object.modifier_add(type='SOLIDIFY')
        obj.modifiers["Solidify"].offset = 1
        obj.modifiers["Solidify"].thickness = buck.border
        obj.modifiers["Solidify"].use_even_offset = True
        bpy.ops.object.modifier_apply(modifier='Solidify')

        # Unlink object from initial collection
        bpy.data.collections['Collection'].objects.unlink(obj)
    else:
        obj = bpy.data.objects.new(objname, bpy.data.meshes['Bucket'])

    bpy.data.collections['Buckets'].objects.link(obj)  # Move to collections
    bpy.data.collections['Freestyle'].objects.link(obj)

    build_location_animation(obj, buck)


def build_bucket_fill(buck: BucketG):
    objname = 'Bucket Fill ' + buck.candidatecode
    if 'Bucket Fill' not in bpy.data.meshes:
        obj = build_first_mesh('Bucket Fill', buck.width, buck.votefillheightratio, 0, 'Vote Material')
        obj.name = objname

        # Unlink object from initial collection
        bpy.data.collections['Collection'].objects.unlink(obj)
    else:
        obj = bpy.data.objects.new(objname, bpy.data.meshes['Bucket Fill'])

    bpy.data.collections['Buckets'].objects.link(obj)  # Move to collections
    obj['Votes'] = 0.0
    obj.location = [0, 0, buck.border]
    obj.parent = bpy.data.objects['Bucket ' + buck.candidatecode]

    add_driver(obj, 'scale', 2, 'Votes', 'var')  # Add Fill Driver

    build_fill_animation(obj, buck)


def build_bucket_sign(buck: BucketG):
    location = (0, buck.width / 2 + buck.border, buck.width * buck.heightratio + 0.15)
    bpy.ops.object.text_add(radius=0.18, location=location, rotation=(pi/2, 0, 0))
    obj = bpy.context.object  # Assign Object
    obj.name = 'Bucket Sign ' + buck.candidatecode
    text = obj.data
    text.name = obj.name
    text.body = buck.candidatename.replace(' ', '\n')
    text.align_x = 'CENTER'
    text.align_y = 'BOTTOM'
    text.resolution_u = 8
    text.extrude = 0.005
    bpy.context.object.data.bevel_depth = 0.002
    bpy.context.object.data.bevel_resolution = 1

    obj.data.materials.append(bpy.data.materials['Text Material'])

    bpy.data.collections['Collection'].objects.unlink(obj)
    bpy.data.collections['Buckets'].objects.link(obj)  # Move to collections
    obj.parent = bpy.data.objects['Bucket ' + buck.candidatecode]


def build_vb(vb: VoteBaseG):
    objname = 'VB ' + vb.uid
    if 'VB' not in bpy.data.meshes:
        obj = build_first_mesh('VB', vb.width, vb.heightratio, 0, 'Vote Material')
        obj.name = objname

        # Unlink object from initial collection
        bpy.data.collections['Collection'].objects.unlink(obj)
    else:
        obj = bpy.data.objects.new(objname, bpy.data.meshes['VB'])

    bpy.data.collections['Vote Bases'].objects.link(obj)  # Move to collections
    obj.location = vb.location

    add_driver(obj, 'scale', 2, 'Votes', 'var')  # Add Drivers

    build_fill_animation(obj, vb)


def build_vf(vf: VoteFractionG):
    objname = 'VF {} {}'.format(vf.voterid, vf.candidatecode)
    obj = bpy.data.objects.new(objname, bpy.data.meshes['VB'])

    bpy.data.collections['Vote Fractions'].objects.link(obj)  # Move to collections

    add_driver(obj, 'scale', 2, 'Votes', 'var')  # Add Drivers

    build_location_animation(obj, vf)
    build_fill_animation(obj, vf)


def build_tracking(viewbase: VoteBaseG):
    bpy.ops.mesh.primitive_plane_add(size=viewbase.width * 3)
    obj = bpy.context.object
    obj.name = 'Tracking Board'
    obj.data.name = 'Tracking Board'
    obj.data.materials.append(bpy.data.materials['Board Material'])
    obj.location = viewbase.location

    bpy.ops.object.modifier_add(type='SOLIDIFY')
    obj.modifiers['Solidify'].offset = -1
    obj.modifiers['Solidify'].thickness = 0.02
    obj.modifiers['Solidify'].use_even_offset = True
    bpy.ops.object.modifier_apply(modifier='Solidify')

    bpy.ops.object.modifier_add(type='BEVEL')
    obj.modifiers['Bevel'].width = 0.003
    bpy.ops.object.modifier_apply(modifier='Bevel')

    bpy.data.collections['Collection'].objects.unlink(obj)
    bpy.data.collections['Vote Bases'].objects.link(obj)  # Move to collections


def create_materials():
    # Vote Material
    mat = bpy.data.materials['Material']
    mat.name = 'Vote Material'
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 0, 0, 1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7

    # Bucket Material
    mat = bpy.data.materials.new('Bucket Glass')
    mat.use_nodes = True
    mat.use_screen_refraction = True

    nodes = mat.node_tree.nodes
    nodes.remove(nodes.get('Principled BSDF'))
    newnode = nodes.new('ShaderNodeBsdfGlass')
    newnode.inputs['Color'].default_value = (0.7, 0.9, 1, 1)
    newnode.inputs['Roughness'].default_value = 0.25
    newnode.inputs['IOR'].default_value = 1
    mat.node_tree.links.new(nodes[0].inputs[0], newnode.outputs[0])

    # Text Material
    mat = bpy.data.materials.new('Text Material')
    mat.diffuse_color = (0.05, 0.05, 0.05, 1)
    mat.roughness = 0.9

    # Board Material
    mat = bpy.data.materials.new('Board Material')
    mat.diffuse_color = (0.2, 0.2, 0.2, 1)
    mat.roughness = 0.8


def main(usegroups, reactivationmode, viewid):
    bpy.data.objects['Cube'].select_set(True)
    bpy.ops.object.delete()

    collection = bpy.data.collections.new('Buckets')
    bpy.context.scene.collection.children.link(collection)
    collection = bpy.data.collections.new('Vote Bases')
    bpy.context.scene.collection.children.link(collection)
    collection = bpy.data.collections.new('Vote Fractions')
    bpy.context.scene.collection.children.link(collection)
    collection = bpy.data.collections.new('Freestyle')
    bpy.context.scene.collection.children.link(collection)

    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.9, 0.9, 1)

    create_materials()

    stvblender = build_from_cli(usegroups, reactivationmode, viewid)
    for bucket in stvblender.buckets:
        build_bucket(bucket)
        build_bucket_fill(bucket)
        build_bucket_sign(bucket)

    for vb in stvblender.votebases:
        build_vb(vb)
        if vb.uid == viewid:
            build_tracking(vb)

    for vf in stvblender.votefractions:
        build_vf(vf)

    cam = bpy.data.objects['Camera']
    cam.location = [0, -9, 5]
    cam.rotation_euler = [1.1, 0, 0]
    cam.data.lens = 25

    scene = bpy.context.scene
    scene.render.use_freestyle = True
    lineset = bpy.context.scene.view_layers["View Layer"].freestyle_settings.linesets["LineSet"]
    lineset.select_by_collection = True
    lineset.collection = bpy.data.collections['Freestyle']
    lineset.collection_negation = 'INCLUSIVE'  # Exclude Sign from freestyle
    scene.render.line_thickness = 0.5
    scene.eevee.use_ssr = True
    scene.eevee.use_ssr_refraction = True
    scene.eevee.use_ssr_halfres = False
    scene.render.resolution_percentage = 75
    scene.render.fps = 30
    scene.render.filepath = "./Renders/"
    scene.frame_end = stvblender.lastframe + 150

    bpy.ops.scene.new(type='EMPTY')
    scene = bpy.context.scene
    scene.name = 'Scene with Text'
    scene.sequence_editor_create()
    sequences = scene.sequence_editor.sequences
    sequences.new_scene('Main Animation', bpy.data.scenes['Scene'], 1, 1)

    for ts in stvblender.textstrips:
        ov = ts.overlay
        seq = sequences.new_effect(ov.name + ' Overlay', 'TEXT', ov.channel, ts.startframe, frame_end=ts.endframe)
        seq.location = (ov.xpos, ov.ypos)
        seq.align_x = ov.xalign
        seq.align_y = ov.yalign
        seq.font_size = ov.size
        seq.text = ts.text
        seq.color = ts.color
        seq.use_shadow = True
        seq.blend_type = 'ALPHA_OVER'


if __name__ == '__main__':
    main(True, True, 'independent')
