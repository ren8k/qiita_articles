---
title: CodeCommit の代替として Gitlab on ECS を CDK で一撃で構築する
tags:
  - AWS
  - GitLab
  - CDK
  - ECS
  - EFS
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

初めて CDK を使ってみた．加えて，TypeScript での開発も初めて．入門記事です．

苦戦した部分も沢山あるので，備忘録として記事に残します．

ECS で EFS をマウントするケースで CDK 化する際の参考となれば幸いです！

なお，CDK の実装は以下のリポジトリに公開しております．

https://github.com/ren8k/aws-cdk-gitlab-on-ecs

## TL;DR

- CodeCommit の代替として，Gitlab のセルフホスティングを検討
- AWS CDK を利用した GitLab on ECS を一撃でデプロイする実装の解説
  - ECS から EFS へマウントする際の Tip
- Gitlab をコンテナホストする際の Tips を共有

## 背景

新規 AWS アカウント上で，[SageMaker AI Project Templates](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-projects-templates-sm.html) を利用する必要がありました．SageMaker AI Project Templates とは，SageMaker AI を利用した MLOps を迅速に実現するために，以下の AWS リソースを CloudFormation で一括構築することができるテンプレートです．

![mlops-architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c66a4c7e-c4f8-db14-996d-38e09ed36d5b.png)

> SageMaker AI Project Templates を利用することで，モデルの学習〜デプロイ〜モデル・データの品質モニタリングまでの一連のプロセスを自動化する MLOps アーキテクチャを構築することができます．なお，Training Pipeline 部は一部省略しています．

