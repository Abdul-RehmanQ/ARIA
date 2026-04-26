from agentscope.tool import Toolkit
tools = Toolkit()
def action(desc=None):
    def dec(f):
        if desc and not f.__doc__: f.__doc__ = desc
        tools.register_tool_function(f)
        return f
    return dec
tools.action = action
@tools.action('Test')
def myfunc(a: int):
    pass
print(tools.get_json_schemas())
