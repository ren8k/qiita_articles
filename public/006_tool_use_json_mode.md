---
title: Amazon Bedrock Converse APIで Claude3 の JSON モードを利用する
tags:
  - AWS
  - bedrock
  - Python
  - LLM
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

<!-- 株式会社 NTT データ デジタルサクセスコンサルティング事業部の  -->

最近 Bedrock の Converse API にハマっている [@ren8k](https://qiita.com/ren8k) です．
前から気になっていたので，今回は JSON モードについて調べ，実際に利用してみました．
実際に Converse API を利用した例などが見当たらなかったので，今回はその辺りをまとめてみました．

また，Claude3.5 Sonnet を利用して検証してみました．

- Converse API を利用し，Claude3 の JSON モードを利用することができるのか
- どのような利用が可能なのかを検証してみました．

:::note
Converse API や，Tool use については，以下の記事にて詳細に解説しております．是非ご覧ください．
:::

https://qiita.com/ren8k/items/64c4a3de56b886942251

## JSON モードとは

[JSON モード](https://docs.anthropic.com/en/docs/build-with-claude/tool-use#json-mode)は，Claude3 に JSON 形式で回答させる方法です．ただし，実態としては，Tool use 利用時，Claude3 がツールへの入力を JSON 形式でレスポンスする性質を利用しているだけです．

JSON モードは，以下のステップで利用することができます．

- Step1. ツールの定義とプロンプトを Claude3 に送信
- Step2. Claude3 からツール実行のリクエストを取得し，JSON 部を抽出

![json_mode.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c8159e84-fbeb-3ba1-dd7b-732f10fb8bc1.png)

具体的に説明すると，ユーザー側で，実際には存在しない「架空のツール」を定義しておき，このツールの入力スキーマとして，求める出力の構造を指定します．この「架空のツール」を Claude3 に送信することで，Claude3 はこのツールが実在すると思い込み，指定されたスキーマに従って JSON 形式の入力を生成します．この生成された JSON 形式のツールの入力が，ユーザーが求める出力そのものとなります．

実際にコードを見た方がイメージが湧くと思いますので，以降では，具体的な利用例を示します．

## 利用例 1（感情分析）

テキストの感情分析を行い、その結果を構造化された JSON 形式で得るタスクを考えます．例えば，`「私はとても幸せです．」`という入力に対し，期待する JSON 出力は以下とします．

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

続いて，ツールの定義とプロンプトを Claude3 に送信します．プロンプトでは，`target_text` にて定義した `私はとても幸せです。` という文章に対し，架空のツール`print_sentiment_scores`を利用するように指示しております．

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

{tool_name} ツールのみを利用すること。各感情スコアは，数値で表現しなさい。
"""

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

Converse API の引数 `toolConfig` にて，`toolChoice` を指定することで，Claude3 に対してツールを使用するよう強制することができます．特に， `tool` というフィールドにツール名を指定することで，Claude3 は指定されたツールを必ず使用するようになります．詳細については，[AWS 公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolChoice.html)や，[Anthropic 公式の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb)をご参照下さい．
:::

:::note
`toolChoice` でツールの利用を強制していますが，プロンプトでも，`{tool_name} ツールのみを利用すること。` という指示を行っております．これは，[Anthropic 公式の学習コンテンツ](https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb)のプロンプト例に倣ったものです．
:::

### Step2. Claude3 からツール実行のリクエストを取得し，JSON 部を抽出

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

## 利用例 2（マルチクエリ）

公式でも description を詳細に書くと良い，と書かれている．

https://docs.anthropic.com/en/docs/tool-use-examples

## 利用例（画像解析）

## 参考

https://github.com/anthropics/courses/blob/master/ToolUse/03_structured_outputs.ipynb

https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb

## まとめ

本日は Amazon Bedrock で昨日リリースされた Claude 3 Opus を中心に記載させていただきました。今後はどのようなビジネスユースケースで活用し、付加価値を提供できるかを検討しつつ、Agent for Amazon Bedrock なども活用し、より高度なサービスの提供を実施していきたい。

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
