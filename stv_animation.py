import bpy
import bmesh

from blender_interface import BucketG, VoteBaseG, VoteFractionG, build_from_shell


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


def build_vb(vb: VoteBaseG):
    objname = 'VB ' + vb.voterid
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
    newnode.inputs['Color'].default_value = (.7, .9, 1, 1)
    newnode.inputs['Roughness'].default_value = 0.25
    newnode.inputs['IOR'].default_value = 1
    mat.node_tree.links.new(nodes[0].inputs[0], newnode.outputs[0])


def main():
    bpy.data.objects['Cube'].select_set(True)
    bpy.ops.object.delete()

    collection = bpy.data.collections.new('Buckets')
    bpy.context.scene.collection.children.link(collection)
    collection = bpy.data.collections.new('Vote Bases')
    bpy.context.scene.collection.children.link(collection)
    collection = bpy.data.collections.new('Vote Fractions')
    bpy.context.scene.collection.children.link(collection)

    create_materials()

    buckets, votebases, votefractions, totalframes = build_from_shell(True, True)
    for bucket in buckets:
        build_bucket(bucket)
        build_bucket_fill(bucket)

    for vb in votebases:
        build_vb(vb)

    for vf in votefractions:
        build_vf(vf)

    cam = bpy.data.objects['Camera']
    cam.location = [0, -9, 5]
    cam.rotation_euler = [1, 0, 0]
    cam.data.lens = 25

    scene = bpy.context.scene
    scene.eevee.use_ssr = True
    scene.eevee.use_ssr_refraction = True
    scene.eevee.use_ssr_halfres = False
    scene.render.resolution_percentage = 75
    scene.render.fps = 30
    scene.render.filepath = "/home/robert/Desktop/STV/"
    scene.frame_end = totalframes + 24


if __name__ == '__main__':
    main()
