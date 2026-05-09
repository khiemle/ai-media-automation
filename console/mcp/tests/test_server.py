from console.mcp.server import build_server


def test_build_server_returns_fastmcp_with_no_tools_yet():
    server = build_server(register=[])
    # tools dict is exposed by FastMCP via list_tools()
    assert hasattr(server, "list_tools")


def test_build_server_registers_passed_callbacks():
    calls = []

    def register_one(server):
        calls.append(server)

    build_server(register=[register_one])
    assert len(calls) == 1
