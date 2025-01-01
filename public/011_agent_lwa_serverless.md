---
title: workflow 型の Agent (LangGraph) を Lambda Web Adapter でサーバーレスでストリーミング実行する
tags:
  - AWS
  - bedrock
  - Lambda
  - LangGraph
  - React
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

## 目的

本検証の目的は，Python でのストリーミング処理 を AWS 上でサーバーレスで実現することです．ストリーミング処理として，LangGraph の [stream メソッド](https://langchain-ai.github.io/langgraph/concepts/streaming/)を利用します．LangGraph のストリーミング処理は，グラフの実行完了を待たずに，逐次的にノードの実行結果を返します．

AWS Lambda は，サーバーレスコンピューティングサービスとして代表的なサービスですが，執筆時点（2025/01/01）において，Lambda は Node.js のマネージドランタイムでのみレスポンスストリーミングをサポートしています．その他の言語でレスポンスストリーミングを実現する場合は，「カスタムランタイムの作成」か Lambda Web Adapter (LWA)の利用」が必要です．

https://docs.aws.amazon.com/ja_jp/lambda/latest/dg/configuration-response-streaming.html

そこで，本検証では，容易に実装可能な Lambda Web Adapter を利用することで，LangGraph (Python) のストリーミングレスポンスを取得可能かを確認します．

## Lambda Web Adapter とは

## 手順

### Docker ファイルの作成

### FastAPI でローカル実行

### ECR に Docker イメージを push

### Lambda の作成

## CDK 実装

## フロントエンドの実装

### Streamlit

### React

```javascript
import { useState } from "react";
import "./App.css";

// API設定
const API_CONFIG = {
  LAMBDA_URL:
    "https://XXXXXXXXXXXXXXXXXXXXXXXXXXXXX.lambda-url.ap-northeast-1.on.aws/",
  ENDPOINT: "api/stream_graph",
  get API_URL() {
    return `${this.LAMBDA_URL}${this.ENDPOINT}`;
  },
  HEADERS: {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  },
};

// カスタムフック: APIとの通信を管理
const useProductAnalysis = () => {
  const [copy, setCopy] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyzeProduct = async (productDetail) => {
    setIsLoading(true);
    setCopy("");
    setTargetAudience("");
    setError(null);

    try {
      const response = await fetch(API_CONFIG.API_URL, {
        method: "POST",
        headers: API_CONFIG.HEADERS,
        credentials: "omit",
        mode: "cors",
        body: JSON.stringify({ product_detail: productDetail }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      await processStream(response.body.getReader());
    } catch (error) {
      console.error("Error:", error);
      setError(error.message || "予期せぬエラーが発生しました");
    } finally {
      setIsLoading(false);
    }
  };

  // ストリーム処理
  const processStream = async (reader) => {
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          processBuffer(buffer);
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        lines.forEach((line) => processBuffer(line));
      }
    } catch (error) {
      console.error("Stream processing error:", error);
      throw error;
    }
  };

  // 個々のJSONデータを処理
  const processBuffer = (buffer) => {
    if (!buffer.trim()) return;

    try {
      const data = JSON.parse(buffer);
      if (data.copy) setCopy(data.copy);
      if (data.target_audience) setTargetAudience(data.target_audience);
    } catch (error) {
      console.error("JSON parsing error:", error);
    }
  };

  return {
    copy,
    targetAudience,
    isLoading,
    error,
    analyzeProduct,
  };
};

// 結果表示用コンポーネント
const ResultCard = ({ title, content, emoji, isTargetAudience }) => (
  <div className="result-card">
    <h2 className="result-title">
      {emoji} {title}
    </h2>
    <div
      className={
        isTargetAudience ? "target-audience-content" : "result-content"
      }
    >
      <p>{content}</p>
    </div>
  </div>
);

// メインコンポーネント
const App = () => {
  const [productDetail, setProductDetail] = useState("");
  const { copy, targetAudience, isLoading, error, analyzeProduct } =
    useProductAnalysis();

  const handleSubmit = (e) => {
    e.preventDefault();
    analyzeProduct(productDetail);
  };

  return (
    <div className="container">
      <div className="card">
        <h1 className="title">商品広告生成アプリ</h1>
        <h2 className="subtitle">商品詳細</h2>

        <form onSubmit={handleSubmit} className="form">
          <textarea
            value={productDetail}
            onChange={(e) => setProductDetail(e.target.value)}
            className="textarea"
            rows={4}
            placeholder="例: ラベンダーとベルガモットのやさしい香りが特徴の保湿クリームで、ヒアルロン酸とシアバターの配合により、乾燥肌に潤いを与えます。価格は50g入りで3,800円（税込）です。"
            required
          />
          <button type="submit" disabled={isLoading} className="button">
            {isLoading ? "実行中..." : "Agent 実行開始"}
          </button>
        </form>

        {error && <div className="error">{error}</div>}

        {copy && (
          <ResultCard title="生成された広告文" content={copy} emoji="📝" />
        )}

        {targetAudience && (
          <ResultCard
            title="ターゲット層分析"
            content={targetAudience}
            emoji="🎯"
            isTargetAudience={true}
          />
        )}
      </div>
    </div>
  );
};

export default App;
```

## まとめ

summary

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
