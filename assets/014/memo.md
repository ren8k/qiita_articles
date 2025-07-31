https://chatgpt.com/c/6880347b-f594-8330-b188-5b0f0031ea3c

https://speakerdeck.com/yokawasa/ai-ready-api-designing-mcp-and-apis-in-the-ai-era

## MCP Inspector

`npx @modelcontextprotocol/inspector`

https://github.com/modelcontextprotocol/inspector

https://zenn.dev/ohke/articles/mcp-quick-study-2025
https://blog.msysh.me/posts/2025/07/amazon-bedrock-agentcore-runtime-mcp-server-deployment.html

※node js を download する必要あり．

https://nodejs.org/ja/download

## OpenAI

Strands 内部では，OpenAI の Response API を利用していないようなので，o3 で web search tool を利用することができなかった．今回は，OpenAI が提供している Response API を利用している．

### response api

https://platform.openai.com/docs/api-reference/responses/create

### web search tool

https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses

## メモ

- 実行環境をメモしておくこと．
- agentcore configure で， `--codebuild`オプションが利用できることも確認したい

## MCP

以下が tool の本質．

```
print("=" * 50)
print(tool_result.model_dump_json(indent=2))
print("=" * 50)
```

### Bug

mcp==1.2.1 でも以下．

```
((pytorch) ) ubuntu@ip-172-30-4-2:~/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client$ uv run src/mcp_client_remote.py
warning: `VIRTUAL_ENV=/opt/pytorch` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead

Connect to: https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A684452318078%3Aruntime%2Ftestagent_v0-LPfkGv3y4T/invocations?qualifier=DEFAULT

🔄 Initializing MCP session...
Error parsing JSON response
Traceback (most recent call last):
  File "/home/ubuntu/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client/.venv/lib/python3.12/site-packages/mcp/client/streamable_http.py", line 304, in _handle_json_response
    message = JSONRPCMessage.model_validate_json(content)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ubuntu/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client/.venv/lib/python3.12/site-packages/pydantic/main.py", line 746, in model_validate_json
    return cls.__pydantic_validator__.validate_json(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core._pydantic_core.ValidationError: 1 validation error for JSONRPCMessage
  Invalid JSON: expected `,` or `}` at line 1 column 122 [type=json_invalid, input_value=b'{"jsonrpc":"2.0","error...4e8a-b1f6-8e5ccee975ae}', input_type=bytes]
    For further information visit https://errors.pydantic.dev/2.11/v/json_invalid


```

### Bug (streamable http client)

````
((pytorch) ) ubuntu@ip-172-30-4-2:~/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client$ uv run src/agent2.py
warning: `VIRTUAL_ENV=/opt/pytorch` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
🌐 MCPエンドポイント: https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A684452318078%3Aruntime%2Ftestagent_v1-stSLgz4P5S/invocations?qualifier=DEFAULT
🔍 利用可能なツールを取得中...
MCPの実装方法について調べてみますね。
Tool #1: openai_o3_search
追加でPython MCPの具体的な実装手順やコード例について詳しく調べてみます。
Tool #2: openai_o3_search
MCPの実装方法について詳しく調べました。以下にPythonを使ったMCPの実装方法をまとめます。

## MCP（Model Context Protocol）とは

MCPは、AIモデルと外部アプリケーションやデータソースを効率的に接続するためのオープンプロトコルです。Anthropic社によって開発され、AIモデルがさまざまなツールやデータと統合する際の標準的な方法を提供します。

## 基本構成要素

- **MCPホスト**: Claude DesktopやIDEなど、MCPを通じてデータにアクセスするプログラム
- **MCPクライアント**: サーバーと1対1の接続を維持するプロトコルクライアント
- **MCPサーバー**: 標準化されたMCPを通じて特定の機能を提供する軽量なプログラム
- **ローカルデータソース**: コンピュータ上のファイルやデータベース、サービスなど
- **リモートサービス**: インターネット経由で利用可能な外部システム（APIなど）

## Pythonでの実装手順

### 1. MCPのインストール

```bash
pip install "mcp[cli]"
````

### 2. MCP サーバーの実装

FastMCP を使用した基本的なサーバーの例：

```python
# server.py
from mcp.server.fastmcp import FastMCP

# MCPサーバーの作成
mcp = FastMCP("Demo")

# 足し算を行うツールの追加
@mcp.tool()
def add(a: int, b: int) -> int:
    """2つの数値を加算します"""
    return a + b

# 動的な挨拶リソースの追加
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """個人向けの挨拶を取得します"""
    return f"こんにちは、{name}さん！"
```

### 3. MCP クライアントの実装

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_mcp_client():
    """MCPクライアントを起動し、サーバーと対話するメイン関数"""
    server_params = StdioServerParameters(
        command='python',
        args=['server.py']
    )

    async with stdio_client(server_params) as (reader, writer):
        async with ClientSession(client_name="my-python-client", client_version="0.1.0") as session:
            # セッションの初期化やツールの呼び出しをここで行います
            pass

asyncio.run(run_mcp_client())
```

### 4. FastAPI を使用した実装例

```python
from fastapi import FastAPI, Request
from google.protobuf.json_format import ParseDict, MessageToDict
import your_protobuf_pb2 as pb2  # Protobufコンパイル結果

app = FastAPI()

@app.post("/infer")
async def infer(request: Request):
    raw_body = await request.body()
    try:
        request_data = await request.json()
        inference_request = ParseDict(request_data, pb2.InferenceRequest())
    except Exception as e:
        return {"error": f"Invalid request format: {e}"}, 400

    # モデル推論のロジックをここに実装
    output_data = b"processed_" + inference_request.input_data

    response = pb2.InferenceResponse(
        output_data=output_data,
        request_id=inference_request.context.request_id if inference_request.HasField("context") else "",
        model_name=inference_request.model_name
    )

    return MessageToDict(response)
```

### 5. サーバーの起動とテスト

```bash
# MCPサーバーのインストールと起動
mcp install server.py

# MCP Inspectorでのテスト
mcp dev server.py
```

## セキュリティ対策

MCP は発展途上のプロトコルであり、セキュリティ対策が重要です。以下の点に注意してください：

- MCP サーバーは外部リソースへのアクセス権を持つため、信頼できる提供元からのサーバーを使用
- 内容を十分に確認してから実装
- 適切な認証・認可の仕組みを導入

MCP を使用することで、AI アプリケーションと外部ツールやデータソースとの統合が容易になり、開発効率が向上します。

Session termination failed: 404
((pytorch) ) ubuntu@ip-172-30-4-2:~/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client$

```



https://github.com/modelcontextprotocol/python-sdk/issues?q=is%3Aissue%20state%3Aopen%20streamable%20http%20timeout

https://github.com/modelcontextprotocol/python-sdk/issues/1010?plain=1
https://github.com/modelcontextprotocol/python-sdk/pull/1008
https://github.com/modelcontextprotocol/python-sdk/issues/1010?plain=1
```
