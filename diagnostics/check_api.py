from agentscope.tool import Toolkit
print('execute:', hasattr(Toolkit, 'execute'))
print('get_tool_schemas:', hasattr(Toolkit, 'get_tool_schemas'))
print('get_json_schemas:', hasattr(Toolkit, 'get_json_schemas'))
tools = Toolkit()
@tools.register_tool_function
def test(): pass
print('decorator returned:', type(test))
