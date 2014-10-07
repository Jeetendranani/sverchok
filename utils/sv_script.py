# support classes for SvScript node MK2
# some utility functions

import abc
# basic class for Script Node MK2   
from .sv_itertools import sv_zip_longest

import itertools

'''
TEMPORARY DOCUMENTATION

Every SvScript needs a self.process() function.
The node can be access via self.node
 
Procsess won't be called unless all sockets without a default are conneted
 
inputs = (socket_type, socket_name, default, ... )
outputs = (socket_type, socket_name, ... )
the ... can be additional parameters for specific node script.

if the function provides a draw_buttons it will be called
the same with update, but then the node is also responsible for calling process 

if the .name parameter is set it will used as a label otherwise the class will be used
'''

# base method for all scripts
class SvScript(metaclass=abc.ABCMeta):
    def get_data(self):
        '''Support function to get raw data from node'''
        node = self.node
        if node:
            return [(s.name, s.sv_get(deepcopy=False), s.bl_idname) for s in node.inputs]
        else:
            raise Error
    
    def set_data(self, data):
        '''
        Support function to set data
        '''
        node = self.node
        for name, d in data.items():
            node.outputs[name].sv_set(d)
    
    @abc.abstractmethod
    def process(self):
        return

def recursive_depth(l):
    if isinstance(l, (list, tuple)) and l:
        return 1 + recursive_depth(l[0])
    elif isinstance(l, (int, float, str)):
        return 0
    else:
        return None

        
# this method will be renamed and moved
        
def atomic_map(f, args):
    # this should support different methods for finding depth
    types = tuple(isinstance(a, (int, float)) for a in args)
    
    if all(types):
        return f(*args)
    elif any(types):
        tmp = [] 
        tmp_app = tmp.append
        for t,a in zip(types, args):
            if t:
                tmp_app((a,))
            else:
                tmp_app(a)
        return atomic_map(f, tmp)
    else:
        res = []
        res_app = res.append
        for z_arg in sv_zip_longest(*args):
            res_app(atomic_map(f, z_arg))
        return res


# not ready at all.
def v_map(f,*args, kwargs):
    def vector_map(f, *args):
        # this should support different methods for finding depth   
        types = tuple(isinstance(a, (int, float)) for a in args)
        if all(types):
            return f(*args)
        elif any(types):
            tmp = [] 
            tmp_app
            for t,a in zip(types, args):
                if t:
                    tmp_app([a])
                else:
                    tmp_app(a)
            return atomic_map(f, *tmp)
        else:
            res = []
            res_app = res.append
            for z_arg in sv_zip_longest(*args):
                res_app(atomic_map(f,*z_arg))
            return res
    

    
class SvScriptAuto(SvScript, metaclass=abc.ABCMeta):
    """ 
    f(x,y,z,...n) -> t
    with unlimited depth
    """

    @staticmethod
    @abc.abstractmethod
    def function(*args):
        return
        
    def process(self):
        data = self.get_data()
        tmp = [d for name, d, stype in data]
        res = atomic_map(self.function, tmp)
        name = self.node.outputs[0].name
        self.set_data({name:res})

class SvScriptSimpleGenerator(SvScript, metaclass=abc.ABCMeta):
    """
    Simple generator script template
    outputs must be in the following format
    (socket_type, socket_name, socket_function)
    where socket_function will be called for linked socket production
    for each set of input parameters
    """
    def process(self):
        inputs = self.node.inputs
        outputs = self.node.outputs
        
        data = [s.sv_get()[0] for s in inputs]

        for socket, ref in zip(outputs, self.outputs):
            if socket.links:
                func = getattr(self, ref[2])
                out = tuple(itertools.starmap(func, sv_zip_longest(*data)))
                socket.sv_set(out)

class SvScriptSimpleFunction(SvScript, metaclass=abc.ABCMeta):
    """
    Simple f(x0, x1, ... xN) -> y0, y1, ... ,yM
    
    """
    @abc.abstractmethod
    def function(*args, depth=None):
        return 
        
    def process(self):
        inputs = self.node.inputs
        outputs = self.node.outputs
        
        data = [s.sv_get() for s in inputs]
        # this is not used yet, I don't think flat depth is the right long
        # term approach, but the data tree should be easily parseable
        depth = tuple(map(recursive_depth, data))
        links = [s.links for s in outputs]
        result = [[] for d in data]
        for d in zip(*data):
            res = self.function(*d, depth=depth)
            for i, r in enumerate(res):
                result[i].append(r)
        for link, res, socket in zip(links, result, outputs):
            if link:
                socket.sv_set(res)
                    
