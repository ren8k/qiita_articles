---
title: Amazon Bedrock Converse APIで Claude3 の JSON モードを利用する
tags:
  - Python
  - AWS
  - bedrock
  - 生成AI
  - LLM
private: false
updated_at: "2024-07-01T00:47:52+09:00"
id: 3d5f66df251703b8407e
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

<!-- 株式会社 NTT データ デジタルサクセスコンサルティング事業部の  -->

最近 Bedrock の Converse API にハマっている [@ren8k](https://qiita.com/ren8k) です．
Claude3 では，Tool use を利用することで，JSON モード (JSON 形式のレスポンスを取得する手法) が利用可能です．[Anthropic のユーザーガイド](https://docs.anthropic.com/en/docs/build-with-claude/tool-use#json-mode)には JSON モードの説明があるのですが，AWS の公式ドキュメントには記載がなく，JSON モードを試した記事や実装例なども見当たりませんでした．そこで本記事では，Claude3 の JSON モードについて調査し，Converse API で実際に検証した結果をまとめます．

JSON モードを検証するにあたり，2024/6/20 にリリースされた Claude3.5 Sonnet を使用し，以下の 3 つのユースケースを題材として検証しました．

- 感情分析
- クエリ拡張
- 画像分析

:::note
Converse API や Tool use については，以下の記事にて詳細に解説しております．是非ご覧ください．
:::

https://qiita.com/ren8k/items/64c4a3de56b886942251

## JSON モードとは

[JSON モード](https://docs.anthropic.com/en/docs/build-with-claude/tool-use#json-mode)は，Claude3 に JSON 形式で回答させる手法です．ただし，実態としては，Tool use 利用時，Claude3 がツールへの入力を JSON 形式でレスポンスする性質を利用しているだけです．

JSON モードは，以下のステップで利用することができます．

- Step1. ツールの定義とプロンプトを Claude3 に送信
- Step2. Claude3 からツール実行のリクエストを取得し JSON 部を抽出

![json_mode.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c8159e84-fbeb-3ba1-dd7b-732f10fb8bc1.png)

> 上図は，[Anthropic 公式の Tool use の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb)から引用しております．

具体的に説明すると，ユーザー側で実際には存在しない「架空のツール」を定義しておき，このツールの入力スキーマとして，求める出力の構造を指定します．この「架空のツール」を Claude3 に送信することで，Claude3 はこのツールが実在すると思い込み，指定されたスキーマに従って JSON 形式の入力を生成します．この生成された JSON 形式のツールの入力が，ユーザーが求める出力そのものとなります．

実際にコードを見た方がイメージが湧くと思いますので，以降では，具体的な利用例を示します．

## 利用例 1（感情分析）

テキストの感情分析を題材として JSON モードを利用してみます．ここで，入力されたテキストに対し，positive, negative, neutral のスコアを JSON 形式で得るタスクを考えます．例えば，`「私はとても幸せです．」`という入力に対し，期待する JSON 出力は以下とします．

```json
{
  "positive_score": 0.9,
  "negative_score": 0.0,
  "neutral_score": 0.1
}
```

### Step1. ツールの定義とプロンプトを Claude3 に送信

まず，架空のツールを定義します．ポイントとして，取得したい出力の構造を，`inputSchema` 中に記述します．以下では，`positive_score`，`negative_score`，`neutral_score` の 3 つのフィールドを入力とする架空のツール`print_sentiment_scores`を定義しております．なお，実際にツールを実行するわけではないので，ツールの実装は不要です．

```python:json_mode_tutorial.py
tool_name = "print_sentiment_scores"
description = "与えられたテキストの感情スコアを出力します。"

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "positive_score": {
                        "type": "number",
                        "description": "ポジティブな感情のスコアで、0.0から1.0の範囲です。",
                    },
                    "negative_score": {
                        "type": "number",
                        "description": "ネガティブな感情のスコアで、0.0から1.0の範囲です。",
                    },
                    "neutral_score": {
                        "type": "number",
                        "description": "中立的な感情のスコアで、0.0から1.0の範囲です。",
                    },
                },
                "required": ["positive_score", "negative_score", "neutral_score"],
            }
        },
    }
}
```

続いて，ツールの定義とプロンプトを Claude3 に送信します．プロンプトは変数 `prompt`で定義しており，変数 `target_text` にて定義した `私はとても幸せです。` という文章に対し，架空のツール`print_sentiment_scores`を利用するように指示しております．

```python:json_mode_tutorial.py
import json
from pprint import pprint

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

target_text = "私はとても幸せです。"

prompt = f"""
<text>
{target_text}
</text>

{tool_name} ツールのみを利用すること。
"""

messages = [
    {
        "role": "user",
        "content": [{"text": prompt}],
    }
]

# Send the message to the model
response = client.converse(
    modelId=model_id,
    messages=messages,
    toolConfig={
        "tools": [tool_definition],
        "toolChoice": {
            "tool": {
                "name": tool_name,
            },
        },
    },
)
pprint(response)
```

:::note

Converse API の引数 `toolConfig` にて，`toolChoice` を指定することで，Claude3 に対してツールを使用するよう強制することができます．特に， `tool` というフィールドにツール名を指定することで，Claude3 は指定されたツールを必ず使用するようになります．詳細については，[AWS 公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolChoice.html)や，[Anthropic 公式の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb)，[Anthropic 公式ユーザーガイド](https://docs.anthropic.com/en/docs/build-with-claude/tool-use#forcing-tool-use)をご参照下さい．
:::

:::note
`toolChoice` でツールの利用を強制していますが，プロンプトでも，`{tool_name} ツールのみを利用すること。` という指示を行っております．これは，[Anthropic 公式の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb)のプロンプト例に倣ったものです．
:::

### Step2. Claude3 からツール実行のリクエストを取得し JSON 部を抽出

Converse API の引数 `toolConfig` にて，`toolChoice` を指定しているため，レスポンスには必ずツール実行のリクエストが含まれます．以下に，レスポンスの一部（`output` キーと `stopReason` キーの値のみ）を示します．

```json
{
  "output": {
    "message": {
      "content": [
        {
          "toolUse": {
            "input": {
              "negative_score": 0.1,
              "neutral_score": 0.0,
              "positive_score": 0.9
            },
            "name": "print_sentiment_scores",
            "toolUseId": "tooluse_Ij0M6aAWQjK2JMO8XZqJrw"
          }
        }
      ],
      "role": "assistant"
    }
  },
  "stopReason": "tool_use"
}
```

上記より，`toolUse` キーの `input` キーに，ツールの入力（引数）が JSON 形式で格納されていることがわかります．Claude3 は，このツールの入力を利用して感情分析ツール `print_sentiment_scores` を実行することをリクエストしていますが，この JSON 部を抽出することで求める出力を得ることができます．

以下のコードでは，この JSON 部を抽出し，出力しています．

```python:json_mode_tutorial.py
def extract_tool_use_args(content):
    for item in content:
        if "toolUse" in item:
            return item["toolUse"]["input"]
    return None

response_content = response["output"]["message"]["content"]

# json部を抽出
tool_use_args = extract_tool_use_args(response_content)
print(json.dumps(tool_use_args, indent=2, ensure_ascii=False))
```

上記の実行結果は以下です．

```json
{
  "positive_score": 0.9,
  "negative_score": 0.0,
  "neutral_score": 0.1
}
```

`「私はとても幸せです．」` という入力文に対し，`positive_score` が 0.9，`negative_score` が 0.0，`neutral_score` が 0.1 というスコアで JSON 形式で出力されており，期待通りの結果であることが確認できます．

## 利用例 2（クエリ拡張）

Advanced RAG における「クエリ拡張」を題材として JSON モードを利用してみます．ここで，ユーザーからの質問文から，多様な観点で検索に適した複数のクエリを JSON 形式で得るタスクを考えます．例えば，`「Amazon Kendra がサポートしているユーザーアクセス制御の方法は？」`という入力に対し，期待する JSON 出力は以下とします．

```json
{
  "query_1": "amazon kendra user access control",
  "query_2": "Amazon Kendra ユーザーアクセス制御 権限設定",
  "query_3": "Amazon Kendra ユーザー認証 ユーザー権限管理 セキュリティ"
}
```

:::note warn
本検証では，AWS 公式ブログ「[Amazon Kendra と Amazon Bedrock で構成した RAG システムに対する Advanced RAG 手法の精度寄与検証](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)」にて紹介されているプロンプトを参考に，改変させていただいております．
:::

### ツールの定義

以下では，与えられた質問文に基づいて，3 つの検索用クエリを生成する架空のツール `multi_query_generator` を定義しております．また，変数 `description` にて，ツールの説明と例を詳細に記述することで，ユーザーがどのような JSON 出力（ツールの入力）を求めているのかを明確にしております．

```python:json_mode_multi_query.py
description = """
与えられる質問文に基づいて、類義語や日本語と英語の表記揺れを考慮し、多角的な視点からクエリを生成します。
検索エンジンに入力するクエリを最適化し、様々な角度から検索を行うことで、より適切で幅広い検索結果が得られるようにします。

<example>
question: Knowledge Bases for Amazon Bedrock ではどのベクトルデータベースを使えますか？
query_1: Knowledge Bases for Amazon Bedrock vector databases engine DB
query_2: Amazon Bedrock ナレッジベース ベクトルエンジン vector databases DB
query_3: Amazon Bedrock RAG 検索拡張生成 埋め込みベクトル データベース エンジン
</example>

<rule>
- 与えられた質問文に基づいて、3個の検索用クエリを生成してください。
- 各クエリは30トークン以内とし、日本語と英語を適切に混ぜて使用すること。
- 広範囲の文書が取得できるよう、多様な単語をクエリに含むこと。
</rule>
"""
tool_name = "multi_query_generator"

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "query_1": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                    "query_2": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                    "query_3": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                },
                "required": ["query_1", "query_2", "query_3"],
            }
        },
    }
}
```

:::note

[Anthropic 公式ユーザーガイド](https://docs.anthropic.com/en/docs/tool-use-examples)では，ツール定義のベストプラクティスとして以下を挙げております，

- 非常に詳細な説明を提供する
- 例よりも説明を優先する

ツールのパフォーマンスにおいて，ツールの詳細な説明（ツールの機能，利用すべきタイミング，各パラメーターの意味）が重要な要素であると解説されています．また，詳細な説明に加え，ツールの使用例を与えることも有効であることも述べられています．
:::

### Claude3 からツール実行のリクエストを取得し JSON 部を抽出

続いて，ツールの定義とプロンプトを Claude3 に送信します．ユーザーからの質問文として，`Amazon Kendra がサポートしているユーザーアクセス制御の方法は` という文章を変数 `target_text` に格納しております．なお，先程の利用例 1 でのコードとの差分は，変数`target_text`の値のみです．

```python:json_mode_multi_query.py
import json
from pprint import pprint

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

target_text = "Amazon Kendra がサポートしているユーザーアクセス制御の方法は"
prompt = f"""
<text>
{target_text}
</text>

{tool_name} ツールのみを利用すること。
"""
print(prompt)
messages = [
    {
        "role": "user",
        "content": [{"text": prompt}],
    }
]

# Send the message to the model
response = client.converse(
    modelId=model_id,
    messages=messages,
    toolConfig={
        "tools": [tool_definition],
        "toolChoice": {
            "tool": {
                "name": tool_name,
            },
        },
    },
)
pprint(response)

def extract_tool_use_args(content):
    for item in content:
        if "toolUse" in item:
            return item["toolUse"]["input"]
    return None

response_content = response["output"]["message"]["content"]

# json部を抽出
tool_use_args = extract_tool_use_args(response_content)
print(json.dumps(tool_use_args, indent=2, ensure_ascii=False))
```

上記のコードで得られる最終的な結果（JSON）は以下です．

```json
{
  "query_1": "Amazon Kendra user access control methods サポート",
  "query_2": "Kendra ユーザーアクセス制御 認証 承認 セキュリティ",
  "query_3": "Amazon Kendra アクセス管理 IAM ABAC 統合認証"
}
```

ユーザーからの質問文に対し，拡張された検索用クエリが 3 つ JSON 形式で出力されており，期待通りの結果であることが確認できます．

:::note
過去の私の記事では，拡張クエリを実現するために，Claude3 に対してプロンプトで JSON 形式で回答するように指示し，生成結果が JSON 形式かどうかをコード上で検証していました．JSON モードを利用すると，生成結果が JSON であることが保証されるため，便利ですね．
:::

https://qiita.com/ren8k/items/dcdb7f0c61fda384c478

## 利用例 3（画像分析）

最後に，画像を分析を題材として JSON モードを利用してみます．ここで，与えられた画像を分析し，画像の特徴や要約を記録するタスクを考えます．例えば，以下の東京スカイツリーの画像に対し，以下のような情報を記録することを考えます．

- `key_colors`: 画像で利用されている代表的な rgb 値と色の名前のリスト (3~4 色程度)
- `description`: 画像の説明
- `estimated_year`: 撮影された年の推定値
- `tags`: 画像のトピックのリスト (3~5 個程度)

<img width="350" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8647c9c7-816b-5366-d1cb-3e7368eeafbd.jpeg">

上記のスカイツリーの画像に期待する JSON 出力は以下とします．

```json
{
  "key_colors": [
    {
      "r": 0,
      "g": 0,
      "b": 100,
      "name": "dark_blue"
    },
    {
      "r": 0,
      "g": 255,
      "b": 255,
      "name": "cyan"
    },
    {
      "r": 255,
      "g": 223,
      "b": 0,
      "name": "golden"
    },
    {
      "r": 50,
      "g": 205,
      "b": 50,
      "name": "lime_green"
    }
  ],
  "description": "東京スカイツリーが夜景の中でライトアップされ、周囲の木々やビルと共に美しい都市の風景を作り出している。",
  "estimated_year": 2022,
  "tags": [
    "Tokyo Skytree",
    "night view",
    "illumination",
    "urban landscape",
    "tourism"
  ]
}
```

### ツールの定義

以下では，与えられた画像を分析し，要約を記録する架空のツール `record_image_summary` を定義しております．利用例 2 と同様，変数 `description` にて，ツールの説明を詳細に記述しております．また，`inputSchema`中の`description`でも，各フィールドの説明と例をなるべく詳細に記述しております．

```python:json_mode_record_img_summary.py
tool_name = "record_image_summary"
description = """
与えられた画像を分析し、要約を記録します。
具体的には、以下の要素を含む要約をJSON形式で出力します。

<summary>
- key_colors: 画像で利用されている代表的なrgb値と色の名前のリスト。3~4色程度。
- description: 画像の説明。1~2文程度。
- estimated_year: 撮影された年の推定値
- tags: 画像のトピックのリスト。3~5個程度。
</summary>
"""

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "key_colors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "r": {
                                    "type": "number",
                                    "description": "赤の値。値の範囲: [0.0, 255.0]",
                                },
                                "g": {
                                    "type": "number",
                                    "description": "緑の値。値の範囲: [0.0, 255.0]",
                                },
                                "b": {
                                    "type": "number",
                                    "description": "青の値。値の範囲: [0.0, 255.0]",
                                },
                                "name": {
                                    "type": "string",
                                    "description": 'スネークケースの人間が読める色の名前。例: "olive_green" や "turquoise" など。',
                                },
                            },
                            "required": ["r", "g", "b", "name"],
                        },
                        "description": "画像の主要な色。4色未満に制限すること。",
                    },
                    "description": {
                        "type": "string",
                        "description": "画像の説明。1〜2文程度。",
                    },
                    "estimated_year": {
                        "type": "integer",
                        "description": "写真の場合、撮影された年の推定値。画像がフィクションではないと思われる場合にのみ設定してください。おおよその推定で構いません。",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'トピックの配列。例えば ["building-name", "region"] など。できるだけ具体的であるべきで、重複しても構いません。',
                    },
                },
                "required": ["key_colors", "description", "tags"],
            }
        },
    }
}
```

### Claude3 からツール実行のリクエストを取得し JSON 部を抽出

続いて，ツールの定義とプロンプトを Claude3 に送信します．スカイツリーの画像を `./skytree.jpeg` に保存しておき，それをバイナリで読み込み，Converse API に送信しております．Converse API を利用する場合，画像は base64 エンコードする必要はありません．

```python:json_mode_record_img_summary.py
import json
from pprint import pprint

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

image_path = "./skytree.jpeg"
prompt = f"""
{tool_name} ツールのみを利用すること。
"""

with open(image_path, "rb") as f:
    image = f.read()

messages = [
    {
        "role": "user",
        "content": [
            {
                "image": {
                    "format": "jpeg",
                    "source": {"bytes": image},
                }
            },
            {
                "text": prompt,
            },
        ],
    }
]

# Send the message to the model
response = client.converse(
    modelId=model_id,
    messages=messages,
    toolConfig={
        "tools": [tool_definition],
        "toolChoice": {
            "tool": {
                "name": tool_name,
            },
        },
    },
)
pprint(response)

def extract_tool_use_args(content):
    for item in content:
        if "toolUse" in item:
            return item["toolUse"]["input"]
    return None

response_content = response["output"]["message"]["content"]

# json部を抽出
tool_use_args = extract_tool_use_args(response_content)
print(json.dumps(tool_use_args, indent=2, ensure_ascii=False))
```

上記のコードで得られる最終的な結果（JSON）は以下です．

```json
{
  "key_colors": [
    {
      "r": 13,
      "g": 20,
      "b": 41,
      "name": "navy_blue"
    },
    {
      "r": 104,
      "g": 205,
      "b": 193,
      "name": "turquoise"
    },
    {
      "r": 255,
      "g": 223,
      "b": 128,
      "name": "golden_yellow"
    },
    {
      "r": 255,
      "g": 255,
      "b": 255,
      "name": "white"
    }
  ],
  "description": "東京スカイツリーの夜景。イルミネーションで彩られた建物と周辺の木々が印象的。",
  "estimated_year": 2022,
  "tags": [
    "Tokyo-Skytree",
    "night-view",
    "illumination",
    "cityscape",
    "architecture"
  ]
}
```

入力画像がスカイツリーの画像であることを認識しており，その画像の要約や特徴が JSON 形式で適切に出力されていることを確認できます．

## まとめ

本記事では，Amazon Bedrock の Converse API を利用して，Claude3 の JSON モード (Tool use) を利用する方法の紹介と検証を行いました．JSON モードではレスポンスが必ず JSON 形式で帰ってくるため，ユースケース次第では非常に便利な機能であることがわかりました．また，実際に具体的なユースケースで JSON モードを利用した結果，期待通りの出力が得られ，十分実用的であることも確認できました．

Anthropic の公式リポジトリでは，Anthropic API を利用した場合の JSON モードの様々な実装例が公開されています．ツールの定義方法などは参考になりそうなので，興味のある方は以下のリンクも参照してみてください．

https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb

https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb

<!-- ## 仲間募集

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
https://enterprise-aiiot.nttdata.com/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDF-AM（Trusted Data FoundationⓇ - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援（Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://enterprise-aiiot.nttdata.com/service/tdf/tdf_am
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。
https://enterprise-aiiot.nttdata.com/service/tableau

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://enterprise-aiiot.nttdata.com/service/alteryx

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://enterprise-aiiot.nttdata.com/service/datarobot

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。
https://enterprise-aiiot.nttdata.com/service/informatica

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://enterprise-aiiot.nttdata.com/service/snowflake

</div></details> -->
