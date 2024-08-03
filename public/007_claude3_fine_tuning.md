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
- データセットを S3 へアップロード
- fine-tuning job の実行
- プロビジョンドスループットの購入
- fine-tuning したモデルの実行
- モデルの評価

## 利用申請

執筆時点（2024/07/27）では，Amazon Bedrock で Claude3 Haiku を fine-tuning するには，[AWS サポートに申請が必要](https://aws.amazon.com/jp/about-aws/whats-new/2024/07/fine-tuning-anthropics-claude-3-haiku-bedrock-preview/)です．サポートチケット作成時，サービスとして「Bedrock」を選択し，カテゴリとして「Models」を選択して下さい．

## データセットの作成

本検証では，Claude3 Haiku にドメイン知識を獲得させることを目的として，Amazon Bedrock に関する fine-tuning 用データセットを準備しました．データセットとして，AWS 公式ドキュメントから作成された質問と回答のペアを利用しています．以降，本検証を行う際に検討した事項や検証方針，データセットの準備・作成方法について説明します．

### 利用するデータセットの方針

オープンソースで公開されている日本語データセットとして，[databricks-dolly-15k-ja](https://huggingface.co/datasets/kunishou/databricks-dolly-15k-ja) や [databricks-dolly-15k-ja-gozaru](https://huggingface.co/datasets/bbz662bbz/databricks-dolly-15k-ja-gozaru?row=99) などが挙げられます．databricks-dolly-15k-ja-gozaru は，LLM の応答の語尾（口調）を「ござる」にするためのユニークなデータセットです．しかし，Claude3 Haiku の性能であれば，このデータセットで fine-tuning せずとも，システムプロンプトで指示するだけで同様の効果が得られると予想されます．そのため，このデータセットを使用しての fine-tuning は，その効果を実感しにくい可能性があります．

そこで，本検証では，Claude3 Haiku に出力形式を学習させるのではなく，ドメイン知識を獲得させることを目的としました．具体的には，Claude3 Haiku の事前学習データに含まれていないと考えられる「Amazon Bedrock」の知識を学習させるためのデータセットを準備することにしました．

また，以下の AWS 公式ブログでは fine-tuning のパフォーマンスを最適化するために，まずは小規模かつ高品質のデータセット（50-100 件）で試すことを推奨しています．この推奨に基づき，本検証でも 100 件未満のデータセットで fine-tuning を行うことにしました．

https://aws.amazon.com/jp/blogs/machine-learning/fine-tune-anthropics-claude-3-haiku-in-amazon-bedrock-to-boost-model-accuracy-and-quality/

:::note
[databricks-dolly-15k](https://huggingface.co/datasets/databricks/databricks-dolly-15k) は，Databricks が公開した 15,000 の指示-応答ペアを含むデータセットです．[databricks-dolly-15k-ja-gozaru](https://huggingface.co/datasets/bbz662bbz/databricks-dolly-15k-ja-gozaru?row=99) は，databricks-dolly-15k を日本語訳したデータセットである [databricks-dolly-15k-ja](https://huggingface.co/datasets/kunishou/databricks-dolly-15k-ja) の応答の語尾を「ござる」に置換したデータセットであり，LLM の fine-tuning の検証によく利用されております．
:::

### 利用する訓練データ

本検証では，AWS Machine Learning Blog の記事 “[Improve RAG accuracy with fine-tuned embedding models on Amazon SageMaker](https://aws.amazon.com/jp/blogs/machine-learning/improve-rag-accuracy-with-fine-tuned-embedding-models-on-amazon-sagemaker/)” で利用されている [Amazon Bedrock FAQs](https://aws.amazon.com/jp/bedrock/faqs/) のデータセットを fine-tuning 用の訓練データとして利用しました．データセットは以下のリポジトリで公開されています．

https://github.com/aws-samples/fine-tune-embedding-models-on-sagemaker/blob/main/sentence-transformer/multiple-negatives-ranking-loss/training.json

本データセットは，[Amazon Bedrock FAQs](https://aws.amazon.com/jp/bedrock/faqs/)を基に作成されており，JSON 形式で 計 85 個の質問と回答のペアが保存されています．以下に，データセットの一部を示します．JSON のキー`sentence1`が質問，`sentence2`が回答となっております．

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

以下の AWS 公式ドキュメントを基に，Claude3 Opus で検証データを作成しました．その際，下記のドキュメントを PDF 化しておき，Amazon Bedrock の Converse API の **Document chat** と **Json mode** を利用することで，比較的容易に JSON 形式でかつ 品質の高い QA 形式のデータセットを作成することができました．

https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html

以下に示すコードを利用し，計 32 個の質問と回答のペアを生成しました．

<details open><summary>Python実装（折り畳めます）</summary>

Tool use の設定を行うためのコード `tool_config.py` と，検証データを作成するためのコード `create_val_dataset.py` を示します．`tool_conifg.py` では，`question` と `answer` を要素とする JSON を Array 型で生成するように設定しており，プロンプトで 32 個生成するように指示しています．なお，Json mode で利用するため，ツール自体の定義は行っておりません．

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

`create_val_dataset.py` では，AWS 公式ドキュメントの PDF ファイルをバイナリ形式で読み込み，Converse API の Document chat で直接入力入力しています．加えて，Converse API の Tool use の設定値で `toolChoice` を指定することで，ツールの呼び出しを強制しています．これにより，Converse API のレスポンスに JSON 形式のツール呼び出しのリクエスト（生成された QA 形式の検証データセット）が確実に含まれるようになります．

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

上記のコードでは，外部の JSON ファイルに 32 個の QA 形式の検証データを保存しています．実際に生成された検証データの一部を示します．プロンプトで指示した通り，QA 形式となっていることを確認できます．

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

Claude3 Haiku で fine-tuning を行うには，前処理として，訓練データおよび検証データを以下のフォーマットの JSON Lines (JSONL) 形式にする必要があります．具体的には，システムプロンプト，ユーザーのプロンプト，LLM のレスポンスを 各 JSON レコードとして保存します．

```python
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
{"system": string, "messages": [{"role": "user", "content": string}, {"role": "assistant", "content": string}]}
```

本検証では，以下に示すコードで前処理を行いました．python コード実行時の引数で，システムプロンプト，入力ファイル（訓練データ or 検証データ），出力ファイル，入力ファイルで利用されている JSON のキーを指定することが可能です．

<details open><summary>Python実装（折り畳めます）</summary>

```python:preprocess.py
import argparse
import json


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--system-prompt",
        type=str,
        default="You are a high-performance QA assistant that responds to questions concisely, accurately, and appropriately.",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="../../dataset/rawdata/validation.json",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="../../dataset/preprocessed/claude3_ft_validation.jsonl",
    )
    parser.add_argument("--prompt-key", type=str, default="question")
    parser.add_argument("--completion-key", type=str, default="answer")

    return parser.parse_args()


def preprocess(args: argparse.Namespace) -> None:
    """
    Preprocess the input JSON file to the format that can be used for claude3's fine-tuning.
    Input JSON file should have the structure of a list of dictionaries.
    Below is an example of the input JSON file.
    [
        {
            "question": "What is the capital of France?",
            "answer": "Paris"
        },
        ...
    ]
    """
    with open(args.input_file, "r") as f_in, open(args.output_file, "w") as f_out:
        input_json = json.load(f_in)
        for data in input_json:
            prompt = data[args.prompt_key]
            completion = data[args.completion_key]

            new_data = {}
            new_data["system"] = args.system_prompt
            new_data["messages"] = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": completion},
            ]

            f_out.write(json.dumps(new_data) + "\n")


def main(args: argparse.Namespace) -> None:
    preprocess(args)
    print("Conversion completed!")


if __name__ == "__main__":
    args = get_args()
    main(args)

```

例えば，訓練データの前処理を行いたい場合，以下の shell のようなコマンドを実行します．（`argparse`の default 値は検証データに合わせているため，検証データの前処理を行う際は，引数指定は不要です．）

```bash:run_preprocess.sh
#!/bin/bash

INPUT="../../dataset/rawdata/training.json"
OUTPUT="../../dataset/preprocessed/claude3_ft_training.jsonl"
PROMPT_KEY="sentence1"
COMPLETION_KEY="sentence2"

python3 preprocess.py \
    --input-file $INPUT \
    --output-file $OUTPUT \
    --prompt-key $PROMPT_KEY \
    --completion-key $COMPLETION_KEY
```

</details>

上記のコードでは，外部の jsonl ファイルに 指定のフォーマットでデータセットを保存しています．参考に，実際にフォーマットした訓練データの一部を示します．

```jsonl
{"system": "You are a high-performance QA assistant that responds to questions concisely, accurately, and appropriately.", "messages": [{"role": "user", "content": "What is Amazon Bedrock and its key features?"}, {"role": "assistant", "content": "Amazon Bedrock is a fully managed service that offers a choice of high-performing foundation models along with a broad set of capabilities for building generative AI applications, simplifying development with security, privacy, and responsible AI features."}]}
{"system": "You are a high-performance QA assistant that responds to questions concisely, accurately, and appropriately.", "messages": [{"role": "user", "content": "How can I get started with using Amazon Bedrock?"}, {"role": "assistant", "content": "With the serverless experience of Amazon Bedrock, you can quickly get started by navigating to the service in the AWS console and trying out the foundation models in the playground or creating and testing an agent."}]}
```

## データセットを S3 へアップロード

作成した訓練データ，検証データを，米国西部 (オレゴン) リージョンの S3 バケットにアップロードする必要があります．[本リポジトリ](https://github.com/ren8k/aws-bedrock-claude3-fine-tuning/tree/main/dataset/preprocessed)では，先程のステップで作成した前処理済みのデータセットを公開しております．本リポジトリ上のデータを利用する場合，以下のコマンドで，本データセットのアップロードが可能です．コマンド中の `<your bucket>` は、任意のバケット名に置き換えてください。

```bash
aws s3 cp dataset/preprocessed/ s3://<your bucket>/claude3-haiku/dataset --recursive
```

## fine-tuning job の実行

### コンソール上での実施手順

以降，[Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock)上での，Claude3 Haiku の fine-tuning の実施手順を説明します。

オレゴンリージョンで、Amazon Bedrock コンソールから、左側にあるナビケーションペインの [基盤モデル] セクションから [カスタムモデル] を選択します。

![スクリーンショット 2024-07-24 121526.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/3d928b42-a495-9bb8-b948-48bdc49daa74.png)

右側の [モデルをカスタマイズ] を選択し，[微調整ジョブを作成] を選択します．

![スクリーンショット 2024-07-24 121726.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e29259df-c918-b618-5564-d8a5221d34e5.png)

微調整ジョブ (fine-tuning job) の作成画面の [ソースモデル] の [モデルを選択] を選択します．

![スクリーンショット 2024-07-24 121626.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/829e16d0-e547-90fd-5a44-d14cb2612998.png)

Claude3 Haiku を選択し，[適用] を押下します．

![スクリーンショット 2024-07-24 121845.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2ef34d9d-125a-f632-58ad-a5f05aba2c2a.png)

fine-tuning job の設定画面で，以下の情報を入力します．

- 微調整されたモデル名: 任意のモデル名
- ジョブ名: fine-tuning job 名
- 入力データ: 先程アップロードした訓練データと検証データの S3 パス

![スクリーンショット 2024-07-26 203659.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/706fad24-c0a1-ef54-c6ee-76366f2b029a.png)

fine-tuning job のハイパーパラメータを設定します．なお，エポック数のデフォルト値は 2 ですが，本検証は 10 エポックで実施し，その他のパラメータはデフォルト値としました．

| ハイパーパラメータ        | 内容                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| エポック                  | 訓練データセット全体を繰り返し学習する回数（最大 10epoch）                                 |
| バッチサイズ              | モデルのパラメータ更新で使用するデータの数                                                 |
| Learning rate multiplier  | 基本学習率 (base learning rate) を調整するための係数                                       |
| Early stopping (早期停止) | validation loss が一定のエポック数で改善しない場合に学習を停止する，過学習を防ぐための手法 |
| 早期停止のしきい値        | Early stopping を判断するための validation loss の改善幅のしきい値                         |
| 早期停止ペイシェンス      | Early stopping を判断するまでに許容するエポック数                                          |

![スクリーンショット 2024-07-26 203928.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/32b298e0-1e81-0226-7e57-f50975d3902b.png)

fine-tuning 実行時の training loss, validation loss の推移を記録するため，保存先の S3 URI を指定します．また，サービスロールは新規作成します．その後，[モデルを微調整] を選択し，fine-tuning job を実行します．

![スクリーンショット 2024-07-26 203949.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c6309f0a-0bf5-71eb-02e4-5d2549e1bdf9.png)

fine-tuning job が開始されます．ステータス が `トレーニング` から `完了` に変わるまで待ちます．

![スクリーンショット 2024-07-26 204256.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9d38d8ae-8e7b-5556-ff99-2e765414dfdc.png)

fine-tuning job が完了すると，ステータスが `完了` に変わります．今回の検証では，2 時間程度で完了しました．

![スクリーンショット 2024-07-31 210226.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a3cd20a0-5cfc-22f3-3fc2-632bb3d228a9.png)

[モデル] を選択し、モデル名を選択すると、モデル ARN ジョブ ARN，出力データ（epoch 毎の training loss, validation loss の値）の保存先などの詳細情報を確認できます。

![スクリーンショット 2024-07-31 210436.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/cf7efd19-d8b7-dc72-3ec3-2e00961bc10a.png)

![スクリーンショット 2024-07-31 210710.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a01f30b2-2dc1-aa52-a9c4-1210620a0866.png)

### training loss，validation loss の観察

出力データとして，エポック毎の training loss, validation loss の値が記録された CSV ファイルが S3 に保存されます．これらの値を観察することで，fine-tuning が正常に行えているかを判断することができます．

以下に fine-tuning 実行時の trainin loss, validation loss の推移を示します．training loss, validation loss 共に，エポック数が増えるにつれて減少しており，適切に学習が行えていることが確認できます．また，5 ~ 7 エポック目で validation loss が改善しておらず，7 エポック目で Early stopping が発生していることが確認できます．

![loss_curves.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1425b22d-df25-23e1-cabc-adde882eedbf.png)

:::note warn
CSV ファイルにはステップ毎の loss が記録されていますが，上図ではエポック毎の loss の平均値を示しています．
:::

## プロビジョンドスループットの購入

fine-tuning したモデルをデプロイするために，プロビジョンドスループットを購入する必要があります．以降，コンソール上でのプロビジョンドスループットの購入手順を説明します．

Bedrock コンソールの [カスタムモデル] の画面で微調整されたモデルを選択し，「プロビジョンドスループットの購入」を選択します．

![スクリーンショット 2024-08-02 150103.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f1d646d4-4880-4523-a355-cb8469bfacb2.png)

プロビジョンドスループットの名前を入力し，契約期間を選択します．今回の検証では 1 時間程度しか利用しないため， `No commitment` を選択しました．その後，[プロビジョンドスループットを購入] を選択します．

![スクリーンショット 2024-08-01 105444.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/d834c793-e9e1-d1e4-3f11-ae244ae497d0.png)

購入確認画面が表示されるので，チェックボックスを付け [購入を確認] を選択します．

![スクリーンショット 2024-08-01 105636.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1ed625c1-2bcd-d070-7b9c-7cafbfe1558d.png)
![スクリーンショット 2024-08-01 105725.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a82f5929-7a33-54e7-1a82-ce2df56af95b.png)

今回の検証では，20 分程度で完了しました．

![スクリーンショット 2024-08-01 111945.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f8dc0758-db18-b764-00af-07a7c064f953.png)

作成されたプロビジョンドスループットを選択すると，プロビジョンドスループットの ARN などを確認できます．こちらは，Boto3 を利用してモデルで推論する際に利用します．

![スクリーンショット 2024-08-01 115519.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/0887eea0-7cd4-c4ea-a220-ac5c4b7e4661.png)

## fine-tuning したモデルの実行

Amazon Bedrock のプレイグラウンドおよび，AWS SDK for Python (Boto3) を利用して，実際に fine-tuning したモデルで推論してみます．

### プレイグラウンドで実行

Amazon Bedrock コンソール上でプレイグラウンドの[チャット]を選択し，モデルを選択します．その際，カスタムモデルを選択し，先程 fine-tuning したモデルを選択します．

![スクリーンショット 2024-08-01 112305.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e72815e6-a4e2-ab66-253a-c737e304b8d7.png)

プレイグラウンドで利用されるモデル名が，fine-tuning したモデル名になっていることが確認できます．試しに，`What is Knowledge Bases for Amazon Bedrock?` という質問を入力し，[実行] ボタンを押下しました．

![スクリーンショット 2024-08-01 114125.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/10f8e93b-d458-5498-3644-39f4f5a8de0f.png)

以下が，fine-tuning したモデルの回答です．それらしい回答が得られています．

> Knowledge Bases for Amazon Bedrock is a feature that allows you to seamlessly integrate structured and unstructured data sources into your large language model (LLM) applications built on Amazon Bedrock. This feature enables you to enhance the context and knowledge available to your models, leading to more informed and relevant responses.
>
> With Knowledge Bases for Amazon Bedrock, you can connect your LLM applications to a variety of data sources, including databases, content management systems, enterprise applications, and file storage services. The feature supports a wide range of data formats, including structured data (e.g., CSV, Excel, SQL), unstructured data (e.g., PDF, Word, HTML), and semi-structured data (e.g., JSON, XML).

:::note warn
コンソール上からは，システムプロンプトを設定することはできないようでした．
:::

<!-- ![スクリーンショット 2024-08-01 114232.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/673ffe7a-0e0a-83b4-aa45-ea47484b7ebe.png)
![スクリーンショット 2024-08-01 114622.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/50db2da2-01d6-a373-d023-7dc20379fa1c.png)
![スクリーンショット 2024-08-01 114705.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1a02946c-5f8e-9ae6-f46a-8cbbd01ea977.png) -->

### AWS SDK for Python (Boto3) で実行

AWS SDK for Python (Boto3) を利用し，API 経由でインポートしたモデルを呼び出すことも可能です．具体的には，Amazon Bedrock の InvokeModel API を利用し，引数の modelId にインポートしたプロビジョンドスループットの ARN を指定することで，推論を行えます．

```python:invoke_ft_model.py
import json

import boto3

model_id = "<provisioned throughput arn>"

system_prompt = "You are a high-performance QA assistant that responds to questions concisely, accurately, and appropriately."
prompt = "What can you do with Amazon Bedrock?"

client = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")

response = client.invoke_model(
    body=json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": f"{prompt}"}],
            "temperature": 0.1,
            "top_p": 0.9,
            "system": f"{system_prompt}",
        }
    ),
    modelId=model_id,
)
output = response.get("body").read().decode("utf-8")
response_body = json.loads(output)
response_text = response_body["content"][0]["text"]
print(response_text)

```

上記のコードを実行すると、以下が出力されました。`What can you do with Amazon Bedrock?` という質問に対して，適切な回答が得られています．

> Amazon Bedrock is a fully managed service that enables developers to build, deploy, and scale generative AI applications quickly and easily. With Amazon Bedrock, you can create generative AI applications that can generate human-like text, images, code, and other content, as well as engage in open-ended conversations and complete a variety of tasks.

## 評価

### 設定

- 用意した質問は以下．
- 想定回答は事前に用意．

### 評価指標

- langchain を利用

### 結果

### 考察

### 補足実験

日本語の場合

---

---

---

```
## TODO

- 実際にモデルを実行してみる，モデルの評価（どのように結論づけるか）
- 本橋さんみたいに表を作成する．表の一番右に，総評を書いたほうがわかりやすいかも．
- 図の一部は小さくした方が見やすい．．．
```

| プロンプト                                  | Fine-tuning model の回答                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Base model の回答                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| What can you do with Amazon Bedrock?        | Amazon Bedrock is a fully managed service that provides a quick, effective, and secure path to building generative AI applications powered by foundation models from Amazon, Anthropic, Stability AI, Cohere, and other integrated providers. It simplifies the creation and deployment of cutting-edge customized models and foundational models for a wide range of natural language processing (NLP), text-to-image, and speech-to-text use cases, all while focusing on security, data privacy, and responsible AI.                                                                                                                                                                                                                                                    | Amazon Bedrock is a platform that provides developers with a set of tools and services to build, deploy, and manage conversational AI applications. Here are some of the key things developers can do with Amazon Bedrock:<br><br>1. Build conversational AI models: Bedrock provides access to pre-trained language models that can be fine-tuned for various natural language processing (NLP) tasks, such as text generation, intent detection, and entity extraction.<br><br>2. Deploy and manage models: Bedrock makes it easier to deploy and manage conversational AI models by providing a scalable, cloud-based infrastructure. Developers can use Bedrock to host, monitor, and update their models. |
| What is Knowledge Bases for Amazon Bedrock? | Knowledge Bases for Amazon Bedrock is a feature that allows you to seamlessly integrate structured and unstructured data sources into your large language model (LLM) applications built on Amazon Bedrock. This feature enables you to enhance the context and knowledge available to your models, leading to more informed and relevant responses.<br><br>With Knowledge Bases for Amazon Bedrock, you can connect your LLM applications to a variety of data sources, including databases, content management systems, enterprise applications, and file storage services. The feature supports a wide range of data formats, including structured data (e.g., CSV, Excel, SQL), unstructured data (e.g., PDF, Word, HTML), and semi-structured data (e.g., JSON, XML). | Unfortunately, I do not have any specific information about "Knowledge Bases for Amazon Bedrock." Bedrock is a platform provided by Amazon, but I do not have detailed knowledge about its capabilities or features. Knowledge bases are typically collections of structured data that can be used to provide information, but without more context about how this relates to Amazon Bedrock, I cannot provide any details. My knowledge is limited, so I cannot give you a substantive answer about this particular topic. I'd suggest checking the Amazon documentation or other reliable sources to learn more about Amazon Bedrock and any associated knowledge base capabilities.                         |

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
```
