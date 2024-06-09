---
title: Claude3 で Bedrock Converse API + Tool use を活用したチャットアプリを実装する上でのTips
tags:
  - AWS
  - bedrock
  - Python
  - Claude
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デザイン＆テクノロジーコンサルティング事業本部の [@ren8k](https://qiita.com/ren8k) です．

Converse API の使い方について説明し，応用的な活用方法についても紹介いたします．

## Converse API とは

Converse API とは，統一的なインターフェースで Amazon Bedrock のモデルを容易に呼び出すことが可能な，チャット用途に特化した API です．推論パラメーターなどのモデル毎の固有の差分を意識せず，モデル ID のみを変更することで，異なるモデルを呼び出すことが可能です．本 API のその他の特徴は以下の通りです．

- マルチターン対話が容易に可能
- 画像の Base64 エンコードが不要
- **Tool use (function calling) が可能** (以下のモデルが対応)
  - Anthropic Claude3
  - Mistral AI Large
  - Cohere Command R and Command R+

本記事では，3 つ目に挙げた Tool use の活用方法について説明し，Claude3 で実際にチャットアプリで活用する際の Tips を紹介します．

## Tool use とは

Tool use (function calling) とは，外部ツールや関数（ツール）を定義・呼び出すことにより，Claude3 の能力を拡張する機能です．事前に定義されたツールに Claude3 がアクセスすることで，必要に応じていつでもツールを呼び出すことができ，Claude3 が通常できないような複雑なタスクを自動化できるようになります．

重要な点として，Claude3 が能動的にツールを実行するわけではなく，どのツールをどのような引数で呼ぶべきかをユーザーに依頼し，ユーザーがツールを実行します．その後，ツールの実行結果を Claude3 に伝え，ツールの実行結果に基づいて Claude3 が回答を生成します．具体的な仕組みについては次章で説明します．

![tool_use.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/fe887858-0d9a-9350-06e7-7ee673ebe7e1.png)

## Tool use の仕組み

以下のようなステップで，Tool use を利用できます．

- Step1: ツールの定義とプロンプトを Claude3 に送信
- Step2: Claude3 からツール実行のリクエストを取得
- Step3: ユーザーがツールを実行
- Step4: ツールの実行結果を Claude3 に送信
- Step5: ツールの実行結果に Claude3 が回答を生成

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/258954f4-6ab2-9222-dd3b-19c9d09e110c.png)

以降，天気予報検索ツールを利用する場合を例として，各ステップについて詳細に説明します．

### Step1: ツールの定義とプロンプトを Claude3 に送信

まず，`ToolsList`クラスを作成し，天気予報検索ツールをメソッドとして定義しておきます．なお，以下の関数は簡単のため，実際の天気予報を取得せず，特定の文字列を返す機能のみを実装しています．

```python
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

```python
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

```python
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

なお，上記の事象は，ConverseStream API でも同様に発生することを確認しており，Claude3 特有の事象である可能性があります．（2024/06/09 時点）．また，[Anthropic 公式の Tool use の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/04_complete_workflow.ipynb)においても，レスポンスにテキストが含まれることを示唆する記述があります．

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

gif を見せる感じか？

## 工夫点

### ConverseStream API の利用

### Tool use の活用

## DeepDive 系の話

色々自分だけが気づいた点があるはず

## まとめ

本日は Amazon Bedrock で昨日リリースされた Claude 3 Opus を中心に記載させていただきました。今後はどのようなビジネスユースケースで活用し、付加価値を提供できるかを検討しつつ、Agent for Amazon Bedrock なども活用し、より高度なサービスの提供を実施していきたい。

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
