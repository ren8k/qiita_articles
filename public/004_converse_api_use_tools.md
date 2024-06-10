---
title: Amazon Bedrock Converse API と Tool use を知識ゼロから学び，発展的なチャットアプリを実装する
tags:
  - Python
  - AWS
  - bedrock
  - 生成AI
  - claude
private: true
updated_at: '2024-06-10T21:36:32+09:00'
id: 64c4a3de56b886942251
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

最近 Converse API を叩きすぎて，毎日`throttlingException`を出している[@ren8k](https://qiita.com/ren8k) です．
先日，Amazon Bedrock の [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) と [Tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html) (function calling) を利用した Streamlit チャットアプリを作成し，以下のリポジトリに公開しました．本記事では，初学者から上級者までを対象とし，Tool use の仕組みやその利用方法，チャットアプリ開発の過程で得た知見や発展的な活用方法を共有いたします．

https://github.com/ren8k/aws-bedrock-converse-app-use-tools

## Converse API とは

[Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) とは，統一的なインターフェースで Amazon Bedrock のモデルを容易に呼び出すことが可能な，チャット用途に特化した API です．推論パラメーターなどのモデル毎の固有の差分を意識せず，モデル ID のみを変更することで，異なるモデルを呼び出すことが可能です．本 API のその他の特徴は以下の通りです．

- マルチターン対話が容易に可能
- ストリーミング処理が可能（ConverseStream API を利用）
- 画像の Base64 エンコードが不要
- **Tool use (function calling) が可能**

本記事では，4 つ目に挙げた [Tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html) について，実際にチャットアプリで活用する際の Tips を紹介します．

:::note info
Converse API で Tool use をサポートしているモデルは，執筆時点（2024/06/09）では以下の 3 種類のみです．本記事では，Claude3 で Tool use を利用する前提で解説いたします．

- Anthropic Claude3
- Mistral AI Large
- Cohere Command R and Command R+

なお，Converse API で利用可能な機能はモデルにより異なります．以下に，Converse API で利用可能なモデルと，サポートされている機能を示します．なお，以下の表は，執筆時点（2024/06/09）の [AWS 公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html#conversation-inference-supported-models-features)から引用したものです．

![supported_model_table.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1cd4218f-0d6c-2d15-66b9-4d4e41bad9a0.png)
:::

## Tool use とは

Tool use (function calling) とは，外部ツールや関数（ツール）を定義・呼び出すことにより，Claude3 の能力を拡張する機能です．事前に定義されたツールに Claude3 がアクセスすることで，必要に応じていつでもツールを呼び出すことができ，Claude3 が通常できないような複雑なタスクを自動化できるようになります．

重要な点として，Claude3 が能動的にツールを実行するわけではなく，どのツールをどのような引数で呼ぶべきかをユーザーに依頼し，ユーザーがツールを実行します．その後，ツールの実行結果を Claude3 に伝え，ツールの実行結果に基づいて Claude3 が回答を生成します．具体的な仕組みについては次章で説明します．

TODO：修正

![tool_use.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/fe887858-0d9a-9350-06e7-7ee673ebe7e1.png)

## Tool use の仕組み

以下のようなステップで，Tool use を利用できます．

- Step1: ツールの定義とプロンプトを Claude3 に送信
- Step2: Claude3 からツール実行のリクエストを取得
- Step3: ユーザーがツールを実行
- Step4: ツールの実行結果を Claude3 に送信
- Step5: ツールの実行結果に Claude3 が回答を生成

TODO：修正

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/258954f4-6ab2-9222-dd3b-19c9d09e110c.png)

以降，天気予報検索ツールを利用する場合を例として，各ステップについて詳細に説明します．

### Step1: ツールの定義とプロンプトを Claude3 に送信

まず，`ToolsList`クラスを作成し，天気予報検索ツールをメソッドとして定義しておきます．なお，以下の関数は簡単のため，実際の天気予報を取得せず，特定の文字列を返す機能のみを実装しています．

```python:tool_use_tutorial.py
class ToolsList:
  def get_weather(self, prefecture, city):
      """
      指定された都道府県と市の天気情報を取得する関数。

      引数:
      - prefecture (str): 都道府県名を表す文字列。
      - city (str): 市区町村名を表す文字列。

      返り値:
      - result (str): 指定された都道府県と市の天気情報を含む文字列。
      """
      result = f"{prefecture}, {city} の天気は晴れで，最高気温は22度です．"
      return result
```

:::note info
ToolsList クラスを作成している理由は，後続のステップにて `getattr()`関数を使用してツール名に対応する関数を動的に取得するためです．この点は後ほど説明します．
:::

次に，ツールの定義を行います．定義では，以下の項目を設定する必要があります．

- ツール名: `get_weather`
- ツールの説明: `指定された場所の天気を取得します。`
- 入力スキーマ: `prefecture` と `city` の 2 つの引数の型と説明，必須かどうかを定義

```python
tool_definition = {
    "toolSpec": {
      "name": "get_weather",
      "description": "指定された場所の天気を取得します。",
      "inputSchema": {
        "json": {
          "type": "object",
          "properties": {
            "prefecture": {
              "type": "string",
              "description": "指定された場所の都道府県"
            },
            "city": {
              "type": "string",
              "description": "指定された場所の市区町村"
            }
          },
          "required": ["prefecture", "city"]
        }
      }
    }
  }
```

その後，ツールの定義とプロンプトを Claude3 に送信します．以下では，ツールの定義を Converse API の引数`toolConfig` にて指定しており，プロンプトとして`東京都墨田区の天気は？`という質問を送信しております．

```python:tool_use_tutorial.py
from pprint import pprint

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
model_id = "anthropic.claude-3-haiku-20240307-v1:0"
prompt = "東京都墨田区の天気は？"
messages = [
    {
        "role": "user",
        "content": [{"text": prompt}],
    }
]

# Send the message to the model, using a basic inference configuration.
response = client.converse(
    modelId=model_id,
    messages=messages,
    toolConfig={
        "tools": [tool_definition],
    },
)
pprint(response)
messages.append(response["output"]["message"])
```

### Step2: Claude3 からツール実行のリクエストを取得

Converse API で`toolConfig`を指定した場合，Claude3 は応答にツールが必要かどうかを判断し，ツールが必要な場合はレスポンスにツール実行のための情報を返します．以下に，レスポンスの例（`output`キーと`stopReason`キーの値のみ）を示します．

```json
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [
        {
          "toolUse": {
            "toolUseId": "tooluse_pc4dkiZmR3u1jF4KORkPmA",
            "name": "get_weather",
            "input": { "prefecture": "東京都", "city": "墨田区" }
          }
        }
      ]
    }
  },
  "stopReason": "tool_use"
}
```

ツール実行のリクエスト情報はレスポンスの`output`キーの値の中の`toolUse`キーにあり，実行すべきツール（関数）名や，関数の引数，ツールリクエストの識別を行うための ID が含まれています．また，レスポンスの`stopReason`キーの値は`tool_use`となり，Claude3 のレスポンスがツールリクエストかどうかを判断できます．

### Step3: ユーザーがツールを実行

Claude3 のレスポンス`response`から，`toolUse`キーの値を取得することで，実行すべきツールの名前（関数名）とその入力（引数）を取得します．そして，`getattr`関数を利用し，ツール名に対応する関数（`ToolsList`クラスで定義したメソッド）を動的に取得後，その関数を実行します．

```python:tool_use_tutorial.py
def extract_tool_use(content):
    for item in content:
        if "toolUse" in item:
            return item["toolUse"]
    return None


response_content = response["output"]["message"]["content"]

# toolUseを抽出
tool_use = extract_tool_use(response_content)
# tool_nameを使って対応する関数を取得し、実行する
tool_func = getattr(ToolsList, tool_use["name"])
# get_weather(prefecture="東京都", city="墨田区")を実行する
tool_result = tool_func(**tool_use["input"])
print(tool_result)
```

上記のコードを実行すると，以下のような出力が得られます．

```
東京都, 墨田区 の天気は晴れで，最高気温は22度です．
```

:::note warn
**Tool use 利用時における Converse API のレスポンスの不確定性について**

上記のコードで関数`extract_tool_use`を定義している理由は，Claude3 で Tool use 利用時に，レスポンスに生成されたテキスト（`text`）が含まれることがあるためです．具体的には，以下のように，レスポンスの`output`キーの値にツールリクエストのための情報（`toolUse`）に加え，テキスト（`text`）が含まれることがあります．

```json
{
  "output": {
    "message": {
      "content": [
        { "text": "はい、それでは" },
        {
          "toolUse": {
            "input": { "city": "墨田区", "prefecture": "東京都" },
            "name": "get_weather",
            "toolUseId": "tooluse_80TuoZSWQAWGHrRy9zbmgg"
          }
        }
      ],
      "role": "assistant"
    }
  }
}
```

なお，上記の事象は，ConverseStream API でも同様に発生することを確認しており，Claude3 特有の事象である可能性があります．（2024/06/09 時点）．また，[Anthropic 公式の Tool use の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/04_complete_workflow.ipynb)においても，以下のように，レスポンスにテキストが含まれることを示唆する記述があります．

> Claude's response contains 2 blocks:
>
> TextBlock(text='Okay, let me use the available tool to try and find information on who won the 2024 Masters Tournament:', type='text')`
>
> ToolUseBlock(id='toolu_01MbstBxD654o9hE2RGNdtSr', input={'search_term': '2024 Masters Tournament'}, name='get_article', type='tool_use')

Converse API, ConverseStream API のレスポンスにテキストが含まれるかは，会話内容や推論パラメーターに依存し不確定であるため，レスポンスの解析には注意が必要です．
:::

### Step4: ツールの実行結果を Claude3 に送信

ツールの実行結果を Claude3 に送信するために，`toolResult`キーを含むメッセージを作成します．`toolResult`キーには，ツールリクエストの識別を行うための ID（`toolUseId`）と，ツールの実行結果を含むコンテンツ（`content`）を指定します．

```python
# `toolResult`キーを含むメッセージを作成
tool_result_message = {
    "role": "user",
    "content": [
        {
            "toolResult": {
                "toolUseId": tool_use["toolUseId"],
                "content": [{"text": tool_result}],
            }
        }
    ],
}
messages.append(tool_result_message)

# 結果を Claude3 に送信
response = client.converse(
    modelId=model_id,
    messages=messages,
    toolConfig={
        "tools": [tool_definition],
    },
)
pprint(response)
messages.append(response["output"]["message"])
```

### Step5: ツールの実行結果に基づいて Claude3 が回答を生成

Claude3 は，ツールの実行結果を利用して，元のプロンプト`東京都墨田区の天気は？`に対する回答を生成します．以下に，Claude3 のレスポンスの例（`output`キーと`stopReason`キーの値のみ）を示します．

```json
{
  "output": {
    "message": {
      "content": [
        {
          "text": "東京都墨田区の天気は晴れで、最高気温は22度だと分かりました。墨田区は東京都の中心に位置する地域で、錦糸町や押上など有名な観光地も近くにあります。晴れの天気で気温も過ごしやすい22度ということで、今日は墨田区を散歩したり、観光を楽しむのにぴったりの良い天気だと言えますね。"
        }
      ],
      "role": "assistant"
    }
  },
  "stopReason": "end_turn"
}
```

:::note info
参考に，Use tools を利用した場合の会話履歴（`messages`）の例を以下に示します．以下を見ると，ユーザーが質問を行い，Claude3 がツール利用のリクエスト後，ユーザーがツールを実行して天気情報を取得し，Claude3 がその結果に基づいて回答を生成していることがわかります．

```python
[
    {
        "role": "user",
        "content": [{"text": "東京都墨田区の天気は？"}],
    },
    {
        "role": "assistant",
        "content": [
            {
                "toolUse": {
                    "input": {"city": "墨田区", "prefecture": "東京都"},
                    "name": "get_weather",
                    "toolUseId": "tooluse_UwHeZGCnSQusfLrwCp9CcQ",
                }
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "content": [
                        {
                            "text": "東京都, 墨田区 "
                            "の天気は晴れで，最高気温は22度です．"
                        }
                    ],
                    "toolUseId": "tooluse_UwHeZGCnSQusfLrwCp9CcQ",
                }
            }
        ],
    },
    {
        "role": "assistant",
        "content": [
            {
                "text": "分かりました。東京都墨田区の天気は晴れで、最高気温は22度だそうです。晴れの天気で気温も高めなので、過ごしやすい1日になりそうですね。外出する際は軽めの服装がおすすめです。"
            }
        ],
    },
]
```

:::

## Tool use を利用したチャットアプリを作成する

実際に，Converse API で Tool use を利用したチャットアプリ（デモ）を作成しました．Python 実装は以下のリポジトリにて公開しております．本アプリの特徴は以下です．

- ConverseStreamAPI と Tool use を組合せた実装
- 会話中に以下の設定を自由に変更可能
  - リージョンと利用するモデル
  - 推論パラメーター
  - Converse API と Converse Stream API，Tool use の利用
- Streamlit の ChatUI 機能を利用したチャットアプリ

https://github.com/ren8k/aws-bedrock-converse-app-use-tools

TODO：修正

![demo.gif](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/cf43ee2a-3fd6-7d3b-2011-dad1ce35a1b8.gif)

詳細な機能は，上記リポジトリの README.md をご参照下さい．以下に，アプリの利用手順を示します．

- 本リポジトリをクローン

```bash
git clone https://github.com/ren8k/aws-bedrock-converse-app-use-tools.git
cd aws-bedrock-chat-app-with-use-tools
```

- 仮想環境の作成および有効化（任意）

```bash
python -m venv .venv
source .venv/bin/activate
```

- 必要なライブラリをインストール

```bash
pip install -r requirements.txt
```

- 下記コマンドを実行し，ターミナルに表示された URL 経由でアプリを起動

```bash
cd src/app
bash run_app.sh
```

## Tool use を利用したチャットアプリ実装時における工夫

ConverseStream API で Tool use を利用する場合の工夫と，Claude3 が不必要にツールを利用しないための工夫について説明します．

:::note info
[ConverseStream API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html) は，Converse API と同様に Amazon Bedrock のモデルを容易に呼び出すことが可能な API ですが，レスポンスをストリーミングで取得できる点が異なります．Converse API と同一の引数で呼び出すことが可能です．
:::

### ConverseStream API で Tool use を利用する場合の工夫

ストリーミング処理が可能な ConverseStream API で Tool use を利用する際には，以下の点に注意する必要が有ります．

- ストリーミングで LLM の生成文およびツールリクエスト情報を取得する必要がある点
- ツールリクエストのフォーマット

まず，ストリーミングで LLM の生成文およびツールリクエスト情報を取得する必要がある点について説明します．ConverseStream API で Tool use を利用する際，以下のようなレスポンスを取得できます．なお，以下ではレスポンスの`stream`キーの要素のみを示しており，プロンプトとして`東京都目黒区の天気は？`という質問を送信しています．

```python
{'messageStart': {'role': 'assistant'}}
{'contentBlockDelta': {'delta': {'text': '分'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'か'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'り'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'ました'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '。'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '東'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '京'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '都'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '目'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '黒'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '区'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'の'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '天'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '気'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'を'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '確'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '認'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': 'します'}, 'contentBlockIndex': 0}}
{'contentBlockDelta': {'delta': {'text': '。'}, 'contentBlockIndex': 0}}
{'contentBlockStop': {'contentBlockIndex': 0}}
{'contentBlockStart': {'start': {'toolUse': {'toolUseId': 'tooluse_6L46H7bYQhiZxqbtCzQCrg', 'name': 'get_weather'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': ''}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '{"pref'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': 'ect'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': 'ure": '}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '"\\u677'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '1\\'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': 'u4eac"'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': ', "city": '}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '"\\u76ee\\u9e'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': 'd2\\u5'}}, 'contentBlockIndex': 1}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '33a"}'}}, 'contentBlockIndex': 1}}
{'contentBlockStop': {'contentBlockIndex': 1}}
{'messageStop': {'stopReason': 'tool_use'}}
{'metadata': {'usage': {'inputTokens': 1023, 'outputTokens': 79, 'totalTokens': 1102}, 'metrics': {'latencyMs': 890}}}
```

ストリーミングレスポンスの各キーの内容を整理した表を以下に示します．なお，以下の表では，レスポンスの`stream`キーの要素を`event`として表現している点にご留意下さい．

| レスポンスのキー                                          | 内容                         | 説明                                                    |
| --------------------------------------------------------- | ---------------------------- | ------------------------------------------------------- |
| `event["contentBlockDelta"]["delta"]["text"]`             | LLM の生成した日本語テキスト | 本項目は含まれないことがある                            |
| `event["contentBlockStart"]["start"]["toolUse"]`          | Tool use の開始情報          | Tool use の開始を示し、`toolUseId` と `name` が含まれる |
| `event["contentBlockDelta"]["delta"]["toolUse"]["input"]` | Tool に渡す入力データ        | Tool に渡すための JSON 形式の入力データが含まれる       |
| `event["messageStop"]["stopReason"]`                      | メッセージの停止理由         | Tool use の場合，`"tool_use"`が含まれる                 |

:::note warn
Converse API と同様，ConverseStream API においても，Use tool 利用時にレスポンスに生成されたテキストが含まれることがあります．具体的には，`event["contentBlockDelta"]["delta"]["text"]`の有無は不確定であるため，注意が必要です．
:::

上記のレスポンスを整理すると，以下のようになります．（なお，Tool の引数の日本語は Unicode エスケープシーケンスになっており，下記では日本語に変換しています．）

```python
{'messageStart': {'role': 'assistant'}}
{'contentBlockDelta': {'delta': {'text': '分かりました。東京都目黒区の天気を確認します。'}}}
{'contentBlockStart': {'start': {'toolUse': {'toolUseId': 'tooluse_6L46H7bYQhiZxqbtCzQCrg', 'name': 'get_weather'}}}}
{'contentBlockDelta': {'delta': {'toolUse': {'input': '{ "prefecture": "東京", "city": "目黒区" }'}}}}
{'messageStop': {'stopReason': 'tool_use'}}
```

また，上記の情報を，以下のフォーマットに整形した上で，ConverseStream API の引数 messages に渡す必要があります．

```json
{
  "content": [
    { "text": "分かりました。東京都目黒区の天気を確認します。" },
    {
      "toolUse": {
        "toolUseId": "tooluse_6L46H7bYQhiZxqbtCzQCrg",
        "name": "get_weather",
        "input": { "prefecture": "東京", "city": "目黒区" }
      }
    }
  ],
  "role": "assistant"
}
```

<details open><summary>上記を実現するための実装例</summary>

以下に，アプリの実装で，ストリーミングで LLM の生成文およびツールリクエスト情報を取得している部分のコードを示します．（説明上，github 上のコードを微量変更しております．）関数`display_streaming_msg_content`の引数`response_stream`には，ConverseStream API のレスポンスの`stream`キーの要素が渡されます．

```python
tool_use_args = {
            "input": {},
            "name": "",
            "toolUseId": "",
        }
tool_use_mode = False

def parse_stream(response_stream):
    #  extract the LLM's output and tool's input from the streaming response.
    tool_use_input = ""
    for event in response_stream:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"]["delta"]
            if "text" in delta:
                yield delta["text"]
            if "toolUse" in delta:
                tool_use_input += delta["toolUse"]["input"]

        if "contentBlockStart" in event:
            tool_use_args.update(
                event["contentBlockStart"]["start"]["toolUse"]
            )

        if "messageStop" in event:
            stop_reason = event["messageStop"]["stopReason"]
            if stop_reason == "tool_use":
                tool_use_args["input"] = json.loads(tool_use_input)
                tool_use_mode = True
            else:
                # if stop_reason == 'end_turn'|'max_tokens'|'stop_sequence'|'content_filtered'
                tool_use_mode = False

def tinking_stream():
    message = "Using Tools..."
    for word in message.split():
        yield word + " "

def display_streaming_msg_content(response_stream):
    if response_stream:
        with st.chat_message("assistant"):
            generated_text = st.write_stream(self.parse_stream(response_stream))
            if not generated_text: # if generated_text is empty because of tool_use
                generated_text = st.write_stream(self.tinking_stream())
    return generated_text

```

</details>

### Claude3 が不必要にツールを利用しないための工夫

結論から述べると，Claude3 Sonnet を利用したプロンプトエンジニアリングが特に有効です．

Tool use 利用時，モデルが不必要にツールを利用してしまうことがあります．例えば，モデルの知識で十分回答できる質問に対しても，Web 検索ツールを利用して回答する傾向が高いです．個人的な印象としては，Claude3 Haiku や Opus はツールを利用することが非常に多く，プロンプトでの制御も難しいです．一方，Claude3 Sonnet もツールを利用する傾向はありますが，プロンプトでの制御がある程度効きやすいです．

:::note info
[Anthropic 公式の Tool use の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/04_complete_workflow.ipynb)においても，プロンプトエンジニアリング時に **Claude3 Sonnet** を利用しております．
:::

以下に，各モデルにおけるツールの利用傾向を示します．（下記は個人環境での実験結果に基づく主観的な印象である点にご留意下さい．）

| モデル         | ツールの利用傾向                                         |
| -------------- | -------------------------------------------------------- |
| Claude3 Haiku  | 問答無用でツールを利用                                   |
| Claude3 Sonnet | ツールを積極的に利用する傾向が強いがプロンプトで制御可能 |
| Claude3 Opus   | CoT の過程でどのツールを利用すべきかを思考して利用       |

[Anthropic の公式ドキュメント](https://docs.anthropic.com/en/docs/tool-use-examples#chain-of-thought-tool-use)や[Anthropic の学習コンテンツのコード](https://github.com/anthropics/courses/blob/master/ToolUse/02_your_first_simple_tool.ipynb)を参考に，下記のようなシステムプロンプトを作成することで，Claude3 Sonnet ではツールの利用を抑制することができました．下記プロンプトの特徴としては，「必要な場合のみツールを利用する」ように強調して指示している点です．

```
あなたは日本人のAIアシスタントです。必ず日本語で回答する必要があります。
以下の<rule>タグ内には厳守すべきルールが記載されています。以下のルールを絶対に守り、ツールを不必要に使用しないで下さい。
<rule>
- あなたはツールにアクセスできますが、必要な場合にのみそれらを使用してください。
- 自身の知識で回答できない場合のみ、関連するツールを使用してユーザーの要求に答えてください。
</rule>

まず、提供されたツールのうち、ユーザーの要求に答えるのに関連するツールはどれかを考えてください。次に、関連するツールの必須パラメータを1つずつ確認し、ユーザーが直接提供したか、値を推測するのに十分な情報を与えているかを判断します。

パラメータを推測できるかどうかを決める際は、特定の値をサポートするかどうかを慎重に検討してください。ただし、必須パラメータの値の1つが欠落している場合は、関数を呼び出さず(欠落しているパラメータに値を入れても呼び出さない)、代わりにユーザーに欠落しているパラメータの提供を求めてください。提供されていないオプションのパラメータについては、追加情報を求めないでください。
```

上記のシステムプロンプトを利用した場合の応答例を以下に示します．以下では，富士山に関する質問には自身の知識で回答しており，Amazon Bedrock に関する質問には知識が無いため，Web 検索ツールを利用して回答していることがわかります．

![sonnet_use_tools.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c570b64d-7332-35bc-d953-8e38979a3abd.png)

レスポンスの速度や，ツールの利用制御の観点から，Claude3 Sonnet は有力なモデルの選択肢であると考えられます．

:::note warn
Claude3 Sonnet の場合，上記のようなシステムプロンプトでうまく制御できましたが，Mistral AI Large の場合は，ツールの利用傾向が著しく低くなるように観察されました．モデルの特性を踏まえ，モデルに適したシステムプロンプトを設計することが重要です．
:::

## Converse API + Tool use Deep Dive

本章では，公式ドキュメントには記載されていない，Converse API でツールを利用する際の注意点や Tips について解説します．特に，Claude 3 のモデル毎のツールの利用傾向やツールの利用を制御するためのプロンプトエンジニアリング，Claude3 Opus のレスポンスに含まれる CoT の内容，ツールの引数生成の失敗ケースなど，Tool use を利用する上で知っておくべき留意点を幅広く取り上げます．また，Converse API がサポートするモデルの一部の引数には制限がある点についても説明します．

### Claude3 Opus で Tool use 利用時のレスポンスについて

Claude3 Opus で Tool use を利用する設定で Converse API を利用すると，レスポンスに必ず Chain of thought (CoT) の内容が含まれます．具体的には，Converse API で引数`toolConfig`を指定すると，以下のように，`<thinking>`タグ内でどの tools を利用すべきかを思考した内容が出力されます．

![opus_cot.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/fd6b2ab9-54f1-74b3-f1bc-75869e105319.png)

本現象は，[Anthropic の公式学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/06_chatbot_with_multiple_tools.ipynb)でも下記のように言及されております．

> An Opus-specific problem
> When working with Opus and tools, the model often outputs its thoughts in <thinking> or <reflection> tags before actually responding to a user. You can see an example of this in the screenshot below:

CoT によって，ツール選定の精度が向上する可能性はありますが，ユーザーエクスペリエンス向上のために，CoT の内容は出力しないように工夫することが望ましいです．

:::note info
上記を実現するために，ユーザー向けの最終的な回答部分を特定のタグで囲い，その部分のみをチャット UI 上に表示することが考えられます．例えば，CoT する前提でシステムプロンプトを記述し，出力として<thinking>タグ内には CoT の内容を，<answer>タグ内には最終的な回答を記述することで，<answer>タグ内のみを表示するようにすることが有効です．本アイデアの実装例を，下記リポジトリの`feature_use_cot`ブランチにて公開しておりますので，是非ご参照下さい．

https://github.com/ren8k/aws-bedrock-converse-app-use-tools
:::

### ツール実行のための引数生成が必ずしも成功するとは限らない

Tool use 利用時，LLM がツールの引数を生成しますが，必ずしもツールの引数生成が成功するとは限りません．Claude3 を利用する場合はほぼ成功しますが，Command R+ などのモデルを利用する場合，ツールの引数生成に失敗（引数が不足するなど）することが度々あります．

よって，ツールの引数生成失敗に伴うツールの実行失敗を回避するためのリトライの仕組みを実装することが望ましいです．（本実装では取り入れておりませんが，ツールの実行に失敗した場合，[エラーの内容を含めて LLM に情報を送信](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html)し，それを踏まえて再度引数を生成させることは可能です．）

:::note info
ツールの引数生成の精度的にも，Claude3 は非常に有力な選択肢であると考えられます．
:::

### 会話履歴にツールの利用履歴がある場合、引数 `toolConfig` の指定が必要

会話履歴（Converse API の引数`messages`）にツールの利用履歴（`toolUse` や `toolResult`）が含まれる場合，Converse API の引数 `toolConfig` に対応するツールの定義を必ず指定しなければなりません．引数 `toolConfig` を指定しない場合，以下のようなエラーが発生します．

```
botocore.errorfactory.ValidationException: An error occurred (ValidationException) when calling the Converse operation: The toolConfig field must be defined when using toolUse and toolResult content blocks.
```

本アプリでは，ツールの利用有無をいつでも切り替えることができますが，ツールを利用した後，ツール有りからツール無しに切り替えてチャットを行う場合，上記のエラーが発生する点にご留意下さい．

### モデル毎の Tool use 利用時における Converse API のレスポンスの差異

Converse API を使用して AI モデルに Tool use を利用させる際，モデルによってレスポンス (`response["output"]["message"]`) の構造に差異があります．具体的には，生成されたテキストがレスポンスに含まれるかどうかが異なります．

以下に，ツールの利用がサポートされているモデル毎の， Converse API のレスポンスの差分を示します．

| モデル           | Converse API のレスポンスにテキストが含まれるか |
| ---------------- | ----------------------------------------------- |
| Claude3          | テキストが含まれる場合がある（不確定）          |
| Command R+       | テキストが含まれる                              |
| Mistral AI Large | テキストが含まれない                            |

Claude3 は，前述の通り，レスポンスに生成されたテキストが含まれるかどうかは不確定です．

Command R+ で Tool use を利用する場合，Converse API におけるレスポンス `response["output"]["message"]`には必ず生成されたテキストが含まれます．以下に，Command R+ に「京都府京都市の天気を教えて」と指示した際の Converse API のレスポンス`response["output"]["message"]`を示します．

```json
{
  "content": [
    { "text": "京都府京都市の天気を検索して、ユーザーに知らせます。" },
    {
      "toolUse": {
        "input": { "city": "京都市", "prefecture": "京都府" },
        "name": "get_weather",
        "toolUseId": "tooluse_WMqogtHhTgOUcjGpRxTrKQ"
      }
    }
  ],
  "role": "assistant"
}
```

一方，Mistral AI Large で Tool use を利用する場合， Converse API におけるレスポンス `response["output"]["message"]`にはテキストは含まれません．以下に Mistral AI Large に「京都府京都市の天気を教えて」と指示した際の Converse API のレスポンス`response["output"]["message"]`を示します．

```json
{
  "content": [
    {
      "toolUse": {
        "input": { "city": "京都市", "prefecture": "京都府" },
        "name": "get_weather",
        "toolUseId": "tooluse_v2wRuKgLRPaQxJJBna0cyw"
      }
    }
  ],
  "role": "assistant"
}
```

### Amazon Titan で Converse API を利用する際の引数`stop sequence`について

Amazon Titan で Converse API を利用する場合，引数`stop sequence`の指定の仕方が他のモデルと異なります．具体的には，引数`stop sequence`には，正規表現パターン「`^(|+|User:)$`」にマッチするような文字列しか指定できません．例えば，Amazon Titan で 引数`stop sequence=["</stop>"]`を指定して Converse API を利用すると以下のエラーが出ます．

```
ValidationException: An error occurred (ValidationException) when calling the Converse operation: The model returned the following errors: Malformed input request: string [</stop>] does not match pattern ^(\|+|User:)$, please reformat your input and try again.
```

本アプリでは，Amazon Titan を選択した場合，`stop sequence`のデフォルト値として`User:`を指定するようにしております．

### AI21 Lab で Converse API を利用する際の引数`messages`について

AI21 Labs Jurassic-2 で Converse API を利用する場合，引数`messages`に会話履歴を含めることはできません．例えば，引数`messages`に`assistant`の応答内容を含めると以下のエラーが出ます．

```
botocore.errorfactory.ValidationException: An error occurred (ValidationException) when calling the Converse operation: This model doesn't support conversation history. Try again with input that only includes one user message.
```

本アプリで AI21 Labs Jurassic-2 を利用する場合，一度会話履歴のキャッシュをクリアしてから利用するようにご留意下さい．

## まとめ

本記事では，Amazon Bedrock の Converse API における Tool use の基本的な仕組みから，実践的な活用方法までを幅広く解説しました．Tool use を利用することで，Claude3 の能力を拡張し，複雑なタスクを自動化できることを説明し，ツールの定義方法やツールの実行方法などを，コード例を交えて紹介しました．また，実際に ConverseStream API + Tool use を利用したチャットアプリの実装例を提示し，その特徴や工夫点（プロンプトエンジニアリングなど），Deep Dive な内容についても解説しました．Claude3 on Amazon Bedrock で Tool use を利用した発展的なチャットアプリの実装を行うために，本記事が一助となれば幸いです．

<!-- ## 仲間募集

NTT データ デザイン＆テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

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
