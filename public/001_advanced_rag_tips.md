---
title: Amazon Bedrock で Advanced RAG を実装する上での Tips
tags:
  - Python
  - AWS
  - rag
  - bedrock
  - KnowledgeBaseForAmazonBedrock
private: false
updated_at: '2024-06-10T11:02:12+09:00'
id: dcdb7f0c61fda384c478
organization_url_name: nttdata
slide: false
ignorePublish: false
---

## はじめに<!-- omit in toc -->

株式会社 NTT データ デザイン＆テクノロジーコンサルティング事業本部の [@ren8k](https://qiita.com/ren8k) です．
2024/05/01 に，「[Amazon Kendra と Amazon Bedrock で構成した RAG システムに対する Advanced RAG 手法の精度寄与検証](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)」という先進的で素晴らしい AWS 公式ブログが公開されました．

https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/

上記ブログの内容に感化され，2024/05/06 に，AWS SDK for Python (Boto3)を利用して，ブログで紹介されている Advanced RAG の再現実装を私の方で行いました．その際に，Advanced RAG を実現する上での実装方法や Claude3 を利用する際のプロンプトエンジニアリングで学べた点が多かったので，本ブログにまとめようと思います．なお，Advanced RAG の再現実装（Python）は[本リポジトリ](https://github.com/ren8k/aws-bedrock-advanced-rag-baseline)に公開していますので，興味のある方はご参照ください．

https://github.com/ren8k/aws-bedrock-advanced-rag-baseline

## TL;DR<!-- omit in toc -->

以下の Tips について重点的に解説しております．

- Claude3 のプロンプトエンジニアリングの工夫について
  - XML タグ，具体例，ロールプロンプティング，CoT の利用
  - システムプロンプトの工夫による回答形式の指示（JSON 出力）
- Bedrock，Knowledge Bases の並列実行について
  - Bedrock の`invoke_model`メソッド，Knowledge Bases の`retrieve`メソッドの利用例
  - `concurrent.futures.ThreadPoolExecutor` を利用した並列処理

## 目次<!-- omit in toc -->

- [構築したアーキテクチャ](#構築したアーキテクチャ)
- [実施手順](#実施手順)
  - [前提](#前提)
  - [Knowledge Bases for Amazon Bedrock の構築](#knowledge-bases-for-amazon-bedrock-の構築)
  - [コードの clone と環境構築](#コードの-clone-と環境構築)
  - [Advanced RAG の実行](#advanced-rag-の実行)
- [実装時の工夫](#実装時の工夫)
  - [step1. Pre-Retrieval: Claude3 を利用したクエリ拡張](#step1-pre-retrieval-claude3-を利用したクエリ拡張)
    - [1. プロンプトエンジニアリング（例・XML タグの利用）](#1-プロンプトエンジニアリング例xml-タグの利用)
    - [2. システムプロンプトおよび Claude3 の応答の事前入力の工夫](#2-システムプロンプトおよび-claude3-の応答の事前入力の工夫)
    - [3. JSON 形式で回答が生成されなかった場合に再度 Claude3 Haiku にリクエストを送信（リトライ）](#3-json-形式で回答が生成されなかった場合に再度-claude3-haiku-にリクエストを送信リトライ)
  - [step2. Retrieval: Knowledge Bases でのベクトル検索の並列実行](#step2-retrieval-knowledge-bases-でのベクトル検索の並列実行)
  - [step3. Post-Retrieval: Claude3 Haiku による関連度評価の並列実行](#step3-post-retrieval-claude3-haiku-による関連度評価の並列実行)
    - [1. プロンプトエンジニアリング（Role・XML タグの利用）](#1-プロンプトエンジニアリングrolexml-タグの利用)
    - [2. システムプロンプトの工夫](#2-システムプロンプトの工夫)
    - [3. LLM の関連度評価の並列実行](#3-llm-の関連度評価の並列実行)
  - [step4. Augment and Generate: Claude3 Haiku による回答生成](#step4-augment-and-generate-claude3-haiku-による回答生成)
    - [1. プロンプトエンジニアリング（Role・CoT・XML タグの利用）](#1-プロンプトエンジニアリングrolecotxml-タグの利用)
    - [2. システムプロンプトの工夫](#2-システムプロンプトの工夫-1)
- [まとめ](#まとめ)

## 構築したアーキテクチャ

再現実装の際に構築した Advanced RAG のアーキテクチャを以下に示します．

<img width="700" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/5de3eed4-e711-73dc-1d31-2301913d2a29.png">

[AWS 公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)とは異なり，retriever（検索器）として [Knowledge bases for Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) を利用しております．また，検証コストを最小限に抑えるため，ベクトルデータベース として [Pinecone](https://www.pinecone.io/) を利用しました．

Advanced RAG では，通常の RAG（Naive RAG）と異なり，検索前にクエリやデータのインデックス構造の最適化を行う Pre-Retrieval ステップと，検索後にクエリと検索結果を効果的に結合するための後処理を行い，LLM への入力を最適化する Post-Retrieval ステップが追加されています．公式ブログでは，以下の 4 つのステップで Advanced RAG の検証を行っております．

| ステップ | プロセス             | 処理内容                                   |
| -------- | -------------------- | ------------------------------------------ |
| step1    | Pre-Retrieval        | Claude3 を利用したクエリ拡張               |
| step2    | Retrieval            | Knowledge Bases でのベクトル検索の並列実行 |
| step3    | Post-Retrieval       | Claude3 Haiku による関連度評価の並列実行   |
| step4    | Augment and Generate | Claude3 Haiku による回答生成               |

各プロセスのワークフローとしては，以下のようになります．（以下は，関連度評価の結果，検索結果 1 および 3 のみを利用して回答生成を行っている例です．）

![advanced_rag_workflow_qiita.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/512712f0-4bc9-c1f1-5f05-36b4ad2c6049.png)

:::note info
Advanced RAG の詳細については，AWS 公式ブログ「[Amazon Kendra と Amazon Bedrock で構成した RAG システムに対する Advanced RAG 手法の精度寄与検証](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)」およびサーベイ論文 “[Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/abs/2312.10997)” [Yunfan Gao et al. (2023)] をご参照下さい．
:::

## 実施手順

[本リポジトリ](https://github.com/ren8k/aws-bedrock-advanced-rag-baseline)を利用した Advanced RAG の実行方法を簡易説明します．コードで利用されている config ファイルなどの詳細な説明は[README.md](https://github.com/ren8k/aws-bedrock-advanced-rag-baseline/blob/main/README.md)にて記載しておりますので，興味のある方はご参照ください．

### 前提

- バージニア北部リージョン（`us-east-1`），またはオレゴンリージョン（`us-west-2`）での実行を前提としている．（Pinecone を利用する場合は`us-east-1`である必要があります．）
- 適切な認証情報の設定・ロールの設定がなされている．（設定が面倒な場合，例えば Cloud9 上で実行しても良いです．）
- Bedrock のモデルアクセスの有効化が適切になされている．（最低限，Claude3 Haiku が利用できれば問題ございません．）

### Knowledge Bases for Amazon Bedrock の構築

Pinecone アカウントを作成後，ベクター DB のインデックスの作成を行います．“[Amazon Bedrock の Knowledge Base を Pinecone 無料枠で構築してみた](https://benjamin.co.jp/blog/technologies/bedrock-knowledgeaase-pinecone/)” などが参考になります．また，AWS 公式の “[Amazon Bedrock + Anthropic Claude 3 開発体験ワークショップ](https://catalog.us-east-1.prod.workshops.aws/workshops/7271111a-22bd-40e7-971a-817b0c083c67/ja-JP/rag/kb)” を参考に，OpenSearch Serverless を利用した Knowledge Bases を構築しても問題ございません．

- 簡単のため，データソースの S3 には以下の 2020 ~ 2023 年度の Amazon の株主向け年次報告書を格納し，これを Embedding しました．
  - [AMZN-2022-Shareholder-Letter.pdf](https://s2.q4cdn.com/299287126/files/doc_financials/2023/ar/2022-Shareholder-Letter.pdf)
  - [AMZN-2021-Shareholder-Letter.pdf](https://s2.q4cdn.com/299287126/files/doc_financials/2022/ar/2021-Shareholder-Letter.pdf)
  - [AMZN-2020-Shareholder-Letter.pdf](https://s2.q4cdn.com/299287126/files/doc_financials/2021/ar/Amazon-2020-Shareholder-Letter-and-1997-Shareholder-Letter.pdf)
  - [AMZN-2019-Shareholder-Letter.pdf](https://s2.q4cdn.com/299287126/files/doc_financials/2020/ar/2019-Shareholder-Letter.pdf)

### コードの clone と環境構築

以下を実行し，リポジトリを clone します．

```bash
git clone https://github.com/ren8k/aws-bedrock-advanced-rag-baseline.git
```

続いて，`boto3` をインストールします．

```bash
pip install boto3==1.34.101
```

### Advanced RAG の実行

`./src`ディレクトリに移動し，以下を実行します．引数`--kb-id`には，Knowledge Bases の ID を指定してください．また，引数`--relevance-eval`の有無で，関連度評価を行うかどうかを指定できます．

```bash
cd src
python advanced_rag.py --kb-id <Knowledge Bases の ID> --relevance-eval
```

## 実装時の工夫

Advanced RAG の Pre-Retrieval, Retrieval, Post-Retrieval, Augment and Generate の各ステップにおける実装の工夫について解説します．なお，本実装で利用しているプロンプトは，[AWS 公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)のものを参考にさせていただいております．

### step1. Pre-Retrieval: Claude3 を利用したクエリ拡張

クエリ拡張は，単一のクエリから，多様な観点で検索に適した複数のクエリを作成し，それらに対して検索を実行して検索結果をマージする手法です．これにより，クエリとソースドキュメントの表記・表現が異なる場合でも適切な回答を得ることを目的としています．特に，“[Forget RAG, the Future is RAG-Fusion](https://towardsdatascience.com/forget-rag-the-future-is-rag-fusion-1147298d8ad1)” [A. H. Raudaschl (2023)] で提案されている RAG-Fusion という手法では，LLM を利用してクエリ拡張を行っています．

本実装では，Claude3 Haiku に対して 拡張したクエリを **JSON 形式**で出力させるため，以下の工夫を行っています．なお，公式ブログと同様，3 つのクエリを生成するように Claude3 Haiku に指示しています．

1. プロンプトエンジニアリング（例・XML タグの利用）
2. システムプロンプトおよび Claude3 の応答の事前入力の工夫
3. JSON 形式で回答が生成されなかった場合に再度 Claude3 Haiku にリクエストを送信（リトライ）

以降，各工夫について詳細に解説します．

#### 1. プロンプトエンジニアリング（例・XML タグの利用）

プロンプト中では以下の Tips を取り入れております．

- 具体例を記載する(Few-shot Prompting)
- XML タグを利用した詳細な指示

以下にプロンプトを示します．簡単のために，実際に利用されているプロンプトテンプレート中の変数を一部展開した状態で記載しています．プロンプトでは，`<example></example>`タグ内に具体例を，`<format></format>`タグ内に出力フォーマットを記載しております．Claude3 では，指示とコンテンツ・例をタグを利用し分離して提示することで，より精度の高い回答を得ることができます．

:::note info
詳細は，Anthropic の公式ドキュメントの「[Use XML tags](https://docs.anthropic.com/en/docs/use-xml-tags)」および「[Use examples](https://docs.anthropic.com/en/docs/use-examples)」をご参照下さい．
:::

```yaml:config/prompt_template/query_expansion.yaml
template: |
  検索エンジンに入力するクエリを最適化し、様々な角度から検索を行うことで、より適切で幅広い検索結果が得られるようにします。
  具体的には、類義語や日本語と英語の表記揺れを考慮し、多角的な視点からクエリを生成します。

  以下の<question>タグ内にはユーザーの入力した質問文が入ります。
  この質問文に基づいて、3個の検索用クエリを生成してください。
  各クエリは30トークン以内とし、日本語と英語を適切に混ぜて使用することで、広範囲の文書が取得できるようにしてください。

  生成されたクエリは、<format>タグ内のフォーマットに従って出力してください。

  <example>
  question: Knowledge Bases for Amazon Bedrock ではどのベクトルデータベースを使えますか？
  query_1: Knowledge Bases for Amazon Bedrock vector databases engine DB
  query_2: Amazon Bedrock ナレッジベース ベクトルエンジン vector databases DB
  query_3: Amazon Bedrock RAG 検索拡張生成 埋め込みベクトル データベース エンジン
  </example>

  <format>
  JSON形式で、各キーには単一のクエリを格納する。
  </format>

  <question>
  {question}
  </question>
```

#### 2. システムプロンプトおよび Claude3 の応答の事前入力の工夫

Claude3 のプロンプト以外の引数部にて，以下の Tips を取り入れております．こちらは[AWS 公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)には記載はありませんでしたが，実装上の工夫として取り入れております．

- 引数 system（システムメッセージ） にて有効な JSON 形式での出力を指示
- 引数 messages にて`Assistant`ロールを定義し，応答の事前入力として`{`を指定

以下に Claude3 の引数を示します．システムメッセージの`Respond valid json format.`という部分と，応答の事前入力の`{ "role": "assistant", "content": [{ "type": "text", "text": "{" }] }`という部分が該当箇所です．

```yaml:config/llm/claude-3_query_expansion.yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond valid json format.
messages:
  [
    { "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] }, # {prompt}にはプロンプトが入る
    { "role": "assistant", "content": [{ "type": "text", "text": "{" }] },
  ]
stop_sequences: ["</output>"]
```

なお，上記の工夫で得られる回答は，以下のように，JSON の`{`の続きからなので，コード側で`{`を補完する必要があります．この工夫により，かなり高確率で JSON 形式の回答を得ることができるようになります．以下の例では，`"What is Amazon doing in the field of generative AI?"`という質問に対して 3 つのクエリを生成しています．

```

  "query_1": "Amazon generative AI models language GPT-3 Alexa",
  "query_2": "Amazon generative AI 生成モデル 自然言語処理 AI",
  "query_3": "Amazon generative AI 言語生成 人工知能 AI技術"
}
```

:::note info
詳細は，Anthropic の公式ドキュメントの「[System prompts](https://docs.anthropic.com/en/docs/system-prompts)」および「[Control output format (JSON mode)](https://docs.anthropic.com/en/docs/control-output-format)」をご参照下さい．
:::

#### 3. JSON 形式で回答が生成されなかった場合に再度 Claude3 Haiku にリクエストを送信（リトライ）

`try-except`文を利用して，JSON 形式で回答が生成されなかった場合には，再度 Claude3 Haiku にリクエストを送信するようにしています．以下にコードの該当箇所を示します．コードでは，`self.generate(body) `にて JSON 形式で生成しており，JSON 形式で回答が生成されなかった場合に，`Failed to decode JSON, retrying...`というメッセージを表示し，再度リクエストを送信するようにしています．

```python:src/llm.py
def expand_queries(self, llm_conf: LLMConfig, prompt_conf: PromptConfig) -> dict:
    llm_conf.format_message(prompt_conf.prompt_query_expansion) # プロンプトをClaude3の引数としてフォーマット
    body = json.dumps(llm_conf.llm_args)

    for attempt in range(prompt_conf.retries):
        try:
            if "claude-3" in self.model_id:
                generate_text = "{" + self.generate(body) # JSON形式で拡張したクエリを生成
            else:
                generate_text = self.generate(body)
            query_expanded = json.loads(generate_text)
            query_expanded["query_0"] = prompt_conf.query # オリジナルの質問を追加
            return query_expanded
        except json.JSONDecodeError:
            if attempt < prompt_conf.retries - 1:
                print(
                    f"Failed to decode JSON, retrying... (Attempt {attempt + 1}/{prompt_conf.retries})"
                )
                continue
            else:
                raise Exception("Failed to decode JSON after several retries.")
```

:::note info
ネットワーク障害や一時的なサービスの不具合などで API 実行に失敗した場合にも，リトライするようにしています．具体的には，以下のように，`boto3`の`botocore.config.Config`クラスの`retries`パラメータにて，リトライ回数（`max_attempts`）を 10 回に指定しています．

なお，本機能を利用することで，リトライ間隔は Exponential Backoff アルゴリズムに基づき指数関数的に増加します．詳細は[AWS Boto3 の公式ドキュメント](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html#guide-retries)をご参照下さい．

```python:src/llm.py(__init__)
from botocore.config import Config

retry_config = Config(
    region_name=region,
    retries={
        "max_attempts": 10,
        "mode": "standard",
    },
)
self.bedrock_runtime = boto3.client(
    "bedrock-runtime", config=retry_config, region_name=region
)
```

:::

### step2. Retrieval: Knowledge Bases でのベクトル検索の並列実行

ベクトル検索のレイテンシーを最小限に抑えるため，拡張した複数のクエリを利用して，非同期でベクトル検索を並列実行します．実装では，元のクエリと拡張した 3 つのクエリの計 4 つのクエリで独立に Knowledge Bases で検索を行っており，検索毎に 5 件の抜粋を取得しているので，計 20 件分の抜粋を Retrieve しています．

以下にコードの該当箇所を示します．各クエリの検索は`concurrent.futures.ThreadPoolExecutor`を利用して，`retrieve`メソッドをスレッドベースで並列実行しております．

```python:src/retriever.py
import concurrent.futures

@classmethod
def retrieve_parallel(cls, kb_id: str, region: str, queries: dict, max_workers: int = 10, no_of_results: int = 5) -> dict:
    retriever = cls(kb_id, region)
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers) as executor:
        futures = {
            executor.submit(retriever.retrieve, query, no_of_results): key
            for key, query in queries.items()
        }
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
            except Exception as e:
                results[key] = str(e)
            else:
                results[key] = result

    return results

def retrieve(self, query: str, no_of_results: int = 5) -> list:
    response = self.bedrock_agent_client.retrieve(
        retrievalQuery={"text": query},
        knowledgeBaseId=self.kb_id,
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": no_of_results,
                # "overrideSearchType": "HYBRID",  # optional
            }
        },
    )
    return response["retrievalResults"]
```

:::note info
`concurrent.futures` モジュールは複数の処理を並列実行するための機能を提供し，特に，`ThreadPoolExecutor` クラスはスレッドを利用した並列タスクを実行するためのクラスです．

以下にコードの補足説明を行います．

```python
with concurrent.futures.ThreadPoolExecutor(max_workers) as executor:
    futures = {
        executor.submit(retriever.retrieve, query, no_of_results): key
        for key, query in queries.items()
    }
```

- `concurrent.futures.ThreadPoolExecutor` を使用して，最大 `max_workers` 個のスレッドで並行処理を行います．（本実装では 10 並列）
- `executor.submit` を用いて，各クエリに対して`retrieve`を非同期に実行します．
- 辞書 `futures` には，`executor.submit` によって返される `Future` オブジェクトを key とし，対応するクエリのキー（`query_0`, `query_1`, ...）を value として格納しています．（以下参考）

```
{
    <Future at 0x721e69c3b430 state=running>: 'query_0',
    <Future at 0x721e69d86490 state=running>: 'query_1',
    ...
}
```

```python
for future in concurrent.futures.as_completed(futures):
    key = futures[future]
    try:
        result = future.result()
    except Exception as e:
        results[key] = str(e)
    else:
        results[key] = result

```

- `concurrent.futures.as_completed` を使用して，タスクの完了を待ち，完了したタスクから結果（ベクトル検索で取得した抜粋）を取得します．結果は `future.result()` で取得しています．
- 最終的に，以下のような辞書 `results`を得ます．

```
{
    "query_0": retrieve APIの結果 [抜粋1, 抜粋2, ...],
    "query_1": retrieve APIの結果 [抜粋1, 抜粋2, ...],
    ...
}
```

:::

:::note warn
執筆時点（2024/05/21）では，Knowledge Bases で OpenSearch Serverless を利用している場合のみ，ハイブリッド検索は可能です．
:::

### step3. Post-Retrieval: Claude3 Haiku による関連度評価の並列実行

検索結果の関連度評価では，LLM に検索結果とユーザーからの質問（クエリ）との関連性を評価させ，関連性が低い検索結果を除外する手法です．検索結果（抜粋）を圧縮することで，モデルの回答の精度を向上させることを目的としています．冗長な抜粋を基に LLM に回答を生成させる場合，重要な情報がコンテキストの中央に位置していると，回答精度が著しく低下してしまいます．詳細は論文 “[Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)” [Nelson F. Liu1 et al. (2023)]で報告されております．また，冗長な抜粋には，誤った回答を誘発するような内容が含まれている可能性も考えられます．

本実装では，Claude3 Haiku に対して全ての検索結果の抜粋に対してクエリとの関連度を効率的に評価させるため，以下の工夫を行っています．なお，公式ブログと同様，関連しているか否かの`True` or `False` で評価させており，`True` or `False` の文字列のみ回答するよう指示しております．

1. プロンプトエンジニアリング（Role・XML タグの利用）
2. システムプロンプトの工夫
3. LLM の関連度評価の並列実行

以降，各工夫について詳細に解説します．

#### 1. プロンプトエンジニアリング（Role・XML タグの利用）

プロンプト中では以下の Tips を取り入れております．

- Role の付与
- XML タグを利用した詳細な指示

以下にプロンプトを示します．簡単のために，実際に利用されているプロンプトテンプレート中の変数を一部展開した状態で記載しています．プロンプトの冒頭で，`質問とドキュメントの関連度を評価する専門家`という Role を与えるテクニック（ロールプロンプティング）を利用しております．Claude3 では，ロールプロンプティングにより，論理的で複雑なタスクでの精度向上やコミュニケーションスタイルの変更を促すことができます．また，XML タグを利用して，指示およびコンテンツを分離して指示しております．

```yaml:config/prompt_template/relevance_eval.yaml
template: |
  あなたは、ユーザーからの質問と検索で得られたドキュメントの関連度を評価する専門家です。
  <excerpt>タグ内は、検索により取得したドキュメントの抜粋です。

  <excerpt>{context}</excerpt>

  <question>タグ内は、ユーザーからの質問です。

  <question>{question}</question>

  このドキュメントの抜粋は、ユーザーの質問に回答するための正確な情報を含んでいるかを慎重に判断してください。
  正確な情報を含んでいる場合は 'True'、含んでいない場合は 'False' を返してください。

  TrueまたはFalseのみ回答すること。
```

:::note info
詳細は，Anthropic の公式ドキュメントの「[Give Claude a role](https://docs.anthropic.com/en/docs/give-claude-a-role)」および「[Use XML tags](https://docs.anthropic.com/en/docs/use-xml-tags)」をご参照下さい．
:::

#### 2. システムプロンプトの工夫

Claude3 のシステムプロンプト部で，`True` または `False`のみを回答するように指示しております．以下に Claude3 の引数を示します．

```yaml:config/llm/claude-3_relevance_eval.yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond only True or False.
messages:
    [{ "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] }] # {prompt}にはプロンプトが入る
stop_sequences: ["</output>"]
```

:::note info
詳細は，Anthropic の公式ドキュメントの「[System prompts](https://docs.anthropic.com/en/docs/system-prompts)」をご参照下さい．
:::

#### 3. LLM の関連度評価の並列実行

前述の「step2. Retrieval: Knowledge Bases でのベクトル検索の並列実行」と同様，非同期で Claude3 Haiku による評価を並列実行しております．実装では，計 20 件分の抜粋に対して，10 並列で関連度評価しております．

以下にコードの該当箇所を示します．関連度評価は`concurrent.futures.ThreadPoolExecutor`を利用して，内包関数`generate_single_message`を並列実行しております．`generate_single_message`には，引数として`プロンプト`と`プロンプトに埋め込んだ抜粋`のセットを渡しており，Claude3 Haiku が`True` と回答した場合のみ`抜粋`を返却するように実装することで，最終的に関連のある抜粋のみを抽出しております．

```python:src/llm.py
@classmethod
def eval_relevance_parallel(
    cls,
    region: str,
    llm_conf: LLMConfig,
    prompts_and_contexts: list,
    max_workers: int = 10,
) -> list:
    results = []

    def generate_single_message(
        llm: LLM, llm_conf: LLMConfig, prompt_and_context: dict
    ):
        llm_conf_tmp = copy.deepcopy(llm_conf)
        llm_conf_tmp.format_message(prompt_and_context["prompt"])
        body = json.dumps(llm_conf_tmp.llm_args)
        is_relevant = llm.generate_message(body)

        if is_relevant == "True":
            return prompt_and_context["context"]
        else:
            return None

    llm = cls(region, llm_conf.model_id)

    with ThreadPoolExecutor(max_workers) as executor:
        futures = {
            executor.submit(
                generate_single_message, llm, llm_conf, prompt_and_context
            ): prompt_and_context
            for prompt_and_context in prompts_and_contexts
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return results

def generate_message(self, body: str) -> None:
    try:
        response = self.bedrock_runtime.invoke_model(
            body=body, modelId=self.model_id
        )
        response_body = json.loads(response.get("body").read())
        generated_text = self._get_generated_text(response_body)
        return generated_text
    except ClientError as err:
        message = err.response["Error"]["Message"]
        logger.error("A client error occurred: %s", message)

def _get_generated_text(self, response_body: dict) -> Any:
    if "claude-3" in self.model_id:
        return response_body["content"][0]["text"]
    elif "command-r-plus" in self.model_id:
        return response_body["text"]
```

### step4. Augment and Generate: Claude3 Haiku による回答生成

step3 での関連度評価で抽出した抜粋を基に，Claude3 Haiku を利用してユーザーからの質問に対する回答を生成します．ここでのステップでの考え方は，Naive-RAG の考え方と同様です．本ステップには以下の工夫があります．

- プロンプトエンジニアリング（Role・CoT・XML タグの利用）
- システムプロンプトの工夫

以降，各工夫について詳細に解説します．

#### 1. プロンプトエンジニアリング（Role・CoT・XML タグの利用）

プロンプト中では以下の Tips を取り入れております．

- Role の付与
- CoT（Chain Of Thought）
- XML タグを利用した詳細な指示

以下にプロンプトを示します．簡単のために，実際に利用されているプロンプトテンプレート中の変数を一部展開した状態で記載しています．まず，プロンプトの冒頭で`親切で知識豊富なチャットアシスタント`という Role を与えております．また，`まず、質問に対して<excerpts>タグ内にある情報で答えられるかを考え、<related>true</related>、もしくは、<related>false</related>の形式で答えてください。`という部分では，CoT（Chain Of Thought）を利用して，思考の手順を示しつつ，思考の過程を出力するように指示しております．特に，Claude3 では，段階的な推論と最終的な応答を区別しやすくするために XML タグを利用することが有効です．

```yaml:config/prompt_template/rag.yaml
template: |
    あなたは親切で知識豊富なチャットアシスタントです。
    <excerpts>タグには、ユーザーが知りたい情報に関連する複数のドキュメントの抜粋が含まれています。

    <excerpts>{contexts}</excerpts>

    これらの情報をもとに、<question>タグ内のユーザーの質問に対する回答を提供してください。

    <question>{query}</question>

    まず、質問に対して<excerpts>タグ内にある情報で答えられるかを考え、<related>true</related>、もしくは、<related>false</related>の形式で答えてください。

    質問に答えるための情報がない場合は、「情報が不十分で回答できません」と答えてください。
    また、質問への回答は以下の点に留意してください:

    - <excerpts>タグの内容を参考にするが、回答に<excerpts>タグを含めないこと。
    - 簡潔に3つ以内のセンテンスで回答すること。
    - 日本語で回答すること。
    - 質問への回答は<answer></answer>タグに含めること。
```

:::note info
詳細は，Anthropic の公式ドキュメントの「[Give Claude a role](https://docs.anthropic.com/en/docs/give-claude-a-role)」，「[Let Claude think](https://docs.anthropic.com/en/docs/let-claude-think)」および「[Use XML tags](https://docs.anthropic.com/en/docs/use-xml-tags)」をご参照下さい．
:::

:::note info
例えば，`"What is Amazon doing in the field of generative AI?"`のようなクエリを入力とした場合，最終的に生成される回答（例）は以下のようになります．

```
<related>true</related>

<answer>
Amazonは、大規模言語モデル(LLM)とジェネレーティブAIに大きく投資しています。Amazonは自社のLLMを開発しており、それがあらゆる顧客体験を変革し改善すると考えています。また、AWSを通じてこの技術を民主化し、企業がジェネレーティブAIを活用できるようにしています。さらに、開発者の生産性を向上させるアプリケーションであるCodeWhispererなどを提供しています。
</answer>
```

プロンプトで指示している通り，回答の冒頭で，検索した結果とクエリの関連性があることを`<related></related>`内で回答し，その後，`<answer>`タグ内で最終的な回答を記述しています．
:::

#### 2. システムプロンプトの工夫

Claude3 のシステムプロンプト部で，日本語で回答するように指示しております．以下に Claude3 の引数を示します．

```yaml:config/llm/claude-3_rag.yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond only the answer in Japanese.
messages:
    [{ "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] }]
stop_sequences: ["</output>"]
```

:::note info
詳細は，Anthropic の公式ドキュメントの「[System prompts](https://docs.anthropic.com/en/docs/system-prompts)」をご参照下さい．
:::

## まとめ

本記事では，Advanced RAG を実現する上でのプロンプトエンジニアリングや実装方法に関する Tips をご紹介しました．Advanced RAG の実装を行う際には，本記事および[AWS 公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)を参考に，是非工夫を取り入れてみてください．

## 仲間募集<!-- omit in toc -->

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

## ソリューション紹介<!-- omit in toc -->

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
