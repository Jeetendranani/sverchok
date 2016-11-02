# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import ast
import traceback

import bpy
from bpy.props import StringProperty, BoolProperty, IntProperty, FloatProperty
import mathutils
from mathutils import Matrix, Vector, Euler, Quaternion, Color

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import Matrix_generate, updateNode, node_id, replace_socket

def parse_to_path(p):
    '''
    Create a path and can be looked up easily.
    Return an array of tuples with op type and value
    ops are:
    name - global name to use
    attr - attribute to get using getattr(obj,attr)
    key - key for accesing via obj[key]
    '''
    
    if isinstance(p, ast.Attribute):
        return parse_to_path(p.value)+[("attr", p.attr)] 
    elif isinstance(p, ast.Subscript):
        if isinstance(p.slice.value, ast.Num):
            return  parse_to_path(p.value) + [("key", p.slice.value.n)]
        elif isinstance(p.slice.value, ast.Str):
            return parse_to_path(p.value) + [("key", p.slice.value.s)] 
    elif isinstance(p, ast.Name):
        return [("name", p.id)]
    else:
        raise NameError
        
def get_object(path):
    '''
    access the object speciefed from a path
    generated by parse_to_path
    will fail if path is invalid
    '''
    curr_object = globals()[path[0][1]]
    for t, value in path[1:]:
        if t == "attr":
            curr_object = getattr(curr_object, value)
        elif t == "key":
            curr_object = curr_object[value]
    return curr_object

def apply_alias(eval_str):
    '''
    apply standard aliases
    will raise error if it isn't an bpy path
    '''
    if not eval_str.startswith("bpy."):
        for alias, expanded in aliases.items():
            if eval_str.startswith(alias):
                eval_str = eval_str.replace(alias, expanded, 1)
                break
        if not eval_str.startswith("bpy."):
            raise NameError
    return eval_str

def wrap_output_data(tvar):
    '''
    create valid sverchok socket data from an object
    from ek node
    '''
    if isinstance(tvar, (Vector, Color)):
        data = [[tvar[:]]]
    elif isinstance(tvar, Matrix):
        data = [[r[:] for r in tvar[:]]]
    elif isinstance(tvar, (Euler, Quaternion)):
        tvar = tvar.to_matrix().to_4x4()
        data = [[r[:] for r in tvar[:]]]
    elif isinstance(tvar, list):
        data = [tvar]
    elif isinstance(tvar, (int, float)):
        data = [[tvar]]
    else:
        data = tvar
    return data

def assign_data(obj, data):
    '''
    assigns data to the object
    '''
    if isinstance(obj, (int, float)):
        # doesn't work
        obj = data[0][0]
    elif isinstance(obj, (Vector, Color)):
        obj[:] = data[0][0] 
    elif isinstance(obj, (Matrix, Euler, Quaternion)):
        mats = Matrix_generate(data)
        mat = mats[0]
        if isinstance(obj, Euler):
            eul = mat.to_euler(obj.order)
            obj[:] = eul
        elif isinstance(obj, Quaternion):
            quat = mat.to_quaternion()
            obj[:] = quat 
        else: #isinstance(obj, Matrix)
            obj[:] = mat
    else: # super optimistic guess
        obj[:] = type(obj)(data[0][0])


aliases = {
    "c": "bpy.context",
    "C" : "bpy.context",
    "scene": "bpy.context.scene",
    "data": "bpy.data",
    "D": "bpy.data",
    "objs": "bpy.data.objects",
    "mats": "bpy.data.materials",
    "meshes": "bpy.data.meshes",
    "texts": "bpy.data.texts"
}  

types = {
    int: "StringsSocket",
    float: "StringsSocket",
    str: "StringsSocket", # I WANT A PROPER TEXT SOCKET!!!
    mathutils.Vector:"VerticesSocket",
    mathutils.Color:"VerticesSocket",
    mathutils.Matrix: "MatrixSocket",
    mathutils.Euler: "MatrixSocket", 
    mathutils.Quaternion: "MatrixSocket",
}

class SvGetPropNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Get property '''
    bl_idname = 'SvGetPropNode'
    bl_label = 'Get property'
    bl_icon = 'FORCE_VORTEX'

    bad_prop = BoolProperty(default=False)

    def verify_prop(self, context):
        try:
            obj = self.obj
        except:
            traceback.print_exc()        
            self.bad_prop = True
            return
        self.bad_prop = False
        s_type = types.get(type(obj))
        outputs = self.outputs
        if s_type and outputs:
            replace_socket(outputs[0], s_type)
        elif s_type:
            outputs.new(s_type, "Data")


    prop_name = StringProperty(name='', update=verify_prop)

    @property
    def obj(self):
        eval_str = apply_alias(self.prop_name)
        ast_path = ast.parse(eval_str)
        path = parse_to_path(ast_path.body[0].value)
        return get_object(path)
    
    def draw_buttons(self, context, layout):
        layout.alert = self.bad_prop
        layout.prop(self, "prop_name", text="")

    def process(self):
        self.outputs[0].sv_set(wrap_output_data(self.obj))        


class SvSetPropNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Set property '''
    bl_idname = 'SvSetPropNode'
    bl_label = 'Set property'
    bl_icon = 'FORCE_VORTEX'
    
    
    ok_prop = BoolProperty(default=False)
    bad_prop = BoolProperty(default=False)

    
    @property
    def obj(self):
        eval_str = apply_alias(self.prop_name)
        ast_path = ast.parse(eval_str)
        path = parse_to_path(ast_path.body[0].value)
        return get_object(path)
        
    def verify_prop(self, context):
        try:
            obj = self.obj
        except:
            traceback.print_exc()
            self.bad_prop = True
            return
        self.bad_prop = False

        s_type = types.get(type(obj))
        inputs = self.inputs
        p_name = {float: "float_prop",
                 int: "int_prop"}.get(type(obj),"")
        if inputs and s_type: 
            socket = replace_socket(inputs[0], s_type)
            socket.prop_name = p_name
        elif s_type:
            inputs.new(s_type, "Data").prop_name = p_name
        if s_type == "VerticesSocket":
            inputs[0].use_prop = True
        
    prop_name = StringProperty(name='', update=verify_prop)
    float_prop = FloatProperty(update=updateNode, name="x")
    int_prop = IntProperty(update=updateNode, name="x")
    
    def draw_buttons(self, context, layout):
        layout.alert = self.bad_prop
        layout.prop(self, "prop_name", text="")

    def process(self):
        data = self.inputs[0].sv_get()
        eval_str = apply_alias(self.prop_name)
        ast_path = ast.parse(eval_str)
        path = parse_to_path(ast_path.body[0].value)
        obj = get_object(path)
        if isinstance(obj, (int, float)):
            obj = get_object(path[:-1])
            p_type, value = path[-1]
            if p_type == "attr":
                setattr(obj, value, data[0][0])
            else: 
                obj[value] = data[0][0]
        else:
            assign_data(obj, data)

            
def register():
    bpy.utils.register_class(SvSetPropNode)
    bpy.utils.register_class(SvGetPropNode)


def unregister():
    bpy.utils.unregister_class(SvSetPropNode)
    bpy.utils.unregister_class(SvGetPropNode)

