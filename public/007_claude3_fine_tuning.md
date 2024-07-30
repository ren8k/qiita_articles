---
title: Amazon Bedrock で Claude3 Haiku を fine-tuning する
tags:
  - AWS
  - bedrock
  - Python
  - claude
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

<!-- 株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です． -->

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

Claude3 の FT をやってみたので，その内容を共有します．

本検証で利用したコードは以下のリポジトリで公開しています．

https://github.com/ren8k/aws-bedrock-claude3-fine-tuning

## 利用手順

- 利用申請
- データセットの作成
- S3 へのアップロード
- fine-tuning Job の実行
- プロビジョンスループットの購入
- 実際にモデルを実行してみる

## 利用申請

執筆時点（2024/07/27）では，Amazon Bedrock で Claude3 Haiku を fine-tuning するには，[AWS サポートに申請が必要](https://aws.amazon.com/jp/about-aws/whats-new/2024/07/fine-tuning-anthropics-claude-3-haiku-bedrock-preview/)です．サポートチケット作成時，サービスとして「Bedrock」を選択し，カテゴリとして「Models」を選択して下さい．

## データセットの作成

### 方針

オープンソースで公開されている日本語データセットとして，[databricks-dolly-15k-ja](https://huggingface.co/datasets/kunishou/databricks-dolly-15k-ja) や [databricks-dolly-15k-ja-gozaru](https://huggingface.co/datasets/bbz662bbz/databricks-dolly-15k-ja-gozaru?row=99) などが挙げられます．databricks-dolly-15k-ja-gozaru は，LLM の応答の語尾を「ござる」にするためのユニークなデータセットです．しかし，Claude3 Haiku の性能であれば，このデータセットで fine-tuning せずとも，システムプロンプトで指示するだけで同様の効果が得られると予想されます．そのため，このデータセットを使用しての fine-tuning は，その効果を実感しにくい可能性があります．

そこで，本検証では，Claude3 Haiku に出力形式を学習させるのではなく，ドメイン知識を獲得させることを目的としました．具体的には，Claude3 Haiku の事前学習データに含まれていないと考えられる「Amazon Bedrock」の知識を学習させるためのデータセットを準備することにしました．

また，以下の AWS 公式ブログでは fine-tuning のパフォーマンスを最適化するために，まずは小規模かつ高品質のデータセット（50-100 件）で試すことを推奨しています．この推奨に基づき，本検証でも 100 件未満のデータセットで fine-tuning を行うことにしました．

https://aws.amazon.com/jp/blogs/machine-learning/fine-tune-anthropics-claude-3-haiku-in-amazon-bedrock-to-boost-model-accuracy-and-quality/

:::note
[databricks-dolly-15k](https://huggingface.co/datasets/databricks/databricks-dolly-15k) は，Databricks が公開した 15,000 の指示-応答ペアを含むデータセットです．[databricks-dolly-15k-ja-gozaru](https://huggingface.co/datasets/bbz662bbz/databricks-dolly-15k-ja-gozaru?row=99) は，databricks-dolly-15k を日本語訳したデータセットである [databricks-dolly-15k-ja](https://huggingface.co/datasets/kunishou/databricks-dolly-15k-ja) の応答の語尾を「ござる」に置換したデータセットであり，LLM の fine-tuning の検証によく利用されております．
:::

### 利用する訓練データ

本検証では，AWS Machine Learning Blog の記事 “[Improve RAG accuracy with fine-tuned embedding models on Amazon SageMaker](https://aws.amazon.com/jp/blogs/machine-learning/improve-rag-accuracy-with-fine-tuned-embedding-models-on-amazon-sagemaker/)” で利用されている [Amazon Bedrock FAQs](https://aws.amazon.com/jp/bedrock/faqs/) のデータセットを fine-tuning 用の訓練データとして利用しました．データセットは以下のリポジトリで公開されています．

https://github.com/aws-samples/fine-tune-embedding-models-on-sagemaker/blob/main/sentence-transformer/multiple-negatives-ranking-loss/training.json

本データセットは，[Amazon Bedrock FAQs](https://aws.amazon.com/jp/bedrock/faqs/)を基に作成されており，json 形式で 計 85 個の質問と回答のペアが保存されています．以下に，データセットの一部を示します．json のキー`sentence1`が質問，`sentence2`が回答となっております．

```json
[
  {
    "sentence1": "What is Amazon Bedrock and its key features?",
    "sentence2": "Amazon Bedrock is a fully managed service that offers a choice of high-performing foundation models along with a broad set of capabilities for building generative AI applications, simplifying development with security, privacy, and responsible AI features."
  },
  {
    "sentence1": "How can I get started with using Amazon Bedrock?",
    "sentence2": "With the serverless experience of Amazon Bedrock, you can quickly get started by navigating to the service in the AWS console and trying out the foundation models in the playground or creating and testing an agent."
  }
]
```

ただし，本データセットは 85 件と多くはないため，本データを訓練データと検証データに分割するのではなく，検証データは別途作成することにしました．

:::note
本検証で上記のデータセットを選んだ理由としては，データの品質が高く，ライセンス的にも問題ないためです．また，Claude3 Haiku の事前学習データには含まれてないと考えられる Amazon Bedrock という特定ドメインの知識を学習させるための題材としては適切であると考えたためです．
:::

### 検証データの作成

以下の AWS 公式ドキュメントを基に，Claude3 Opus で検証データを作成しました．その際，Amazon Bedrock の Converse API の **Document chat** と **Json mode** を組合せることで，比較的容易に JSON 形式でかつ 品質の高い QA 形式のデータセットを作成することができました．

https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html

以下に示すコードを利用し，計 32 個の質問と回答のペアを生成しました．

<details open><summary>Python実装</summary>

以下に，Tool use の設定を行うための `tool_config.py` と，検証データを作成する `create_val_dataset.py` を示します．`tool_conifg.py` では，`question` と `answer` の Json を Array 型で取得するように設定しており，プロンプトで 32 個生成するように指示しています．

```python:tool_conifg.py
class ToolConfig:
    tool_name = "QA_dataset_generator"
    no_of_dataset = 32

    description = f"""
    与えられるドキュメントに基づいて、LLMのFine-Tuning用のValidationデータセットを作成します。
    具体的には、ドキュメントの内容を利用し、Amazon Bedrockに関する質問文と回答文のペアを生成します。

    <example>
    question: What is Amazon Bedrock and its key features?
    answer: Amazon Bedrock is a fully managed service that offers a choice of high-performing foundation models along with a broad set of capabilities for building generative AI applications, simplifying development with security, privacy, and responsible AI features.
    </example>

    <rules>
    - 必ず{no_of_dataset}個の質問文と回答文のペアを生成すること。
    - 英語で回答すること。
    - JSON形式で回答すること。
    - Amazon Bedrockについて、多様な質問と回答を作成すること。
    </rules>
    """

    tool_definition = {
        "toolSpec": {
            "name": tool_name,
            "description": description,
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "description": f"Validationデータ用の質問文と回答文のセット。必ず{no_of_dataset}個生成すること。",
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "Validationデータ用の質問文。",
                                    },
                                    "answer": {
                                        "type": "string",
                                        "description": "Validationデータ用の回答文。",
                                    },
                                },
                                "required": ["question", "answer"],
                            },
                        },
                    },
                    "required": ["dataset"],
                }
            },
        }
    }

```

★ ここから！！！！

```python:create_val_dataset.py
import argparse
import json
from pprint import pprint

import boto3
from botocore.config import Config
from tool_config import ToolConfig


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--region",
        type=str,
        default="us-west-2",
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default="anthropic.claude-3-opus-20240229-v1:0",
    )
    parser.add_argument(
        "--order",
        type=str,
        default="LLM の Fine Tuning 用のデータセットを作成しなさい。",
    )
    parser.add_argument(
        "--input-doc-path",
        type=str,
        default="./amazon_bedrock_user_docs.pdf",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="../../dataset/rawdata/validation.json",
    )

    return parser.parse_args()


def document_chat(region: str, model_id: str, prompt: str, doc_bytes: bytes) -> dict:
    retry_config = Config(
        region_name=region,
        connect_timeout=300,
        read_timeout=300,
        retries={
            "max_attempts": 10,
            "mode": "standard",
        },
    )
    client = boto3.client("bedrock-runtime", config=retry_config, region_name=region)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "document": {
                        "name": "Document",
                        "format": "pdf",
                        "source": {"bytes": doc_bytes},
                    }
                },
                {"text": prompt},
            ],
        }
    ]

    # Send the message to the model
    response = client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={
            "maxTokens": 3000,
        },
        toolConfig={
            "tools": [ToolConfig.tool_definition],
            "toolChoice": {
                "tool": {
                    "name": ToolConfig.tool_name,
                },
            },
        },
    )
    pprint(response)
    return response


def extract_tool_use_args(content: list) -> dict:
    for item in content:
        if "toolUse" in item:
            return item["toolUse"]["input"]
    raise ValueError("toolUse not found in response content")


def main(args: argparse.Namespace) -> None:
    prompt = f"""
    {args.order}
    {ToolConfig.tool_name} ツールのみを利用すること。
    """
    print(prompt)

    with open(args.input_doc_path, "rb") as f:
        doc_bytes = f.read()

    # call converse API
    response: dict = document_chat(args.region, args.model_id, prompt, doc_bytes)
    response_content: list = response["output"]["message"]["content"]

    # extract json
    tool_use_args = extract_tool_use_args(response_content)

    # write to file
    with open(args.output_path, "w") as f:
        json.dump(tool_use_args["dataset"], f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    args = get_args()
    main(args)
```

</details>

以下に，実際に生成された検証データの一部を示します．プロンプトで指示した通り，QA 形式となっていることを確認できます．

```json
[
  {
    "question": "What is Amazon Bedrock?",
    "answer": "Amazon Bedrock is a fully managed service that offers a choice of high-performing foundation models along with capabilities for building generative AI applications, simplifying development with security, privacy, and responsible AI features."
  },
  {
    "question": "What can you do with Amazon Bedrock?",
    "answer": "With Amazon Bedrock, you can experiment with and evaluate top foundation models for your use cases, privately customize them with your own data using techniques like fine-tuning and retrieval augmented generation, and build agents that execute tasks using your enterprise systems and data sources."
  }
]
```

### データセットのフォーマット（前処理）

Claude3 Haiku で fine-tuning を行うためには，以下のフォーマットに変換する必要があります．

```python
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
```

## S3 へのアップロード

## fine-tuning Job の実行

## プロビジョンスループットの購入

## 実際にモデルを実行してみる

---

---

---

![スクリーンショット 2024-07-24 121726.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e29259df-c918-b618-5564-d8a5221d34e5.png)
![スクリーンショット 2024-07-24 121845.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2ef34d9d-125a-f632-58ad-a5f05aba2c2a.png)
![スクリーンショット 2024-07-26 203659.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/706fad24-c0a1-ef54-c6ee-76366f2b029a.png)
![スクリーンショット 2024-07-26 203928.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/32b298e0-1e81-0226-7e57-f50975d3902b.png)
![スクリーンショット 2024-07-26 203949.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c6309f0a-0bf5-71eb-02e4-5d2549e1bdf9.png)
![スクリーンショット 2024-07-26 204256.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9d38d8ae-8e7b-5556-ff99-2e765414dfdc.png)

## aaa

![スクリーンショット 2024-07-26 195723.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7862b159-f759-b7ec-02f9-146e426bcdb0.png)
![スクリーンショット 2024-07-26 195943.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/26169f6d-862f-287b-ddf2-70413d803264.png)
![スクリーンショット 2024-07-26 200145.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/229a40e6-a187-52e7-49bf-2ca1970efe30.png)
![スクリーンショット 2024-07-26 201355.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/bbc725cc-affa-90ca-fbea-5044abc44dbb.png)
![スクリーンショット 2024-07-26 201547.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/6ba0583f-6a33-99c6-6873-3a2ffc85990f.png)

## まとめ

本日は Amazon Bedrock で昨日リリースされた Claude 3 Opus を中心に記載させていただきました。今後はどのようなビジネスユースケースで活用し、付加価値を提供できるかを検討しつつ、Agent for Amazon Bedrock なども活用し、より高度なサービスの提供を実施していきたい。

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

</div></details>
