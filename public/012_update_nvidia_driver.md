---
title: NVIDIA Driver の更新方法
tags:
  - NVIDIA
  - nvidia-docker
  - Docker
  - CUDA
  - GPU
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---

## はじめに

株式会社 NTT データ テクノロジーコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

最近，ローカル LLM を Docker コンテナ上で実行する機会がありました．しかし，利用する GPU マシンの NVIDIA Driver が古く，Docker コンテナ内の CUDA のバージョンに対応しておらず，コンテナ内で GPU を利用できませんでした．

本稿では，NVIDIA Driver の更新方法について (自身の備忘も兼ねて) 紹介します．なお，Docker は

/home/renya/Develop/Infra-tips/docs/20250602/references.md

## 環境

```sh
$ lsb_release -a
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 22.04.5 LTS
Release:	22.04
Codename:	jammy
```

```sh
$ nvidia-smi
Mon Jun  2 11:08:52 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 545.23.08              Driver Version: 545.23.08    CUDA Version: 12.3     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA GeForce RTX 3090        On  | 00000000:01:00.0  On |                  N/A |
| 50%   36C    P8              36W / 350W |    752MiB / 24576MiB |     16%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
```

```sh
$ docker --version
Docker version 28.2.2, build e6534b4
```

## 手順

### NVIDIA Driver のアンインストール

NVIDIA Driver，cuda をアンインストールします．この際，NVIDIA Container Toolkit も削除される点にご留意下さい．（後続の手順で再インストールします．）

```sh
sudo apt-get --purge remove nvidia-*
sudo apt-get --purge remove cuda-*
```

### NVIDIA Driver のインストール

NVIDIA 提供の cuda-drivers パッケージをインストールすることで，最新の NVIDIA Driver を取得します．具体的には，NVIDIA 公式の [CUDA Toolkit ダウンロードページ](https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=Ubuntu&target_version=22.04&target_type=deb_local) に表示されるコマンドの最後の行 `sudo apt-get -y install cuda-toolkit-12-9` を `sudo apt-get -y install cuda-drivers` に変更するだけで，最新の NVIDIA Driver を自動でインストールできます．

<img width="550" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/aa4a0d3a-c0aa-4929-9b7c-58f712811923.png">

以下に，私が実行したコマンドを示します．なお，ダウンロードページの Target Platform には，Ubuntu 22.04，Installer Type として deb (local) を選択しています．

```sh
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/12.9.0/local_installers/cuda-repo-ubuntu2204-12-9-local_12.9.0-575.51.03-1_amd64.deb
sudo dpkg -i cuda-repo-ubuntu2204-12-9-local_12.9.0-575.51.03-1_amd64.deb
sudo cp /var/cuda-repo-ubuntu2204-12-9-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda-drivers
```

上記のインストール方法は，NVIDIA の SA の方のブログ “[NVIDIA Docker って今どうなってるの？ (20.09 版)](https://medium.com/nvidiajapan/nvidia-docker-%E3%81%A3%E3%81%A6%E4%BB%8A%E3%81%A9%E3%81%86%E3%81%AA%E3%81%A3%E3%81%A6%E3%82%8B%E3%81%AE-20-09-%E7%89%88-558fae883f44)” で紹介されております．以下の公式ドキュメントでも同様に，cuda-drivers パッケージ経由で NVIDIA Driver をインストールする方法を推奨しています．

- [NVIDIA Container Toolkit のインストールドキュメント](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [Driver Installation Guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/index.html#ubuntu)

:::note warn
[Driver Installation Guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/index.html#ubuntu) には若干異なるインストール手順が記載されていますが，自身の環境に合わせて変数を複数設定する必要があります．
:::

インストール後，再起動して下さい．

```sh
sudo reboot
```

再起動後，以下のコマンドで NVIDIA Driver が正しくインストールされていることを確認します．

```sh
nvidia-smi
```

以下に，私の環境で確認した結果を示します．最新の NVIDIA Driver (575.51.03) がインストールされていることが確認できます．

```sh
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 575.51.03              Driver Version: 575.51.03      CUDA Version: 12.9     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   42C    P8             36W /  350W |    1344MiB /  24576MiB |     23%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            2405      G   /usr/lib/xorg/Xorg                      480MiB |
+-----------------------------------------------------------------------------------------+
```

:::note info
NVIDIA Driver のバージョンが自動更新されないよう，以下のコマンドを実行しておくことをお勧めします．（以前に実行したことがあれば，再度実行する必要はありません．）以下を実行すると，APT パッケージの自動更新を無効化できます．

```sh
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

GUI 上で訊かれる質問で「No」を選択すると，自動更新を無効化できます．

`cat /etc/apt/apt.conf.d/20auto-upgrades` の実行結果が以下のようになっていれば，自動更新は無効化されています．

```sh
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
```

:::

### NVIDIA Container Toolkit のインストール

[NVIDIA 公式ののインストールドキュメント](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#with-apt-ubuntu-debian)を参考に，NVIDIA Container Toolkit をインストールします．

以下に，私が実行したコマンドを示します．

```sh
# Configure the production repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update the packages list from the repository
sudo apt-get update

# Install the NVIDIA Container Toolkit packages
sudo apt-get install -y nvidia-container-toolkit
```

### Docker コンテナ内で GPU が利用できることを確認

[NGC Catalog の PyTorch コンテナイメージ](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/pytorch)を利用し，コンテナ内で GPU が利用できることを確認します．以下のコマンドを実行して，PyTorch のコンテナを起動します．

```sh
docker run --gpus all -it --rm nvcr.io/nvidia/pytorch:25.05-py3
```

コンテナ内で `ipython` を実行し，以下のコマンドを実行することで，PyTorch が GPU を認識しているかを確認します．`torch.cuda.is_available()` が `True` を返す場合，GPU が利用可能であることを示しています．

```sh
root@b3095d447671:/workspace# ipython
Python 3.12.3 (main, Feb  4 2025, 14:48:35) [GCC 13.3.0]
Type 'copyright', 'credits' or 'license' for more information
IPython 9.2.0 -- An enhanced Interactive Python. Type '?' for help.
Tip: The `%timeit` magic has a `-o` flag, which returns the results, making it easy to plot. See `%timeit?`.

In [1]: import torch

In [2]: torch.cuda.is_available()
Out[2]: True
```

## まとめ

NVIDIA Driver の更新方法について，公式ドキュメントを参考にした手順を紹介しました．NVIDIA 提供の cuda-drivers パッケージをインストールすることで，最新の NVIDIA Driver を自動で取得できます．(`ubuntu-drivers devices` コマンドを実行し，利用可能なドライバーを確認した後，直接ドライバーをインストールする必要はありません．) ただし，NVIDIA Container Toolkit のインストールを忘れないように注意が必要です．

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
