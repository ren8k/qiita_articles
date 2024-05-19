---
title: Amazon Bedrock で Advanced RAG を実装する上での Tips
tags:
  - Python
  - AWS
  - rag
  - bedrock
  - 生成AI
private: true
updated_at: "2024-05-18T18:11:57+09:00"
id: dcdb7f0c61fda384c478
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デザイン＆テクノロジーコンサルティング事業本部の@ren8k です。
2024/05/01 に，AWS から「[Amazon Kendra と Amazon Bedrock で構成した RAG システムに対する Advanced RAG 手法の精度寄与検証](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)」という先進的で素晴らしいブログが公開されました．

https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/

上記ブログの内容に感化され，2024/05/06 に，AWS SDK for Python (Boto3)を利用して，ブログで紹介されている Advanced RAG の再現実装を私の方で行いました．その際に，Advanced RAG を実現する上での実装方法や Claude3 を利用する際のプロンプトエンジニアリングで学べた点が多かったので，本ブログにまとめようと思います．なお，Advanced RAG の再現実装（Python）は[本リポジトリ](https://github.com/ren8k/aws-bedrock-advanced-rag-baseline)に公開していますので，興味のある方はご参照ください．

https://github.com/ren8k/aws-bedrock-advanced-rag-baseline

## TL;DR

以下の Tips について重点的に解説しております．

- XML タグ，Chain Of Thought（CoT）を利用したプロンプトエンジニアリングが有効
- Python の非同期による並列実行が有効

## 目次

- Advanced RAG について
  - アルゴリズム：
  - pre-retrieve, retrieve, post-retrieve の各ステップにおける工夫
- 構築したアーキテクチャ
- 実施手順
  - 前提条件
  - Knowledge Bases の作成（任意）
  - Advanced RAG の実行
- 実装の工夫・Tips
  - Pre-Retrieve での工夫
    - プロンプトエンジニアリング(JSON 形式での回答取得)
    - 複数回の実行
  - Retrieve での工夫
    - 並列実行
  - Post-Retrieve
    - プロンプトエンジニアリング(CoT，XML タグの利用)
    - 並列実行

## 構築したアーキテクチャ

## 実施手順

---

## 再現実装時の工夫

Advanced RAG の Pre-Retrieve, Retrieve, Post-Retrieve の各ステップにおける実装の工夫について解説します．なお，本実装で利用しているプロンプトは，[AWS 公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)のものを参考にさせていただいております．

### step1. Pre-Retrieve: Claude3 を利用したクエリ拡張

クエリ拡張は，単一のクエリから，多様な観点で検索に適した複数のクエリを作成し，それらに対して検索を実行して検索結果をマージする手法です．これにより，クエリとソースドキュメントの表記・表現が異なる場合でも適切な回答を得ることを目的としています．特に，[RAG-Fusion](https://towardsdatascience.com/forget-rag-the-future-is-rag-fusion-1147298d8ad1)という手法では，LLM を利用してクエリ拡張を行うことが提案されています．

本実装では，Claude3 Haiku に対して 拡張したクエリを **JSON 形式**で出力させるため，以下の工夫を行っています．なお，公式ブログと同様，3 つのクエリを生成するように Claude3 Haiku に指示しています．

1. Claude3 特有のプロンプトエンジニアリング
2. システムプロンプトおよび Claude3 の応答の事前入力の工夫
3. JSON 形式で回答が生成されなかった場合に再度 Claude3 Haiku にリクエストを送信（リトライ）

以降，各工夫について詳細に解説します．

#### 1. Claude3 特有のプロンプトエンジニアリング

プロンプト中では以下の Tips を取り入れております．

- 具体例を記載する(Few-shot Prompting)
- XML タグを利用した詳細な指示

以下にプロンプトを示します．簡単のために，実際に利用されているプロンプトテンプレート中の変数を展開した状態で記載しています．プロンプトでは，`<example>`タグ内に具体例を，`<format>`タグ内に出力フォーマットを記載しております．Claude3 では，指示とコンテンツ・例をタグを利用し分離して提示することで，より精度の高い回答を得ることができます．

:::note info
詳細は，Anthropic の公式ドキュメントの「[Use XML tags](https://docs.anthropic.com/en/docs/use-xml-tags)」および「[Use examples](https://docs.anthropic.com/en/docs/use-examples)」を参照下さい．
:::

```yaml:config/prompt_template/query_expansion.yaml
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

- 引数 system（システムメッセージ） にて，有効な JSON 形式での出力を指示
- 引数 messages にて，応答の事前入力として Assistant フィールドに`{`を指定

以下に Claude3 の引数を示します．システムメッセージの`Respond valid json format.`という部分と，応答の事前入力の`{ "role": "assistant", "content": [{ "type": "text", "text": "{" }] }`という部分が該当箇所です．

```yaml:config/llm/claude-3_query_expansion.yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond valid json format.
messages:
  [
    { "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] },
    { "role": "assistant", "content": [{ "type": "text", "text": "{" }] },
  ]
stop_sequences: ["</output>"]
```

なお，上記の工夫で得られる回答は，以下のように，JSON の`{`の続きからなので，コード側で`{`を補完する必要があります．この工夫により，かなり高確率で JSON 形式の回答を得ることができるようになります．

:::note info
詳細は，Anthropic の公式ドキュメントの「[Control output format (JSON mode)](https://docs.anthropic.com/en/docs/control-output-format)」を参照下さい．
:::

```

  "query_1": "Amazon generative AI models language GPT-3 Alexa",
  "query_2": "Amazon generative AI 生成モデル 自然言語処理 AI",
  "query_3": "Amazon generative AI 言語生成 人工知能 AI技術"
}
```

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
ネットワーク障害や一時的なサービスの不具合などで API 実行に失敗した場合にも，リトライするようにしています．具体的には，以下のように，`boto3`の`botocore.config.Config`クラスの`retries`パラメータにて，リトライ回数を指定しています．

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

### step2. Retrieve: Knowledge Bases でのベクトル検索の並列実行

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

<details><summary>コードの補足説明</summary>

:::note info
`concurrent.futures` モジュールは複数の処理を並列実行するための機能を提供し，特に，`ThreadPoolExecutor` クラスはスレッドを利用した並列タスクを実行するためのクラスです．

以下にコードの補足説明を行います．

- `with concurrent.futures.ThreadPoolExecutor(max_workers) as executor` ステートメントでは，`max_workers` で指定した数のスレッドを利用して並列処理を行います．
- 辞書 `futures` には，`executor.submit` によって返される `Future` オブジェクトをキーとし，対応するクエリのキー（`query_0`, `query_1`, ...）を値として格納しています．（以下参考）

```
{
    <Future at 0x721e69c3b430 state=running>: 'query_0',
    <Future at 0x721e69d86490 state=running>: 'query_1',
    ...
}
```

- 各スレッドは，`executor.submit` にて指定した関数を非同期に実行し，その結果（ベクトル検索で取得した抜粋）を `future.result()` で取得します．デフォルトでは 10 並列で実行しています．
- 最終的に，以下のような辞書 `results`を得ます．

```
{
    "query_0": retrieve APIの結果 [抜粋1, 抜粋2, ...],
    "query_1": retrieve APIの結果 [抜粋1, 抜粋2, ...],
    ...
}
```

:::

</details>

### step3. Post-Retrieve: Claude3 Haiku による関連度評価の並列実行

検索結果の関連度評価では，LLM に検索結果とユーザーからの質問（クエリ）との関連性を評価させ，関連性が低い検索結果を除外する手法です．検索結果（抜粋）を圧縮することで，モデルの回答の精度を向上させることを目的としています．冗長な抜粋を基に LLM に回答を生成させる場合，重要な情報がコンテキストの中央に位置していると，回答精度が著しく低下してしまいます．詳細は論文[Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)で報告されております．また，冗長な抜粋には，誤った回答を誘発するような内容が含まれている可能性も考えられます．

本実装では，Claude3 Haiku に対して全ての検索結果の抜粋に対してクエリとの関連度を効率的に評価させるため，以下の工夫を行っています．なお，公式ブログと同様，関連しているか否かの`True` or `False` で評価しております．

1. Claude3 特有のプロンプト，およびシステムプロンプトの工夫
2. 非同期での LLM の関連度評価の並列実行

以降，各工夫について詳細に解説します．

また，step2 と同様，非同期で Claude3 Haiku による評価を並列実行しております．以下にコードの該当箇所を示します．Claude3 は，`True` または `False` のバイナリスコアを返すようにプロンプトを工夫しており，`True` の場合は関連があると判断し，`False` の場合は関連がないと判断している．

```python
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
```

以下に利用している cofig ファイルを示す．

**`config/prompt_template/relevance_eval.yaml`**

```yaml
format_instructions: TrueまたはFalseのみ回答すること。
template: |
  あなたは、ユーザーからの質問と検索で得られたドキュメントの関連度を評価する専門家です。
  <excerpt>タグ内は、検索により取得したドキュメントの抜粋です。

  <excerpt>{context}</excerpt>

  <question>タグ内は、ユーザーからの質問です。

  <question>{question}</question>

  このドキュメントの抜粋は、ユーザーの質問に回答するための正確な情報を含んでいるかを慎重に判断してください。
  正確な情報を含んでいる場合は 'yes'、含んでいない場合は 'no' のバイナリスコアを返してください。

  {format_instructions}
```

<br>

**`config/llm/claude-3_relevance_eval.yaml`**

```yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond only true or false.
messages:
  [{ "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] }]
stop_sequences: ["</output>"]

stream: false
model_id: anthropic.claude-3-haiku-20240307-v1:0
```

</details>

### step4. Augment and Generate: Claude3 Haiku による回答生成

プロンプトエンジニアリングが使われている

- CoT
- XML タグ

一般的に，LLM に試行の過程をを吐き出させたほうが性能は向上する

---

---

---

## まとめ

## 仲間募集

NTT データ テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

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
