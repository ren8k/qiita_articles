---
title: Bedrock AgentCore Runtime で Remote MCP サーバー (OpenAI o3 Web search) をデプロイし，Strands Agents から利用する
tags:
  - AWS
  - bedrock
  - Agent
  - MCP
  - OpenAI
private: false
updated_at: ""
id: null
organization_url_name: nttdata
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスソリューション事業部の [@ren8k](https://qiita.com/ren8k) です．

2025/07/17 に，AWS の新サービスである [Amazon Bedrock AgentCore がプレビューで利用可能になりました．](https://aws.amazon.com/jp/about-aws/whats-new/2025/07/amazon-bedrock-agentcore-preview/)

AgentCore は，AI Agent の運用を AWS 上で容易に実現するための PaaS であり，Building Block として利用可能な 7 種類の機能 (Runtime, Identity, Memory, Code Interpreter, Browser, Gateway, Observability)を提供しています．特に，AgentCore Runtime は，コンテナ化された AI Agent をサーバーレスでデプロイ可能な機能であり，実際に利用した CPU リソースに応じた課金が行われるので，コスト効率が良いです．なお，AI Agent は任意のフレームワークで実装して問題ございません．

また，AgentCore Runtime では，AI Agent 本体だけでなく，Cognito による OAuth 認証付きの，[Remote MCP サーバーをデプロイ](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)することが可能です．本稿では，本機能を深く掘り下げ，実際に Remote MCP サーバーをデプロイし，Strands Agents から利用する方法について解説します．

## 検証内容

OpenAI o3 と Web Search tool による詳細な検索を行うための MCP（Model Context Protocol）サーバーを実装しました．フレームワークとしては，OpenAI が提供する Response API を利用しました．そして，bedrock-agentcore-starter-toolkit を利用し，実装した MCP サーバーを AgentCore Runtime に Remote MCP サーバーとしてデプロイしました．最後に，Strands Agents から streamable HTTP で Remote MCP サーバーに接続し，利用可能なことを検証しました．

![architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/458ae1be-3f7a-4e1c-8cf9-8fecf629d9e5.png)

## 実装内容

実装は以下リポジトリにて公開しております．

https://github.com/ren8k/aws-bedrock-agentcore-runtime-remote-mcp

以下がディレクトリ構成です．MCP Client, MCP Server, および，Cognito や IAM ロールのセットアップを行うコードを実践的に利用する想定で実装し，各ディレクトリで管理しております．

```
.
├── README.md
├── .env.sample
├── mcp_client
├── mcp_server
└── setup
```

なお，`.env.sample` をコピーして `.env` を作成し，後述する手順にて環境変数を設定してください．

## 実行環境

開発環境を以下に示します．本検証では，ARM アーキテクチャベースの EC2 インスタンスで開発・実行しています．AgentCore Runtime の仕様上，Docker イメージを ARM64 アーキテクチャ向けにビルドする必要があるためです．AMI として [AWS Deep Learning AMI](https://docs.aws.amazon.com/dlami/latest/devguide/what-is-dlami.html) を利用しました．本 AMI には，Docker や AWS CLI がプリインストールされており，非常に便利です．EC2 には，[uv](https://docs.astral.sh/uv/getting-started/installation/) をインストールしております．

- OS: Ubuntu Server 24.04 LTS
- AMI: 01e1d8271212cd19a (Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.7)
- Instance Type: m8g.xlarge (ARM)
- Docker version: 28.3.2, build 578ccf6
- uv version: 0.8.3
- default region: us-west-2

参考に，Local 上の VSCode から EC2 へ接続し，簡単に開発環境を構築する手順を以下のリポジトリにまとめております．是非ご利用ください．

https://github.com/ren8k/aws-ec2-devkit-vscode

## 手順

以下の各 Step を順に実行し，Remote MCP サーバーの構築と利用を行います．

- Step 1. MCP サーバーの作成
- Step 2. Cognito と IAM ロールの準備
- Step 3. MCP サーバーを AgentCore Runtime にデプロイ
- Step 4. Remote MCP サーバーの動作確認
- Step 5. Strands Agents から Remote MCP サーバーを利用
- Step 6. (おまけ) Claude Code から Remote MCP サーバーを利用

### Step 1. MCP サーバーの作成

リポジトリの `mcp_server` ディレクトリに移動し，`uv sync` を実行することで，`mcp_server` ディレクトリ内のコードの実行に必要なパッケージをインストールして下さい．また，`.env` ファイルに，`OPENAI_API_KEY` を設定してください．

#### Step 1-1. OpenAI o3 Web Search MCP サーバーの実装

[OpenAI o3](https://platform.openai.com/docs/models/o3) と [Web search](https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses) を利用し，最新情報を調査・整理するための MCP サーバーを Python で実装しました．o3 を利用することで，多段階にわたる推論と Web 検索を組み合わせた高度な情報検索が可能になります．

MCP サーバーの実装コードを以下に示します．トランスポートとして Streamable HTTP を利用するため，`mcp.run()` の引数に `transport="streamable-http"` を指定します．なお，AgentCore Runtime 上に MCP サーバーをホストする要件として，[以下の 2 点を満たす必要があります．](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html#runtime-mcp-how-it-works)

- (1) `FastMCP` の引数 `host` を `0.0.0.0` に設定
- (2) `FastMCP` の引数 `stateless_http` を `True` に設定

(1) は，MCP サーバーコンテナが `0.0.0.0:8000/mcp` で利用可能である必要があるためです． (2) は，AgentCore Runtime がデフォルトでセッション分離を提供するためです．

<details open><summary>コード (折りたためます)</summary>

```python: mcp_server/src/mcp_server.py
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from pydantic import Field

INSTRUCTIONS = """
- You must answer the question using web_search tool.
- You must respond in japanese.
"""

mcp = FastMCP(name="openai-web-search-mcp-server", host="0.0.0.0", stateless_http=True)


@mcp.tool()
def openai_o3_web_search(
    question: str = Field(
        description="""Question text to send to OpenAI o3. It supports natural language queries.
        Write in Japanese. Be direct and specific about your requirements.
        Avoid chain-of-thought instructions like "think step by step" as o3 handles reasoning internally."""
    ),
) -> str:
    """An AI agent with advanced web search capabilities. Useful for finding the latest information,
    troubleshooting errors, and discussing ideas or design challenges. Supports natural language queries.

    Args:
        question: The search question to perform.

    Returns:
        str: The search results with advanced reasoning and analysis.
    """
    try:
        client = OpenAI()
        response = client.responses.create(
            model="o3",
            tools=[{"type": "web_search_preview"}],
            instructions=INSTRUCTIONS,
            input=question,
        )
        return response.output_text
    except Exception as e:
        return f"Error occurred: {str(e)}"


@mcp.tool()
def greet_user(
    name: str = Field(description="The name of the person to greet"),
) -> str:
    """Greet a user by name
    Args:
        name: The name of the user.
    """
    return f"Hello, {name}! Nice to meet you. This is a test message."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

> コード中のプロンプトの一部は[本リポジトリのコード](https://github.com/yoshiko-pg/o3-search-mcp/blob/main/index.ts)を参考にさせていただきました．

</details>

:::note info
[Strands Agents](https://github.com/strands-agents/sdk-python) を利用しても，[OpenAI のモデルの推論](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)は可能です．しかし，Strands Agents の [Python SDK](https://github.com/strands-agents/sdk-python) の内部実装 ([openai.py](https://github.com/strands-agents/sdk-python/blob/3f4c3a35ce14800e4852998e0c2b68f90295ffb7/src/strands/models/openai.py#L347)) を確認すると[Chat Completions API](https://platform.openai.com/docs/api-reference/chat) が利用されており，o3 で Web search を利用することができません．[Chat Completion API で Web search を利用する](https://platform.openai.com/docs/guides/tools-web-search?api-mode=chat)場合，以下のモデルを利用する必要があるためです．

- gpt-4o-search-preview
- gpt-4o-mini-search-preview

上記の理由のため，本検証では [OpenAI Response API](https://platform.openai.com/docs/api-reference/responses) を利用しています．Response API は，Agent 開発向けに設計された [Chat Completions API](https://platform.openai.com/docs/api-reference/chat) の上位互換の API です．具体的には，[会話の状態](https://platform.openai.com/docs/guides/conversation-state?api-mode=chat)を API 側でステートフルに管理することや，Web search 等の組み込みツールを容易に利用することが可能です．
:::

#### 【コラム】 MCP サーバーの実装上の工夫

##### Tool の引数 (Args) の 説明 (description) について

[MCP 公式ドキュメントの実装例](https://modelcontextprotocol.io/quickstart/server#implementing-tool-execution)では，関数の docstring 中に関数の説明と引数 (Args) の説明を記載しています．

```python:実装例
@mcp.tool()
def my_function(param: str):
    """
    この関数の説明文

    Args:
        param: パラメーターの説明
    """
    # 関数の実装
```

一方，MCP の [Python-SDK](https://github.com/modelcontextprotocol/python-sdk) の内部実装 ([base.py](https://github.com/modelcontextprotocol/python-sdk/blob/49991fd2c78cded9f70e25871a006f9bab693d4b/src/mcp/server/fastmcp/tools/base.py#L59) や [func_metadata.py](https://github.com/modelcontextprotocol/python-sdk/blob/49991fd2c78cded9f70e25871a006f9bab693d4b/src/mcp/server/fastmcp/utilities/func_metadata.py#L212-L238)) を確認すると，関数の docstring の内容をパースせず，Args の引数説明を抽出しておりません．その結果，`session.list_tools()` で得られる tool 定義の `input_schema` (tool の引数情報) の `description` フィールドが欠落してしまいます．

```json:tool 定義 (input_schemaのparamのdescriptionが欠落)
{
  "properties": {
    "param": {
      "title": "Param",
      "type": "string"
    }
  },
  "required": ["param"],
  "title": "my_functionArguments",
  "type": "object"
}
```

なお，本事実は以下の Issue でも言及されています．

https://github.com/modelcontextprotocol/python-sdk/issues/226

tool 定義の `input_schema` の `description` フィールドに説明を設定するためには，以下のように Pydantic の `Field` を利用して引数の説明を記載する必要があります．([func_metadata.py](https://github.com/modelcontextprotocol/python-sdk/blob/49991fd2c78cded9f70e25871a006f9bab693d4b/src/mcp/server/fastmcp/utilities/func_metadata.py#L212-L238) 参照．)

```python:Field を利用
from pydantic import Field

@mcp.tool()
def my_function(
  param: str = Field(description="パラメーターの説明"),
):
    """
    この関数の説明文

    Args:
        param: パラメーターの説明
    """
    # 関数の実装
```

```json:tool 定義 (input_schemaのparamのdescriptionが設定される)
{
  "properties": {
    "param": {
      "description": "パラメーターの説明",
      "title": "Param",
      "type": "string"
    }
  },
  "required": ["param"],
  "title": "my_functionArguments",
  "type": "object"
}
```

[Anthropic の tool use のドキュメント](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use#best-practices-for-tool-definitions)によると，tool の説明に加え，tool の引数の意味や説明を具体的に記述することがベストプラクティスであるとされているため，本実装では，Pydantic の `Field` を利用して引数の説明を記載しております．

https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use#best-practices-for-tool-definitions

##### error 発生時の処理について

エラー発生時，エラー内容を文字列として返却することで，tool の呼び出し元の LLM が，エラーの内容とその解決方法を提示できるようにしております．

```python
try:
    ...
    return response.output_text
except Exception as e:
    return f"Error occurred: {str(e)}"
```

##### OpenAI o3 の 設定について

執筆時点 (2025/07/31) では，OpenAI o3 で Function Calling を利用する場合，tool の利用を強制するための設定である [`tool_choice`](https://platform.openai.com/docs/guides/function-calling?api-mode=chat#tool-choice) を利用できません． (`tool_choice="auto"` の設定でなければなりません．) このため，Response API の引数 `instructions` にて，Web search を必ず実行するように (システムプロンプトとして) 指示しています．

<!-- また，streamable HTTP を利用する場合，MCP 内部の実行に 1 分以上かかると hang してしまう MCP Python SDK の不具合を観測しました．このため，[reasoning を low に設定](https://platform.openai.com/docs/guides/reasoning?api-mode=responses)することで，MCP の処理時間が 1 分以内になるようにしております．（本不具合については後述します．） -->

#### Step 1-2. Local 上での MCP サーバーの動作確認

AgentRuntime へデプロイする前に，ローカル環境で MCP サーバーが正しく動作するか確認します．まず，`mcp_server` ディレクトリ上で以下のコマンドを実行し，MCP サーバーを起動します．

```bash
uv run src/mcp_server.py
```

次に，別のターミナルを開き，`mcp_client` ディレクトリに移動し，`uv sync` を実行します．その後，以下のコードを実行することで，簡易的な MCP クライアントから MCP サーバーに接続して，tool の一覧が取得可能なことを確認します．

```bash
uv run mcp_client/src/mcp_client_local.py
```

<details open><summary>コード (折りたためます)</summary>

```python:mcp_server/src/mcp_server.py
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    mcp_url = "http://localhost:8000/mcp"
    headers = {}

    async with streamablehttp_client(
        mcp_url, headers, timeout=120, terminate_on_close=False
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_result = await session.list_tools()
            print("Available tools:")
            for tool in tool_result.tools:
                print(f"  - {tool.name}: {tool.description}")
                print(f"    InputSchema: {tool.inputSchema.get('properties')}")


if __name__ == "__main__":
    asyncio.run(main())
```

```bash: 出力結果
Available tools:
  - openai_o3_web_search: An AI agent with advanced web search capabilities. Useful for finding the latest information,
    troubleshooting errors, and discussing ideas or design challenges. Supports natural language queries.

    Args:
        question: The search question to perform.

    Returns:
        str: The search results with advanced reasoning and analysis.

    InputSchema: {'properties': {'question': {'description': 'Question text to send to OpenAI o3. It supports natural language queries.\n        Write in Japanese. Be direct and specific about your requirements.\n        Avoid chain-of-thought instructions like "think step by step" as o3 handles reasoning internally.', 'title': 'Question', 'type': 'string'}}, 'required': ['question'], 'title': 'openai_o3_web_searchArguments', 'type': 'object'}
  - greet_user: Greet a user by name
    Args:
        name: The name of the user.

    InputSchema: {'properties': {'name': {'description': 'The name of the person to greet', 'title': 'Name', 'type': 'string'}}, 'required': ['name'], 'title': 'greet_userArguments', 'type': 'object'}
```

</details>

:::note info
[MCP Inspector](https://github.com/modelcontextprotocol/inspector) を利用することで，Web UI 上で MCP サーバーの動作を確認することができます．(実行には [Node.js](https://nodejs.org/ja/download) をダウンロードする必要があります．)

以下のコマンドで MCP Inspector を起動できます．

```bash
npx @modelcontextprotocol/inspector
```

Web UI 上で，Transport Type を `Streamable HTTP` に，URL を `http://localhost:8000/mcp` に設定することで，MCP サーバーと接続できます．
:::

### Step 2. Cognito と IAM ロールの準備

OAuth 認証や，AgentCore Runtime で MCP サーバーを利用するためのリソースを準備します．リポジトリの `setup` ディレクトリに移動し，`uv sync` を実行して下さい．

#### Step 2-1. Amazon Cognito のセットアップ

AgentCore Runtime にデプロイした MCP サーバーの認証方法には，[AWS IAM か OAuth 2.0 を利用できます](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html#runtime-auth-security)．本検証では OAuth 2.0 を利用するため，以下のコードを実行することで，Cognito User Pool と Cognito User を作成後，認証のために必要な以下 3 つの情報を取得します．

- Cognito client ID
- Cognito discovery URL
- JWT (`Bearer_token`)

```bash
uv run src/setup_cognito.py
```

コードの出力結果の `Client_id`，`Discovery_url`，`Bearer_token` (Access Token) を `.env` ファイルの `COGNITO_CLIENT_ID`, `COGNITO_DISCOVERY_URL`, `COGNITO_ACCESS_TOKEN` に記載してください．

<details><summary>コード (折りたたんでます)</summary>

```python:setup/src/setup_cognito.py
import os

import boto3
from dotenv import load_dotenv


def setup_cognito_user_pool(
    username: str, temp_password: str, password: str, region: str = "us-west-2"
) -> dict:
    """
    Set up a new AWS Cognito User Pool with a test user and app client.

    This function creates a complete Cognito setup including:
    - A new User Pool with password policy
    - An app client configured for user/password authentication
    - A test user with permanent password
    - Initial authentication to obtain an access token

    Args:
        username: The username for the test user
        temp_password: The temporary password for initial user creation
        password: The permanent password to set for the user
        region: AWS region where the User Pool will be created (default: us-west-2)

    Returns:
        dict: A dictionary containing:
            - pool_id: The ID of the created User Pool
            - client_id: The ID of the created app client
            - bearer_token: The access token from initial authentication
            - discovery_url: The OpenID Connect discovery URL for the User Pool
    """
    # Initialize Cognito client
    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName="MCPServerPool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]

        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = app_client_response["UserPoolClient"]["ClientId"]

        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword=temp_password,
            MessageAction="SUPPRESS",
        )

        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password=password,
            Permanent=True,
        )

        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            },
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]

        # Return values if needed for further processing
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "bearer_token": bearer_token,
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }

    except Exception as e:
        raise RuntimeError(f"Failed to set up Cognito User Pool: {e}")


def main() -> None:
    load_dotenv()
    username = os.getenv("COGNITO_USERNAME", "testuser")
    temp_password = os.getenv("COGNITO_TMP_PASSWORD", "Temp123!")
    password = os.getenv("COGNITO_PASSWORD", "MyPassword123!")
    if not (username and temp_password and password):
        raise ValueError("Cognito credentials are not set in environment variables.")

    response = setup_cognito_user_pool(username, temp_password, password)
    # Output the required values
    print(f"Pool id: {response.get('pool_id')}")
    print(f"Client ID: {response.get('client_id')}")
    print(f"Discovery URL: {response.get('discovery_url')}")
    print(f"Bearer Token: {response.get('bearer_token')}")


if __name__ == "__main__":
    main()
```

</details>

#### Step 2-2. IAM ロールの作成

以下のコードを実行し，AgentCore Runtime 用の IAM ロールを作成します．作成されるロールは，[AWS 公式ドキュメントに記載のロール](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)と同一です．

ロールでは，指定した Runtime (Remote MCP サーバー) に対する session initialize に必要な権限や，Runtime 作成時に必要な権限 (ECR へのアクセス等)，Runtime 運用時に必要な権限 (CloudWatch Logs への書き込み権限等) が設定されています．また，コードでは，同名の role が存在する場合は削除してから role を再作成するようにしております．

```bash
uv run src/create_role.py
```

コードの出力結果の `Created role` を `.env` ファイルの `ROLE_ARN` に記載してください．

<details><summary>コード (折りたたんでます)</summary>

```python:setup/src/create_role.py
import json
import os
import time

import boto3
from boto3.session import Session
from dotenv import load_dotenv


def create_agentcore_role(agent_name: str) -> dict:
    """Create an IAM role for the agent core.

    Args:
        agent_name (str): The name of the agent.

    Returns:
        dict: The response from the IAM create_role API call.
    """
    client = boto3.client("iam")
    agentcore_role_name = f"agentcore-{agent_name}-role"
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account_id}:*",
                ],
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                "Resource": [f"arn:aws:ecr:{region}:{account_id}:repository/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                },
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*",
                ],
            },
        ],
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": f"{account_id}"},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    },
                },
            }
        ],
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)
    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the AgentCore
    try:
        agentcore_iam_role = client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

        # Pause to make sure role is created
        time.sleep(10)
    except client.exceptions.EntityAlreadyExisAnthropic の tool use のドキュメントによると，tool の説明に加え，tool の引数の意味や説明を具体的に記述することがベストプラクティスであるとされているため，本実装では，Pydantic の Field を利用して引数の説明を記載することにしました。tsException:
        print("Role already exists -- deleting and creating it again")

        # Check and detach inline policies
        inline_policies = client.list_role_policies(
            RoleName=agentcore_role_name, MaxItems=100
        )
        print("inline policies:", inline_policies)
        for policy_name in inline_policies["PolicyNames"]:
            client.delete_role_policy(
                RoleName=agentcore_role_name, PolicyName=policy_name
            )

        # Check and detach managed policies
        managed_policies = client.list_attached_role_policies(
            RoleName=agentcore_role_name, MaxItems=100
        )
        print("managed policies:", managed_policies)
        for policy in managed_policies["AttachedPolicies"]:
            client.detach_role_policy(
                RoleName=agentcore_role_name, PolicyArn=policy["PolicyArn"]
            )

        print(f"deleting {agentcore_role_name}")
        client.delete_role(RoleName=agentcore_role_name)
        print(f"recreating {agentcore_role_name}")
        agentcore_iam_role = client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

    # Attach the AgentCore policy
    print(f"attaching role policy {agentcore_role_name}")
    try:
        client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name,
        )
    except Exception as e:
        print(e)Anthropic の tool use のドキュメントによると，tool の説明に加え，tool の引数の意味や説明を具体的に記述することがベストプラクティスであるとされているため，本実装では，Pydantic の Field を利用して引数の説明を記載することにしました。

    return agentcore_iam_role


def main() -> None:
    load_dotenv()
    agent_name = os.getenv("AGENT_NAME", "default-agent")

    role = create_agentcore_role(agent_name)
    print(f"Created role: {role['Role']['Arn']}")


if __name__ == "__main__":
    main()
```

</details>

### Step 3. MCP サーバーを AgentCore Runtime にデプロイ

[bedrock-agentcore-starter-toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit) を利用することで，ローカルで開発した MCP サーバーを AgentCore Runtime に容易にデプロイすることができます．具体的には，`agentcore configure` コマンドや `agentcore launch` コマンドで，以下の処理を自動実行することができます．

- デプロイに必要な `Dockerfile` や設定ファイル (`.bedrock_agentcore.yaml`)の作成
- ECR リポジトリの作成
- Docker イメージのビルドと ECR へのプッシュ
- AgentCore Runtime へのデプロイ

:::note warn
Docker イメージは，[ARM64 アーキテクチャ向けにビルド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html#build-and-deploy-arm64-image)する必要があります．異なる CPU アーキテクチャを利用している場合，`agentcore launch` コマンドに `--codebuild` オプションを指定することで，CodeBuild を利用して ARM64 アーキテクチャ向けにビルド・デプロイすることができます．(bedrock-agentcore-starter-toolkit を最新化して下さい．)

https://github.com/aws/bedrock-agentcore-starter-toolkit/releases/tag/v0.1.1
:::

本検証では，Python で starter-toolkit を利用し，Dockerfile や設定ファイルの作成からデプロイまでを一括で実行するスクリプトを実装しました．リポジトリの `mcp_server` ディレクトリに移動し，以下のコマンドを実行することで，MCP サーバーを AgentCore Runtime にデプロイできます．

```bash
uv run scripts/deploy_mcp_server.py
```

なお，ディレクトリ構成は以下の前提です．

```
mcp_server/
├── README.md
├── pyproject.toml # ライブラリ依存関係ファイル
├── scripts
│   └── deploy_mcp_server.py # デプロイ用スクリプト
├── src
│   ├── __init__.py
│   └── mcp_server.py # OpenAI o3 MCP サーバー
└── uv.lock
```

コードの出力結果の `Agent ARN` を `.env` ファイルの `AGENT_ARN` に記載してください．

<details open><summary>コード (折りたためます)</summary>

```python:mcp_server/scripts/deploy_mcp_server.py
import os

from bedrock_agentcore_starter_toolkit import Runtime
from dotenv import load_dotenv


def deploy_mcp_server(
    cognito_client_id: str,
    cognito_discovery_url: str,
    role_arn: str,
    agent_name: str,
    env_vars: dict,
    entrypoint: str = "./src/mcp_server.py",
    requirements_file: str = "./pyproject.toml",
    region: str = "us-west-2",
) -> None:
    agentcore_runtime = Runtime()

    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [cognito_client_id],
            "discoveryUrl": cognito_discovery_url,
        }
    }

    print("Configuring AgentCore Runtime...")
    agentcore_runtime.configure(
        entrypoint=entrypoint,
        execution_role=role_arn,
        auto_create_ecr=True,
        requirements_file=requirements_file,
        region=region,
        authorizer_configuration=auth_config,
        protocol="MCP",
        agent_name=agent_name,
    )
    print("Configuration completed ✓\n")

    print("Launching MCP server to AgentCore Runtime...")
    print("This may take several minutes...")
    launch_result = agentcore_runtime.launch(
        env_vars={"OPENAI_API_KEY": env_vars.get("OPENAI_API_KEY")},
    )
    print("Launch completed ✓\n")
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")


def main() -> None:
    """
    Main function to execute the deployment of the MCP server.
    """
    load_dotenv()
    cognito_client_id = os.getenv("COGNITO_CLIENT_ID")
    cognito_discovery_url = os.getenv("COGNITO_DISCOVERY_URL")
    role_arn = os.getenv("ROLE_ARN")
    agent_name = os.getenv(
        "AGENT_NAME"
    )  # Must start with a letter, contain only letters/numbers/underscores, and be 1-48 characters long.
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not (
        cognito_client_id
        and cognito_discovery_url
        and role_arn
        and agent_name
        and openai_api_key
    ):
        raise ValueError("Required environment variables are not set.")

    deploy_mcp_server(
        cognito_client_id,
        cognito_discovery_url,
        role_arn,
        agent_name,
        {"OPENAI_API_KEY": openai_api_key},
    )


if __name__ == "__main__":
    main()
```

</details>

上記のコードの関数 `deploy_mcp_server` では，以下 2 つのメソッドを実行しています．

- `bedrock_agentcore_starter_toolkit.Runtime.configure()`
- `bedrock_agentcore_starter_toolkit.Runtime.launch()`

`configure()` では，デプロイに必要な Dockerfile や設定ファイル (.bedrock_agentcore.yaml)を自動生成します．指定可能な引数について，主要なものを以下に説明します．

| 引数名                     | 説明                                                                         |
| -------------------------- | ---------------------------------------------------------------------------- |
| `entrypoint`               | 実行する MCP サーバーのコードのパス                                          |
| `requirements_file`        | ライブラリの依存関係ファイル (`pyproject.toml` or `requirements.txt`) のパス |
| `auto_create_ecr`          | ECR リポジトリを自動作成するかどうか (デフォルトは `True`)                   |
| `authorizer_configuration` | OAuth 認証の設定                                                             |
| `protocol`                 | Runtime のプロトコル (MCP を利用する場合は `MCP` を指定)                     |

:::note note
各引数の利用方法については，[AWS CLI Reference](https://docs.aws.amazon.com/cli/latest/reference/bedrock-agentcore-control/create-agent-runtime.html) や [starter-toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/src/bedrock_agentcore_starter_toolkit/notebook/runtime/bedrock_agentcore.py#L34) の実装が参考になります．
:::

上記の実行により，以下のファイルが `mcp_server` ディレクトリに自動生成されます．

- `.bedrock_agentcore.yaml`
- `.dockerignore`
- `Dockerfile`

`.bedrock_agentcore.yaml` は， AgentCore Runtime の設定ファイルであり，launch 時に指定した情報が反映されます．また，`Dockerfile` も簡単なものが自動生成されます．参考のため，以下に `.bedrock_agentcore.yaml` と `Dockerfile` の内容を示します．

<details><summary>.bedrock_agentcore.yaml (折りたたんでます)</summary>

```yaml:.bedrock_agentcore.yaml
default_agent: <agent name>
agents:
  <agent name>:
    name: <agent name>
    entrypoint: /home/ubuntu/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_server/src/mcp_server.py
    platform: linux/arm64
    container_runtime: docker
    aws:
      execution_role: arn:aws:iam::<aws-account-id>:role/agentcore-<agent name>-role
      execution_role_auto_create: false
      account: "<aws-account-id>"
      region: <region>
      ecr_repository: <aws-account-id>.dkr.ecr.<region>.amazonaws.com/bedrock-agentcore-<agent name>
      ecr_auto_create: false
      network_configuration:
        network_mode: PUBLIC
      protocol_configuration:
        server_protocol: MCP
      observability:
        enabled: true
    bedrock_agentcore:
      agent_id: <agent name>-<runtime id>
      agent_arn: arn:aws:bedrock-agentcore:<region>:<aws-account-id>:runtime/<agent name>-<runtime id>
      agent_session_id: null
    codebuild:
      project_name: null
      execution_role: null
      source_bucket: null
    authorizer_configuration:
      customJWTAuthorizer:
        allowedClients:
          - <cognito-client-id>
        discoveryUrl: https://cognito-idp.<region>.amazonaws.com/<region>_<cognito-discovery-id>/.well-known/openid-configuration
    oauth_configuration: null
```

</details>

<details><summary>Dockerfile (折りたたんでます)</summary>

```dockerfile:Dockerfile
FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /app



COPY . .
# Install from pyproject.toml directory
RUN pip install .




RUN pip install aws-opentelemetry-distro>=0.10.0


# Set AWS region environment variable

ENV AWS_REGION=<region>
ENV AWS_DEFAULT_REGION=<region>


# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080
EXPOSE 8000

# Copy entire project (respecting .dockerignore)
COPY . .

# Use the full module path

CMD ["opentelemetry-instrument", "python", "-m", "src.mcp_server"]
```

</details>

`launch()` では，実際に Docker イメージのビルドや ECR へのプッシュ，AgentCore Runtime へのデプロイを行います．引数 `env_vars` で環境変数を指定することで，MCP サーバーの実行時に必要な環境変数を設定できます．今回は，OpenAI API キーを `OPENAI_API_KEY` という環境変数名で指定しています．

:::note warn
本検証では OpenAI の API キーを AgentCore Runtime のコンテナの環境変数 `OPENAI_API_KEY` に設定しておりますが，AWS コンソール上では平文で保存されてしまいます．本番環境においては，Secret Manager で保存したり，以下の記事のように，AgentCore Identity を API キー認証情報プロバイダーとして利用する方が良いでしょう．
:::

https://qiita.com/moritalous/items/6c822e68404e93d326a4

:::note alert
MCP サーバーで利用するパッケージ `mcp` のバージョンについて，執筆時点 (2025/07/31) で最新の`mcp==1.12.2` として下さい．仮に OAuth 関連で不具合が発生する場合，`mcp==1.11.0` にダウングレードして下さい．（本不具合については後述します．）
:::

https://github.com/awslabs/amazon-bedrock-agentcore-samples/pull/86

### Step 4. Remote MCP サーバーの動作確認

簡易的な MCP クライアントにより，Remote MCP サーバーの動作確認を行います．リポジトリの `mcp_client` ディレクトリに移動して下さい．

以下のコマンドを実行し，MCP サーバーに接続して，tool の一覧を取得できることを確認します．なお，`.env` ファイルに以下の変数が設定されていることを確認して下さい．

- `AGENT_ARN`: AgentCore Runtime 上にデプロイした MCP サーバーの ARN
- `COGNITO_ACCESS_TOKEN`: Cognito のアクセストークン (Bearer Token)

```bash
uv run src/mcp_client_remote.py
```

:::note info
Cognito のアクセストークンの期限は 1 時間で切れます．期限が切れた場合，`setup` ディレクトリに移動後，以下のコードを実行することで新しいアクセストークンを取得できます．

```bash
uv run src/setup_cognito.py
```

:::

<details open><summary>コード (折りたためます)</summary>

```python:mcp_client/src/mcp_client_remote.py
import asyncio
import os
import sys

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def get_mcp_endpoint(agent_arn: str, region: str = "us-west-2") -> str:
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"


async def connect_to_server(mcp_endpoint: str, headers: dict) -> None:
    try:
        async with streamablehttp_client(
            mcp_endpoint, headers, timeout=120, terminate_on_close=False
        ) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                print("\n🔄 Initializing MCP session...")
                await session.initialize()
                print("✓ MCP session initialized")

                print("\n🔄 Listing available tools...")
                tool_result = await session.list_tools()

                print("\n📋 Available MCP Tools:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}")
                    print(f"   Description: {tool.description}")
                    if hasattr(tool, "inputSchema") and tool.inputSchema:
                        properties = tool.inputSchema.get("properties", {})
                        if properties:
                            print(f"   Parameters: {list(properties.keys())}")
                    print()

                print("✅ Successfully connected to MCP server!")
                print(f"Found {len(tool_result.tools)} tools available.")

    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        sys.exit(1)


async def main():
    load_dotenv()
    agent_arn = os.getenv("AGENT_ARN")
    bearer_token = os.getenv("COGNITO_ACCESS_TOKEN")
    if not (agent_arn and bearer_token):
        raise ValueError(
            "Required environment variables AGENT_ARN and COGNITO_ACCESS_TOKEN are not set."
        )

    mcp_endpoint = get_mcp_endpoint(agent_arn)
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    print(f"\nConnect to: {mcp_endpoint}")
    await connect_to_server(mcp_endpoint, headers)


if __name__ == "__main__":
    asyncio.run(main())
```

```bash: 出力結果
Connect to: https://bedrock-agentcore.<region>.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3A<region>%3A<account-id>%3Aruntime%2F<agent-arn>/invocations?qualifier=DEFAULT

🔄 Initializing MCP session...
✓ MCP session initialized

🔄 Listing available tools...

📋 Available MCP Tools:
==================================================
🔧 openai_o3_web_search
   Description: An AI agent with advanced web search capabilities. Useful for finding the latest information,
    troubleshooting errors, and discussing ideas or design challenges. Supports natural language queries.

    Args:
        question: The search question to perform.

    Returns:
        str: The search results with advanced reasoning and analysis.

   Parameters: ['question']

🔧 greet_user
   Description: Greet a user by name
    Args:
        name: The name of the user.

   Parameters: ['name']

✅ Successfully connected to MCP server!
Found 2 tools available.
```

</details>

コードでは，パッケージ `mcp` の `streamablehttp_client` を利用して，MCP サーバーに接続しています．重要な点は，引数で指定している `mcp_endpoint` (Remote MCP サーバーの接続先のエンドポイント) と `headers` の形式です．

#### mcp_endpoint

接続先エンドポイントは，以下の形式である必要があります．以下は，[ドキュメントの実装例](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html#runtime-mcp-invoke-server)や，[GitHub のサンプル](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)から確認することができます． (AWS コンソール上では確認することができませんでした．)

```
https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<encoded-agent-arn>/invocations?qualifier=DEFAULT
```

また，`<encoded-agent-arn>` の部分は，URL エンコードされた AgentCore Runtime の ARN である必要があります．具体的には，`:` を `%3A` に，`/` を `%2F` に置換する必要があります．

#### headers

header の形式は，以下の形式である必要があります．authorization ヘッダーには，Cognito のアクセストークンを設定する必要があります．Content-Type ヘッダーおよび Accept ヘッダーは省略可能ですが，記述する場合は [MCP の仕様](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#sending-messages-to-the-server)に[従う必要があります](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html#runtime-mcp-invoke-server)．

```json
{
  "authorization": "Bearer <token>",
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream"
}
```

### Step 5. Strands Agents から Remote MCP サーバーを利用

[Strands Agents](https://strandsagents.com/latest/) を利用し，MCP サーバーに接続します．Strands Agents は，AWS が公開した OSS の AI Agent 開発フレームワークであり，数行で Agent を実装することができます．Strands Agents が提供するクラス [`MCPClient`](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/mcp-tools/)を利用することで，非常に簡単に MCP サーバーを利用することができます．

`mcp_client` ディレクトリ上で，以下のコマンドを実行することで，Strands Agents 経由で MCP サーバーを利用できます．

```bash
uv run src/agent.py
```

<details open><summary>コード (折りたためます)</summary>

```python:mcp_client/src/agent.py
import os

from dotenv import load_dotenv
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

PROMPT = "LangGraphにおけるMCPの実装方法 (python) について調べて. "


def get_mcp_endpoint(agent_arn: str, region: str = "us-west-2") -> str:
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"


def main() -> None:
    load_dotenv()
    agent_arn = os.getenv("AGENT_ARN")
    bearer_token = os.getenv("COGNITO_ACCESS_TOKEN")
    mcp_endpoint = get_mcp_endpoint(agent_arn)
    headers = {"authorization": f"Bearer {bearer_token}"}

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            mcp_endpoint,
            headers=headers,
            timeout=300,
        )
    )

    try:
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            agent = Agent(tools=tools)
            agent(PROMPT)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to MCP server or execute agent: {e}")


if __name__ == "__main__":
    main()
```

> [公式ドキュメントの実装例](https://strandsagents.com/latest/documentation/docs/examples/python/mcp_calculator/)を参考にしました．

</details>

上記のコードと Step 4 のコードを比較すると，少量のコードであることがわかります．特に，MCP サーバーの初期化処理 (initialize) やセッションの管理が `MCPClient` で自動で行われており、非常にシンプルな実装になっています．

o3 Web search MCP の調査結果を基にした Strands Agents の回答結果を以下に示します．(出力が多いので，GitHub に upload しています．)

https://github.com/ren8k/aws-bedrock-agentcore-runtime-remote-mcp/blob/main/assets/strands_agent_results_using_o3_mcp.md

OpenAI o3 の Web search 特有の詳細な検索結果を基に，回答が生成されています．ただし，Strands Agents の回答の最後に `Session termination failed: 404` というエラー出力が表示されており，こちらについては原因不明です．

:::note info
MCP サーバーの実行ログについて，CloudWatch Logs GenAI Observability の Bedrock AgentCore タブ内に記録されないようです．Strands Agent の Agent Loop の実行内容については，CloudWatch Logs GenAI Observability の Model Invocations タブ内に記録されます．
:::

### Step 6. Claude Code から Remote MCP サーバーを利用

最後に，Claude Code から o3 Web search MCP サーバーを利用してみます．`mcp_client` ディレクトリ上で，以下のコマンドを実行します．

```bash
bash src/claude_code.py
```

[Claude Code の公式ドキュメント](https://docs.anthropic.com/en/docs/claude-code/mcp)を参考に，header の設定を行っております．

<details open><summary>コード (折りたためます)</summary>

```shell:setup_claude_code.sh (一部抜粋)
claude mcp add --transport http \
    o3-mcp-server "$MCP_ENDPOINT" \
    --header "Authorization: Bearer $COGNITO_ACCESS_TOKEN"
```

</details>

以下が実際の利用結果です．

![cc_result.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9e95cc5c-df92-4bbc-a91c-f74568a6c41d.png)

Claude Code と o3 を組み合わせることで，開発効率を大幅に向上できそうです．

## 観測した MCP の不具合について

執筆時点 (2025/07/31) では，トランスポートとして streamable HTTP を利用する場合，パッケージ `mcp` では以下の不具合が発生することを確認しております．

### 1. MCP サーバーのレスポンスに `\x85` が含まれる場合，hang してしまう

極稀ですが，MCP の最終的なレスポンス (o3 の出力結果) に `\x85` が含まれる場合、MCP サーバーのレスポンスのパースに失敗してしまいます．

https://github.com/modelcontextprotocol/python-sdk/issues/1144

<details><summary>エラー内容 (折りたたんでます)</summary>

```

Tool #1: openai_o3_web_search
Error parsing SSE message
Traceback (most recent call last):
File "/home/ubuntu/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client/.venv/lib/python3.12/site-packages/mcp/client/streamable_http.py", line 162, in \_handle_sse_event
message = JSONRPCMessage.model_validate_json(sse.data)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/ubuntu/workspace/aws-bedrock-agentcore-runtime-remote-mcp/mcp_client/.venv/lib/python3.12/site-packages/pydantic/main.py", line 746, in model_validate_json
return cls.**pydantic_validator**.validate_json(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core.\_pydantic_core.ValidationError: 1 validation error for JSONRPCMessage
Invalid JSON: EOF while parsing a string at line 1 column 3373 [type=json_invalid, input_value='{"jsonrpc":"2.0","id":2,...ル作成可能\\n\\n', input_type=str]
For further information visit https://errors.pydantic.dev/2.11/v/json_invalid

```

</details>

その他，2025/07/30 時点では以下のような不具合も観測しておりましたが，**2025/07/31 時点では解決しているようです．**

### 2. `mcp>=1.2.0` の場合，MCP サーバーへの接続でエラーが発生する

パッケージのバージョン起因で，OAuth 認証直後，streamable HTTP のレスポンス (JSON) のパースに失敗する事象が発生しておりました．(AWS Samples でも不具合があったので PR を作成しておりました．) `mcp==1.11.0` にダウングレードすることで解決しましたが，現在は`mcp>=1.8.0`であればどのバージョンでも問題なく動作するようです．(実機検証済み)

https://github.com/awslabs/amazon-bedrock-agentcore-samples/pull/86

### 3. MCP の実行時間が長い場合，hang してしまう

o3 の検索時間が長く，MCP の処理時間が 1 分以上となる場合，MCP のレスポンスが返却されず，MCP Client がハングしてしまう事象が発生しておりました．(MCP の出力自体は OpenAI Dashboard の Logs から確認しております．) こちらに関しては原因不明ですが，現在は解決しているようです．(実機検証済み)

## まとめ

本記事では，AWS Bedrock AgentCore Runtime 上に Remote MCP サーバーをデプロイし，
Strands Agents を利用して MCP サーバーを呼び出す方法について解説しました．AgentCore Runtime を利用することで，streamable HTTP で接続可能な OAuth 認証付きの Remote MCP サーバーを容易に構築することができるので，業務での活用 (MCP サーバーの横展開など) が期待されます．

また，本検証では，MCP 起因の不具合で原因追求に時間を要しましたが，MCP のエラー出力からは根本原因を特定することが難しい点が課題でした．AgentCore Runtime にデプロイ後に不具合が発生した場合は，まずは [mcp python-sdk の Issue](https://github.com/modelcontextprotocol/python-sdk/issues) を確認することを推奨します．

AgentCore は公開されてまだ日が浅く，公式ドキュメントでも詳細な情報が不足しておりますが，本記事の内容が参考になれば幸いです．

## 参考資料

- [Deploy MCP servers in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)
- [GitHub - 01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb)

## 仲間募集

NTT データ デジタルサクセスコンサルティング事業部 では、以下の職種を募集しています。

<details><summary>1. クラウド技術を活用したデータ分析プラットフォームの開発・構築(ITアーキテクト/クラウドエンジニア)</summary>

クラウド／プラットフォーム技術の知見に基づき、DWH、BI、ETL 領域におけるソリューション開発を推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/cloud_engineer

</details>

<details><summary>2. データサイエンス領域（データサイエンティスト／データアナリスト）</summary>

データ活用／情報処理／AI／BI／統計学などの情報科学を活用し、よりデータサイエンスの観点から、データ分析プロジェクトのリーダーとしてお客様の DX／デジタルサクセスを推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/datascientist

</details>

<details><summary>3.お客様のAI活用の成功を推進するAIサクセスマネージャー</summary>

DataRobot をはじめとした AI ソリューションやサービスを使って、
お客様の AI プロジェクトを成功させ、ビジネス価値を創出するための活動を実施し、
お客様内での AI 活用を拡大、NTT データが提供する AI ソリューションの利用継続を推進していただく人材を募集しています。
https://nttdata.jposting.net/u/job.phtml?job_code=804

</details>

<details><summary>4.DX／デジタルサクセスを推進するデータサイエンティスト《管理職/管理職候補》</summary>
データ分析プロジェクトのリーダとして、正確な課題の把握、適切な評価指標の設定、分析計画策定や適切な分析手法や技術の評価・選定といったデータ活用の具現化、高度化を行い分析結果の見える化・お客様の納得感醸成を行うことで、ビジネス成果・価値を出すアクションへとつなげることができるデータサイエンティスト人材を募集しています。

https://nttdata.jposting.net/u/job.phtml?job_code=898

</details>

## ソリューション紹介

<details><summary> Trusted Data Foundationについて</summary><div>

～データ資産を分析活用するための環境をオールインワンで提供するソリューション～
https://www.nttdata.com/jp/ja/lineup/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDFⓇ-AM（Trusted Data Foundation - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援 (Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://www.nttdata.com/jp/ja/lineup/tdf_am/
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary> NTTデータとDatabricksについて </summary>
NTTデータは、お客様企業のデジタル変革・DXの成功に向けて、「databricks」のソリューションの提供に加え、情報活用戦略の立案から、AI技術の活用も含めたアナリティクス、分析基盤構築・運用、分析業務のアウトソースまで、ワンストップの支援を提供いたします。

https://www.nttdata.com/jp/ja/lineup/databricks/

</details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。

https://www.nttdata.com/jp/ja/lineup/tableau/

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://www.nttdata.com/jp/ja/lineup/alteryx/

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://www.nttdata.com/jp/ja/lineup/datarobot/

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。

https://www.nttdata.com/jp/ja/lineup/informatica/

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://www.nttdata.com/jp/ja/lineup/snowflake/

</div></details>
