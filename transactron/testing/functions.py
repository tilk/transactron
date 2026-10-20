import amaranth.lib.data as data


__all__ = ["MethodData", "data_const_to_dict"]


type MethodData = data.Const[data.StructLayout]


def data_const_to_dict(c: data.Const[data.Layout]):
    ret = {}
    for k, _ in c.shape():
        v = c[k]
        if isinstance(v, data.Const):
            v = data_const_to_dict(v)
        ret[k] = v
    return ret
