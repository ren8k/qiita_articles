---
title: Template
tags:
  - AWS
  - bedrock
  - Agent
  - MCP
  - OpenAI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

## 目次

- 検証内容
- 実装内容
- 実行環境
- 手順

## 検証内容

OpenAI の GPT-4.1 を利用し，Web Search を実行するための MCP（Model Context Protocol）を実装しました．フレームワークとしては，OpenAI が提供する Response API を利用しました．Bedrock AgentCore Runtime では，どのようなフレームワークでも利用可能な点が特徴です．

Amazon Bedrock AgentCore Runtime に，自作の MCP サーバーをデプロイし，streamable HTTP で remote MCP

Amazon Bedrock AgentCore Python SDK を利用していく．

## 実装内容

https://github.com/ren8k/aws-bedrock-agentcore-runtime-remote-mcp

```
.
├── README.md
├── .env.sample
├── mcp_client
├── mcp_server
└── setup
```

`.env.sample` をコピーして，`.env` を作成し，必要な環境変数を設定してください．

## 実行環境

以下に開発環境を示します．本検証では，ARM アーキテクチャベースの EC2 インスタンスで開発・実行しています．AMI として [AWS Deep Learning AMI](https://docs.aws.amazon.com/dlami/latest/devguide/what-is-dlami.html) を利用しました．本 AMI には，Docker や AWS CLI がプリインストールされており，非常に便利です．EC2 には，[uv](https://docs.astral.sh/uv/getting-started/installation/) をインストールしております．

- OS: Ubuntu Server 24.04 LTS
- AMI: 01e1d8271212cd19a (Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.7)
- Instance Type: m8g.xlarge (ARM)
- Docker version: 28.3.2, build 578ccf6
- uv version: 0.8.3

以下のリポジトリでは，local 上の VSCode から EC2 へ接続して，簡単に開発環境を構築する手順をまとめております．是非ご利用ください．

https://github.com/ren8k/aws-ec2-devkit-vscode

## 手順

### Step 1. 事前準備

リポジトリの `setup` ディレクトリに移動し，`uv sync` を実行することで，`setup` ディレクトリ内のコードの実行に必要なパッケージをインストールして下さい．

#### Step 1-1. Amazon Cognito のセットアップ

AgentCore Runtime にデプロイした MCP サーバーの認証方法には，[AWS IAM か Oauth 2.0 を利用できます](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html#runtime-auth-security)．本検証では，Oauth 2.0 を利用するため，以下のコードを実行し，Cognito User Pool と Cognito User を作成後，認証のために必要な以下の情報を取得します．

- Cognito client ID
- Cognito discovery URL
- JWT (`Bearer_token`)

```
uv run src/setup_cognito.py
```

コードの出力結果の `Client_id`，`Discovery_url`，`Bearer_token` (Access Token) を `.env` ファイルの `COGNITO_CLIENT_ID`, `COGNITO_DISCOVERY_URL`, `COGNITO_ACCESS_TOKEN` に記載してください．

<details open><summary>コード</summary>

```python:setup_cognito.py
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

#### Step 1-2. ロールの作成

以下のコードを実行し，AgentCore Runtime 用の IAM ロールを作成します．作成されるロールは，[AWS 公式ドキュメントに記載のロール](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)と同一です．

作成されるロールは，指定した Agent 名の Runtime が，指定した region の remote MCP サーバーとの認証や通信を行うために必要な権限を持つように設定されています．また，コードでは，同名の role が存在する場合は削除してから再作成するようにしております．

```
uv run src/create_role.py
```

コードの出力結果の `Created role` を `.env` ファイルの `ROLE_ARN` に記載してください．

<details open><summary>コード</summary>

```python:create_role.py
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
    except client.exceptions.EntityAlreadyExistsException:
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
        print(e)

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

### Step2. MCP サーバーの実装

リポジトリの `mcp_server` ディレクトリに移動し，`uv sync` を実行することで，`mcp_server` ディレクトリ内のコードの実行に必要なパッケージをインストールして下さい．

#### Step 2-1. OpenAI o3 Web Search MCP サーバーの実装

[Web Search](https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses)

:::note info
[Strands Agent](https://github.com/strands-agents/sdk-python) では，[Chat Completions API](https://platform.openai.com/docs/guides/text?api-mode=responses) を利用しております．このため，o3 で Web Search Tool を利用することができなかったので，OpenAI が提供している Response API を利用して Web Search Tool を実装しました．
:::

::: note info
instructions について

tool_choice が利用できないので，system prompt で web search tool を利用するように指示しています．
:::

[reasoning を low に設定](https://platform.openai.com/docs/guides/reasoning?api-mode=responses)

#### Step 2-2. Local 上での MCP サーバーの動作確認

#### Step 2-3. MCP サーバーのデプロイ

一括でデプロイするスクリプトを実装しました．

ECR も自動作成してくれます．

:::note info
OpenAI の API キーの扱いについて

簡単のため，本検証では OpenAI の API キーを環境変数 `OPENAI_API_KEY` に設定しておりますが，AWS コンソール上では平文で保存されてしまいます．本番環境においては，Secret Manager で保存したり，以下の記事のように，AgentCore Identity 上を API キー認証情報プロバイダーとして利用することをお勧めします．
:::

https://qiita.com/moritalous/items/6c822e68404e93d326a4

## MCP のバグについて

streamable HTTP を利用する場合，以下の不具合が発生します．MCP サーバーを local で実行した場合には発生しません．

### MCP=1.2.0 以上だと，streamable HTTP のレスポンスの JSON のパースに失敗してしまう

PR も出した

https://github.com/awslabs/amazon-bedrock-agentcore-samples/pull/86

### MCP の実行時間が長い場合(1min 以上)，タイムアウトしてしまう．

https://qiita.com/7shi/items/3bf54f47a2d38c70d39b

似た Issue は上がっているが，解決済みとされている．

### MCP のレスポンスに `\x85` が含まれる場合，hang してしまう．

MCP のレスポンスに `\x85` が含まれる場合、json のパースに失敗してしまう．
pydantic 起因のバグなので，いずれは修正されると思われる．

https://github.com/modelcontextprotocol/python-sdk/issues/1144

## その他

GenAI observability でも確認できる．

## Tips

- role はドキュメント通りで良かった．
- やりなおす場合は，bedrock_agentcore.yaml を削除すべき

## 内容 1

## まとめ

summary

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
```