SageMaker AI Project Templates では，MLOps の CI/CD パイプライン用のリポジトリとして CodeCommit または 3rd party 製の Git リポジトリサービスが利用可能です．しかし，2024/7/25 以降，新規 AWS アカウントにおいて，[CodeCommit は利用不可能](https://aws.amazon.com/jp/blogs/devops/how-to-migrate-your-aws-codecommit-repository-to-another-git-provider/)なため，3rd party 製の Git リポジトリサービスを利用する必要がありました．

そこで，CodeCommit の代替として GitLab をセルフホスティングすることを検討しました．本検討の理由は以下です．

- セキュリティ要件により、インターネット上の Git リポジトリサービスの利用には制限がある
  - 一定の承認プロセスを経れば利用可能だが、社内手続きが複雑でかなり時間がかかる
- GitLab は，Issue 管理，Wiki などの機能が豊富である

ただし，利用する AWS サービスの選定や，アーキテクチャの検討，CDK での IaC 化を行う際に色々苦戦した部分が多かったので，本稿ではその解説や Tips の共有を行います．

:::note
筆者は Data Scientist であり，CDK に関しては初学者でしたので，余計に苦戦しました．
:::

## ソリューション（アーキテクチャ）

GitLab の運用に必要なインフラストラクチャの管理工数を最小限に抑えるため，ECS on Fargate + EFS の構成を採用しました．

![gitlab_architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/166eb897-c701-6690-1e21-4321679840a1.png)

本ソリューションの特徴は以下です．

- **メンテナンスの労力が少ないフルマネージドサービスを採用**
  - ECS Fargate, EFS を使用
    - ECS，EFS は共に Private Subnet に配置し，Public Subnet に配置した ALB を経由して外部からのアクセスを許可
    - GitLab リポジトリのデータ永続化のために EFS を利用
    - GitLab の root ユーザーのパスワードは AWS Secrets Manager に保存
- **コスト効率の良いアーキテクチャ設計**
  - NAT Gateway の代わりに NAT インスタンスを使用可能
- **既存の AWS リソースとの連携**
  - 既存の VPC 内で GitLab をホスト可能
  - 既存のドメインの使用が可能

:::note warn
X でご教示いただいたのですが，GitLab では，EFS やその他の [Cloud File System の利用を推奨していません](https://docs.gitlab.com/ee/administration/nfs.html#avoid-using-cloud-based-file-systems)．I/O レイテンシによるパフォーマンスの低下のためです．具体的には，Git による多数の小規模ファイルの逐次書き込みという処理特性が，クラウドベースのファイルシステムと相性が悪いためです．

本番運用の場合や，大規模な利用を想定する場合には，ECS on EC2 (+EBS) の利用や，EC2 への GitLab のインストールを検討した方が良いと考えられます．一方，個人用途や少人数での検証用途などであれば，本構成でも問題無いとも考えております．（実際 3~4 名で 1~2 ヶ月利用していますが，今の所問題は生じておりません．）
:::

## コード (各コンストラクタ) の解説

利用する AWS サービス毎に，以下のコンストラクタを用意しました．

- Network (VPC)
- Storage (EFS)
- Security (Secrets Manager, IAM Role)
- LoadBalancer (ALB, DNS)
- EFS Initialization (Lambda)
- Computing (ECS, Fargate)

以降，各コンストラクタの実装について解説します．

### Network (VPC)

### Storage (EFS)

### Security (Secrets Manager, IAM Role)

あと，ECS から EFS へのマウントに必要なポリシーもなかなか記載が見つからないので有益だと思われる

https://aws.amazon.com/jp/blogs/news/developers-guide-to-using-amazon-efs-with-amazon-ecs-and-aws-fargate-part-2/

https://github.com/aws/aws-cdk/issues/13442

うーん，やっぱ read write のポリシーを明示する必要があるっぽい

```
ResourceInitializationError: failed to invoke EFS utils commands to set up EFS volumes: stderr: b'mount.nfs4: access denied by server while mounting 127.0.0.1:/srv/gitlab/data' Traceback (most recent call last): File "/usr/sbin/supervisor_mount_efs", line 52, in <module> return_code = subprocess.check_call(["mount", "-t", "efs", "-o", opts, args.fs_id_with_path, args.dir_in_container], shell=False) File "/usr/lib64/python3.9/subprocess.py", line 373, in check_call raise CalledProcessError(retcode, cmd) subprocess.CalledProcessError: Command '['mount', '-t', 'efs', '-o', 'noresvport,tls,iam,awscredsuri=/v2/credentials/3f626a1f-4f38-4a0c-8a8a-d12e68b2995d', 'fs-0486fc40aef1fa1a5:/srv/gitlab/data', '/efs-vols/data']' returned non-zero exit status 32. During handling of the above exception, another exception occurred: Traceback (most recent call last): File "/usr/sbin/supervisor_mount_efs", line 56, in <module> "message": err.message, AttributeError: 'CalledProcessError' object has n: unsuccessful EFS utils comma
```

あと，ECS にログインするためのポリシーも付与している．
ECS へのログインはこのシェルでできますよ．

### LoadBalancer (ALB, DNS)

### EFS Initialization (Lambda)

### Computing (ECS, Fargate)

- FileSystem.connections を使用して ECS サービスからのインバウンドを許可するようにしましょう。

- ECS EXEC もできるようにしております

- ECS へのログイン
  - Session Manager プラグインのインストール
    - https://qiita.com/kooohei/items/190802d07655809bd1bd
    - https://dev.classmethod.jp/articles/202310-ecs-efs-01/
  - ECS Exec の有効化
    - https://dev.classmethod.jp/articles/tsnote-ecs-update-service-fails-with-invalidparameterexception-in-ecs-exec/
  - 以下を実行

```bash
CLUSTER_NAME=XXX
TASK_ID=arn:XXX
CONTAINER_NAME=XXX

aws ecs execute-command \
    --cluster $CLUSTER_NAME \
    --task  $TASK_ID\
    --container $CONTAINER_NAME \
    --interactive \
    --command "/bin/bash"
```

### (その他)Stack

dependencies を明示しなければ，スタック削除時にエラーが発生

Lambda と VPC の削除順序を制御できていない．
Lambda と VPC の削除が同時に行われているように見える．

## GitLab セルフホスティングの Tips

本節では，[Docker コンテナ上で GitLab をセルフホスト](https://docs.gitlab.com/ee/install/docker/installation.html)する際に詰まった点や，ポイントについて共有します．

### Gitlab の外部 URL (https) の設定

GitLab コンテナを ALB (リバースプロキシ) の背後に配置する場合，GitLab 内部の Nginx に対し，以下のように HTTPS を利用しないように設定する必要があります．以下の設定は，ECS タスクにおける環境変数 `GITLAB_OMNIBUS_CONFIG` にて指定しています．(CDK コードの該当箇所は下記に記載しています．)

- `nginx['listen_port'] = 80`
- `nginx['listen_https'] = false;`

これは，GitLab の `external_url` に `https://` を指定すると，GitLab の Listen Port が 443 となり，内部の Nginx が HTTPS 通信を行うようになるためです． 本ソリューションの構成では， ALB が SSL 通信を行うため，GitLab 側は SSL (HTTPS) 通信を行わず，HTTP を利用して ALB と通信する必要があります．そのため，外部 URL に `https://` を指定する場合は，内部の Nginx の Listen port の設定を明示的に 80 に設定する必要があります．

参考: https://stackoverflow.com/questions/51487180/

<details open><summary>CDK コードの該当箇所</summary>

```typescript
const container = taskDefinition.addContainer("GitlabContainer", {
  image: ecs.ContainerImage.fromRegistry(
    `gitlab/gitlab-ce:${props.gitlabImageTag}`
  ),
  portMappings: [{ containerPort: 80 }],
  secrets: {
    GITLAB_ROOT_PASSWORD: ecs.Secret.fromSecretsManager(
      props.gitlabSecret,
      "password"
    ),
    GITLAB_ROOT_EMAIL: ecs.Secret.fromSecretsManager(
      props.gitlabSecret,
      "email"
    ),
  },
  environment: {
    GITLAB_OMNIBUS_CONFIG: props.useHttps
      ? `external_url '${props.externalUrl}'; nginx['listen_port'] = 80; nginx['listen_https'] = false;`
      : `external_url '${props.externalUrl}'`,
  },
  logging: ecs.LogDrivers.awsLogs({ streamPrefix: "gitlab" }),
});
```

</details>

### EFS アクセスポイントでの git clone 権限エラーとその解決

GitLab コンテナは，起動時にコンテナ内に `/var/opt/gitlab`, `/var/log/gitlab`, `/etc/gitlab` ディレクトリを作成します．これらのディレクトリは，GitLab のアプリケーションデータ，ログ，設定ファイルを保存するためのディレクトリです．これらのディレクトリをローカルボリュームにマウントすることで，GitLab のデータを永続化することができます．

| ローカルパス          | コンテナパス      | 用途                         |
| --------------------- | ----------------- | ---------------------------- |
| `$GITLAB_HOME/data`   | `/var/opt/gitlab` | アプリケーションデータを保存 |
| `$GITLAB_HOME/logs`   | `/var/log/gitlab` | ログを保存                   |
| `$GITLAB_HOME/config` | `/etc/gitlab`     | GitLab の設定ファイルを保存  |

> [公式ドキュメント](https://docs.gitlab.com/ee/install/docker/installation.html#create-a-directory-for-the-volumes)では，`$GITLAB_HOME = /srv/gitlab` としています．

ソリューション開発当初，GitLab のデータ永続化のためのボリュームマウント先として，EFS アクセスポイントを利用することを検討しました．ここで，アクセスポイントとは，EFS 上の指定したディレクトリに対し，指定した POSIX ユーザー ID (UID) とグループ ID (GID) でマウントすることができる機能です．また，指定したディレクトリが存在しない場合，自動でディレクトリを作成することができます．

ECS と EFS アクセスポイントを組み合わせることで，指定したディレクトリを EFS 上に自動作成し， ECS タスクにマウントすることができます．当初は，POSIX UID と GID を 0:0 に設定し，root ユーザーとして EFS 上のディレクトリをマウントしていました．この理由は，GitLab コンテナは，初回起動時に root ユーザーで必要なファイルやディレクトリを作成する必要があるためです．

GitLab コンテナが正常に起動し，動作確認のためリポジトリを作成して `git clone` を実行すると，以下のエラーが発生しました．この原因は，`/var/opt/gitlab/git-data/repositories` 内の一部のファイルの所有者が git ユーザー (UID: 998) である必要があるためです．(本エラーに関する情報が少なく，原因究明に時間を要しました．)

```
fatal: unable to access 'https://gitlab.example.com/root/test-pj.git/':
Error while processing content unencoding: invalid stored block lengths
```

つまり，GitLab コンテナの起動には EFS アクセスポイントの POSIX UID と GID を 0:0 にする必要があり，その結果，マウント先のディレクトリ内の全てのファイルの所有者が root となっていたため，本事象が発生していました．

そこで，本ソリューションでは，EFS アクセスポイントを利用せず，Lambda から直接 EFS にマウントし，ディレクトリを作成後，ECS タスクにマウントするようにしています．CDK の実装では，CustomResource を利用して，Lambda の操作を行っております．

参考: https://gitlab.com/gitlab-org/charts/gitlab/-/issues/5546#note_2017038672

### ヘルスチェックパスについて

ALB のターゲットグループのヘルスチェックのために，[公式ドキュメント](https://docs.gitlab.com/ee/administration/monitoring/health_check.html)に記載されている GitLab のヘルスチェックのエンドポイント `/-/health` を利用すると，期待するレスポンスを得ることができませんでした．こちらの原因は不明ですが，暫定対処として，現在は，`/-/users/sign_in` に対してヘルスチェックを行うことで，サーバーの稼働状況を確認しています．

### コンテナ起動後の Gitlab の起動に時間がかかり、ヘルスチェックを開始するタイミングをずらす必要がある

Gitlab のヘルスチェックパスが誤っており、ALB 側のヘルスチェックにも失敗してしまっていたため

## 利用手順

### AWS CDK コマンドの場合

### AWS CloudShell の場合

## GitLab の初回サインイン方法

![gitlab_signin.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a960c7ed-c682-e29c-fea4-2287b2051081.png)

https://qiita.com/takoikakani/items/936faf23ee6bc286a270

https://zenn.dev/tech4anyone/articles/62f360ccea30ca

## まとめ

summary

## 謝辞

<!-- ## 仲間募集

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

</div></details> -->
