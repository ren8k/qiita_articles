---
title: Amazon Titan Image Generator G1 v2 の全機能を徹底検証：機能解説と実践ガイド
tags:
  - Python
  - AWS
  - bedrock
  - 画像生成
  - 生成AI
private: true
updated_at: '2024-10-01T23:57:47+09:00'
id: 42d91f7893f38cb5b0f0
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．2024/08/06 に，Amazon Bedrock にて，画像生成 AI である [**Amazon Titan Image Generator v2** がバージニア北部リージョンとオレゴンリージョンで利用可能になりました．](https://aws.amazon.com/jp/about-aws/whats-new/2024/08/titan-image-generator-v2-amazon-bedrock/)

本モデルでは，Amazon Titan Image Generator v1 の全ての機能に加え，様々な新機能が利用できるようになり，**計 11 種類**の機能が利用できます．本稿では，Amazon Titan Image Generator v2 の全機能の feasibility や利用方法を確認することを目的とし，検証結果をまとめました．

https://aws.amazon.com/jp/blogs/news/amazon-titan-image-generator-v2-is-now-available-in-amazon-bedrock/

また，検証にあたり，Amazon Titan Image Generator v2 の全機能を利用できる簡易アプリケーションを streamlit で実装し，Github 上で公開しております．是非利用してみて下さい！

https://github.com/ren8k/aws-bedrock-titan-image-generator-app

![demo.gif](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/3f339578-13cc-f5a0-a6c2-758f8931d249.gif)

## Amazon Titan Image Generator v2 とは

Amazon が開発した画像生成 AI であり，Amazon Bedrock にて提供されているモデルです．Amazon Titan Image Generator v2 は，画像生成 AI として，以下の特徴を持っています．

- 機能が豊富であり，⾼品質な画像を⽣成可能
  - インペインティング/アウトペインティング，画像調整，背景除去,,,etc
- 生成画像には，[不可視のウォーターマーク](https://aws.amazon.com/jp/about-aws/whats-new/2024/04/watermark-detection-amazon-titan-image-generator-bedrock/)や [C2PA のコンテンツ認証情報](https://aws.amazon.com/jp/about-aws/whats-new/2024/09/content-credentials-amazon-titan-image-generator/)が含まれる
  - [ウォーターマーク検出 API](https://aws.amazon.com/jp/blogs/news/amazon-titan-image-generator-and-watermark-detection-api-are-now-available-in-amazon-bedrock/) や[Content Credentials Verify](https://contentcredentials.org/verify)で検出可能
- 責任ある AI の原則に基づいた設計
  - 学習データとしてオープンソースや独自のデータなど，安全なものを利用
  - 生成画像が著作権を侵害した際の請求に対して[補償](https://aws.amazon.com/jp/about-aws/whats-new/2023/12/aws-announces-more-model-choice-and-powerful-new-capabilities-in-amazon-bedrock-to-securely-build-and-scale-generative-ai-applications/)あり

執筆時点 (2024/09/24) では，入力の言語は**英語のみ**対応しており，最大 512 文字まで入力が可能です．その他詳細な仕様については，公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html)に記載があります．

## Amazon Titan Image Generator v2 の機能一覧

6 種類のタスクタイプがありますが，細かい機能は計 11 種類あります．

| タスクタイプ              | 機能                                 | 説明                                                                                |
| ------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------- |
| `TEXT_IMAGE`              | 画像生成                             | テキストプロンプトから画像を生成                                                    |
|                           | 画像コンディショニング(Canny Edge)   | 入力画像のエッジに従い、テキストプロンプトに基づいた画像を生成                      |
|                           | 画像コンディショニング(Segmentation) | 入力画像のセグメンテーションに従い、テキストプロンプトに基づいた画像を生成          |
| `INPAINTING`              | インペインティング(Default)          | 入力画像の指定した領域をテキストプロンプトに基づいて編集                            |
|                           | インペインティング(Removal)          | 入力画像の指定した領域を削除し、周囲の背景に合わせて補完                            |
| `OUTPAINTING`             | アウトペインティング(Default)        | 入力画像の指定した領域外をテキストプロンプトに基づいて拡張 (マスク内も一部変更)     |
|                           | アウトペインティング(Precise)        | 入力画像の指定した領域外をテキストプロンプトに基づいて拡張 (マスク内は変更されない) |
| `IMAGE_VARIATION`         | 画像バリエーション                   | 入力画像のバリエーションを生成                                                      |
| `COLOR_GUIDED_GENERATION` | カラーパレットによる画像ガイダンス   | 指定されたカラーパレットに従い、テキストプロンプトに基づいた画像を生成              |
| `BACKGROUND_REMOVAL`      | 背景の削除                           | 入力画像からオブジェクトを識別し、背景を透明化                                      |
| ---                       | サブジェクトの一貫性                 | fine-tuning により、特定のオブジェクトの特徴とその名称を関連付ける                  |

## 機能解説

本節では，AWS SDK for Python (boto3) を使用し，Amazon Titan Image Generator v2 の各機能を検証します．説明のため，画像を生成して表示するヘルパー関数 `generate_image` を定義しておきます．

```python:generate_image.py
import base64
import io
import json

import boto3
from PIL import Image


def generate_image(
    payload: dict,
    num_image: int = 1,
    cfg_scale: float = 10.0,
    seed: int = 42,
    model_id: str = "amazon.titan-image-generator-v2:0",
) -> None:

    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    body = json.dumps(
        {
            **payload,
            "imageGenerationConfig": {
                "numberOfImages": num_image,  # Range: 1 to 5
                "quality": "premium",  # Options: standard/premium
                "height": 1024,  # Supported height list above
                "width": 1024,  # Supported width list above
                "cfgScale": cfg_scale,  # Range: 1.0 (exclusive) to 10.0
                "seed": seed,  # Range: 0 to 214783647
            },
        }
    )

    response = client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())
    base64_image = response_body.get("images")[0]
    base64_bytes = base64_image.encode("ascii")
    image_bytes = base64.b64decode(base64_bytes)

    image = Image.open(io.BytesIO(image_bytes))
    image.show()
```

メソッド `invoke_model` の body 部の `imageGenerationConfig` は各機能で共通の推論パラメータであり，以下の設定が可能です．詳細な情報は公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-image.html)にも記載があります．

- `numberOfImages`: 生成する画像の数
- `quality`: 生成される画像の品質 (standard or premium)
- `height`: 出力画像の高さ
- `width`: 出力画像の幅
- `cfgScale`: 生成画像に対するプロンプトの影響度合い（忠実度）
- `seed`: 再現性のために使用するシード値

ヘルパー関数の引数 `payload` には，各機能独自の設定 (dict) を指定します．例えば，画像生成の機能の場合，`invoke_model` の最終的な body は以下のように指定する必要があります．以降，具体的な設定項目も提示しつつ解説していきます．なお，本解説で利用した jupyter notebook は Github にて公開しております．

```json
{
  "taskType": "TEXT_IMAGE",
  "textToImageParams": {
    "text": "string",
    "negativeText": "string"
  },
  "imageGenerationConfig": {
    "numberOfImages": "int",
    "height": "int",
    "width": "int",
    "cfgScale": "float",
    "seed": "int"
  }
}
```

https://github.com/ren8k/aws-bedrock-titan-image-generator-app/blob/main/notebook/verify_all_features_of_titan_image_generator_v2.ipynb

:::note

### 出力画像の解像度について

タスクタイプが `TEXT_IMAGE`，`COLOR_GUIDED_GENERATION` の場合，つまり，**text2img** のタスクの場合，1024x1024 や 1280x768 ，512×512 などの許容されている**特定のアスペクト比を指定することができます**．一方，タスクタイプが前述以外の場合，つまり，**img2img** のタスクの場合，**出力画像の解像度は入力画像の解像度と同一**になりますが，入力画像の幅と高さはそれぞれ **1408 pixel 以内**である必要がある点に注意が必要です．（本情報は公式ドキュメントには明示されておらず，実際に検証して確認しました．）

text2img のタスクで指定可能な解像度については[公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-image.html)をご参照下さい．
:::

### 画像生成

テキストプロンプトから，画像を生成する機能です．オプションとしてネガティブプロンプトを利用し，画像に含めたくない要素を指定可能です．なお，テキストプロンプト，ネガティブプロンプト共に 512 文字以下である必要があります．

以下のコードでは，`"A cute brown puppy and a white cat inside a red bucket"` というテキストプロンプトから画像を生成しています．

```python
generate_image(
    {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": "A cute brown puppy and a white cat inside a red bucket",  # Required
            "negativeText": "bad quality, low res, noise",  # Optional
        },
    }
)
```

> - テキストプロンプト: "A cute brown puppy and a white cat inside a red bucket"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 生成画像                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) |

### 画像コンディショニング(Canny Edge)

Canny 法により，入力画像からエッジ（オブジェクトの輪郭や境界線など）を検出し，テキストプロンプトからエッジに従った画像を生成する機能です．Canny 法とは，古典的なエッジ検出アルゴリズムであり，ノイズ除去，画像の輝度勾配の算出，非極大値の抑制，ヒステリシスを利用した閾値処理により，エッジを検出します．参考のため，Canny 法によるエッジ検出の例を示します．

| 入力画像                                                                                                                    | エッジ検出結果 (例)                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_edge.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e8db4541-3c0d-7c2a-f69b-696d7f3ec76d.png) |

<details><summary>（参考）Canny 法によるエッジ検出の実行コード</summary>

OpenCV には cv2.Canny() という関数が用意されており，これを利用することで簡単に Canny 法によるエッジ検出を行うことができます．

```python
import cv2
import matplotlib.pyplot as plt

def canny_edge_detection(image_path: str, low_threshold: int, high_threshold: int):
    """
    Canny法によるエッジ検出を行う関数
    :param image_path: 画像ファイルのパス
    :param low_threshold: 二重しきい値処理の低い方の閾値
    :param high_threshold: 二重しきい値処理の高い方の閾値
    :return: エッジ検出結果の画像
    """
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    edges = cv2.Canny(image, low_threshold, high_threshold)

    plt.figure(figsize=(8, 8))
    plt.subplot(121), plt.imshow(image, cmap='gray')
    plt.title('Original Image'), plt.xticks([]), plt.yticks([])
    plt.subplot(122), plt.imshow(edges, cmap='gray')
    plt.title('Edge Image'), plt.xticks([]), plt.yticks([])
    plt.show()

    return edges

canny_edge_detection('/path/to/img', low_threshold=100, high_threshold=200)
```

</details>

画像内の顕著なエッジが検出されていることを確認できます．なお，API 側でエッジ検出が行われるため，本機能を利用する際，エッジ検出した画像は不要です．

以下のコードでは，入力画像と`"A cute black puppy and a brown cat inside a blue bucket"` というテキストプロンプトから画像を生成しています．推論パラメータの `controlStrength` は，入力画像のレイアウトと構図にどの程度従わせるかを調整する設定値であり，デフォルト値は 0.7 です．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": "A cute black puppy and a brown cat inside a blue bucket",
            "conditionImage": input_image,
            "negativeText": "bad quality, low res, noise",  # Optional
            "controlMode": "CANNY_EDGE", # Optional: CANNY_EDGE | SEGMENTATION
            "controlStrength": 0.7 # Optional: weight given to the condition image. Default: 0.7
        },
    },
)
```

> - テキストプロンプト: "A cute black puppy and a brown cat inside a blue bucket"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_conditioning_canny.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/ed8285b9-ffc8-78ce-e2cd-3ceed75d8645.png) |

入力画像のエッジに対して忠実に，画像が生成されていることが確認できます．

:::note
[What's news](https://aws.amazon.com/about-aws/whats-new/2024/08/titan-image-generator-v2-amazon-bedrock/?nc1=h_ls) によると，生成画像の制御には ControlNet を利用しているようです．（憶測ですが，Amazon Titan Image Generator のモデルアーキテクチャは Unet ベースなのかもしれません．）
:::

### 画像コンディショニング(Segmentation)

入力画像をセグメンテーションすることにより，入力画像内のオブジェクトや領域を特定したマスクを生成し，テキストプロンプトからマスクに従った画像を生成する機能です．なお，本機能で利用されるセグメンテーションアルゴリズムは非公開です．SoTA なセグメンテーションモデルの中でも，代表的なものとして [SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) が挙げられます．

SAM2 は，Meta が公開したセグメンテーションのための基盤モデルであり，ゼロショットで画像・動画内の任意のオブジェクトや領域のセグメンテーションを行うことができます．モデルは [OSS として公開](https://github.com/facebookresearch/segment-anything-2)されており，Apache-2.0 ライセンスの下，利用が可能です．参考のため，SAM2 によるセグメンテーション結果の例を示します．

| 入力画像                                                                                                                    | セグメンテーション結果 (例)                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_segmentation_mask.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/6953b27c-93b7-ff20-8253-2524a67cc6b7.png) |

:::note
SAM2 を利用することで，以降紹介するインペインティングやアウトペインティング機能で利用するためのマスク画像を容易に作成することができます．
:::

画像内のオブジェクト（犬や猫，背景）を区別して検出できていることが確認できます．なお，API 側でセグメンテーションが行われるため，本機能を利用する際，セグメンテーション画像は不要です．

以下のコードでは，入力画像と`"A cute black puppy and a brown cat inside a blue bucket"` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": "A cute black puppy and a brown cat inside a blue bucket",
            "conditionImage": input_image,
            "negativeText": "bad quality, low res, noise",  # Optional
            "controlMode": "SEGMENTATION", # Optional: CANNY_EDGE | SEGMENTATION
            "controlStrength": 0.7 # Optional: weight given to the condition image. Default: 0.7
        },
    },
)
```

> - テキストプロンプト: "A cute black puppy and a brown cat inside a blue bucket"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_conditioning_segmentation.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/33c8c29a-75a7-2677-c904-8247a4e38de1.png) |

入力画像のセグメンテーション領域に対して，忠実に画像が生成されていることが確認できます．ここで，先程の画像コンディショニング(Canny Edge) と比較すると，犬の目線やバケツの模様，猫の右足などは，入力画像とは異なることがわかります．

:::note
入力画像の大まかな構図を生成画像に反映したい場合は Segmentation の利用が適しており，入力画像の細かな特徴を生成画像に反映したい場合は，Canny Edge の利用が適していると考えられます．
:::

### インペインティング(Default)

mask prompt，または mask image を利用することで，入力画像内の任意のオブジェクトをテキストプロンプトで指示した内容に置換 (編集) することができる機能です．なお，mask prompt と mask image は，どちらか一方を指定する必要があります．

#### mask prompt を利用する場合

mask prompt には，入力画像内の編集対象のオブジェクトを自然言語で指定することができます．ただし，編集対象のオブジェクトについて，正確かつ詳細に説明する必要があります．

以下のコードでは，入力画像と `"A brown puppy"` という mask prompt， `"A black cat inside a red bucket, background is dim green nature"` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "INPAINTING",
        "inPaintingParams": {
            "text": "A black cat inside a red bucket, background is dim green nature",
            "image": input_image,  # Required
            "maskPrompt": "A brown puppy",  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "deformed ears, bad quality, low res, noise",  # Optional
        },
    },
)
```

> - マスクプロンプト: "A brown puppy"
> - テキストプロンプト: "A black cat inside a red bucket, background is dim green nature"
> - ネガティブプロンプト: "deformed ears, bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_inpaint_mask_prompt.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/6b3dbe01-fddc-e119-7a7a-734efe776435.png) |

mask prompt で指示した通り，入力画像中の犬のみ猫に置換されていることが確認できます．

#### mask image を利用する場合

mask image として，2 値のマスク画像を利用することができ，0 値のピクセル (黒塗り部分) が編集対象の領域を示し，255 値のピクセル (白塗り部分) が編集対象外の領域を示します．

:::note
[DALL-E-2](https://platform.openai.com/docs/api-reference/images/createEdit#images-createedit-mask) や [Stable Diffusion XL Inpainting 0.1](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1) の場合，mask image は白塗り部分が編集対象の領域を示す点に注意が必要です．
:::

本検証では，[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) を利用して，高精度の犬の mask image を生成しました．(SAM2 で得られるセグメンテーション結果の色を反転させています．)

以下のコードでは，入力画像と 犬の領域を黒で示した mask image， `"A black cat inside a red bucket, background is dim green nature"` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

with open("/path/to/mask_img", "rb") as image_file:
    mask_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "INPAINTING",
        "inPaintingParams": {
            "text": "A black cat inside a red bucket, background is dim green nature",
            "image": input_image,  # Required
            "maskImage": mask_image,  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "deformed ears, deformed eyes, bad quality, low res, noise",  # Optional
        },
    },
)
```

> - テキストプロンプト: "A black cat inside a red bucket, background is dim green nature"
> - ネガティブプロンプト: "deformed ears, deformed eyes, bad quality, low res, noise"

| 入力画像                                                                                                                    | マスク画像                                                                                                                  | 生成画像                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8e76ae64-1d1b-5b9e-2b66-f384bd7431ea.png) | ![dogcat_inpaint_mask_image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/bf8722aa-fb6f-2bfb-2bc9-82274a717017.png) |

mask image で指示した通り，入力画像中の犬のみ猫に置換されていることが確認できます．先程の mask prompt の場合と比較すると，結果の質の差は少ないように見えます．

:::note

#### コラム: mask image の作成手段について

[SAM2 (Segment Anything Model 2)](https://github.com/facebookresearch/segment-anything-2) を利用すると，入力画像内の任意のオブジェクトを自動でセグメンテーション可能であり，以下のように，自動で検出されたオブジェクトの各マスク画像を容易に抽出することができます．各画像中の白い領域がセグメンテーション領域です．

![masks.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/53956972-55d9-95ff-a422-e1dcca884c82.png)

また，[Grounded-Segment-Anything](https://github.com/IDEA-Research/Grounded-Segment-Anything) という，テキストベースのオブジェクト検出モデルである [Grounding Dino](https://github.com/IDEA-Research/GroundingDINO) と [SAM](https://github.com/facebookresearch/segment-anything) を組み合わせたツールを利用することで，以下のように自然言語で指定のオブジェクトを自動で検出し，セグメンテーションすることが可能です．

| 検出結果                                                                                                                           | セグメンテーション結果                                                                                                                   | マスク画像                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat_detect.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/bb8003de-3b42-d20d-19f4-301a3e93c7bc.png) | ![dogcat_segmentation.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/0451f70c-f9f4-83e7-1116-0357a3377850.png) | ![dogcat_mask.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/41304650-af81-5a3c-d03a-fef6d8ec0896.png) |

実際に検証したノートブックも公開しているので，是非ご参照ください．

https://github.com/ren8k/aws-bedrock-titan-image-generator-app/blob/main/notebook/automatic_mask_generator_example.ipynb

https://github.com/ren8k/Grounded-Segment-Anything/blob/main/grounded_sam.ipynb

また，以下の AWS ブログでのソリューションでは， Amazon Titan Image Generator v1 による Inpaint が行われていますが，その際，[rembg](https://github.com/danielgatis/rembg) という Python ライブラリを利用して，マスク画像を生成しているようです．rembg のバックエンドのモデルとしては [U2-Net](https://github.com/xuebinqin/U-2-Net) などが利用されております．
:::

https://aws.amazon.com/jp/blogs/news/aws-summit-2024-retail-cpg-ec-genai-bedrock-demo-architecture/

### インペインティング(Removal)

mask prompt，または mask image を利用することで，入力画像内の任意のオブジェクトを除去することができる機能です．本機能を利用する際の推論パラメータは先程のインペインティングと同様ですが，**テキストプロンプトの指定を省略**する必要があります．

#### mask prompt を利用する場合

mask prompt には，入力画像内の除去対象のオブジェクトを自然言語で指定することができます．ただし，除去対象のオブジェクトについて，正確かつ詳細に説明する必要があります．

以下のコードでは，入力画像と `"A white cat"` という mask prompt から画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "INPAINTING",
        "inPaintingParams": {
            "image": input_image,  # Required
            "maskPrompt": "A white cat",  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
        },
    },
)
```

> - マスクプロンプト: "A white cat"
> - ネガティブプロンプト: "deformed ears, bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_remove_mask_prompt.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/b3fcdcae-5f5f-17b1-c966-a64c7cde98c7.png) |

mask prompt で指示した通り，入力画像中の猫のみ削除されていることが確認できます．

#### mask image を利用する場合

mask image として，2 値のマスク画像を利用することができ，0 値のピクセル (黒塗り部分) が削除対象の領域を示し，255 値のピクセル (白塗り部分) が削除対象外の領域を示します．

本検証では，[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) を利用して，高精度の猫の mask image を生成しました．(SAM2 で得られるセグメンテーション結果の色を反転させています．)

以下のコードでは，入力画像と 猫の領域を黒で示した mask image， `"A black cat inside a red bucket, background is dim green nature"` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

with open("/path/to/mask_img", "rb") as image_file:
    mask_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "INPAINTING",
        "inPaintingParams": {
            "image": input_image,  # Required
            "maskImage": mask_image,  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
        },
    },
)
```

> - ネガティブプロンプト: "deformed ears, deformed eyes, bad quality, low res, noise"

| 入力画像                                                                                                                    | マスク画像                                                                                                                  | 生成画像                                                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_2.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/cda30655-fd92-6004-0979-0a5fa4707dc9.png) | ![dogcat_remove_mask_image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1504c862-2e20-6f84-94d6-a9873f6d5ee3.png) |

mask image で指示した通り，入力画像中の猫のみ削除されていることが確認できます．先程の mask prompt の場合と比較すると，結果の質の差は少ないように見えます．

### アウトペインティング(Default)

mask prompt，または mask image を利用することで，入力画像内の任意のオブジェクトの背景を変更することが可能です．特に， **DEFAULT モード**では，背景の描画に伴い，マスク内のオブジェクトの一部が変更され，全体の画像が一貫性を持つように調整されます．

#### mask prompt を利用する場合

mask prompt には，入力画像内で保持するオブジェクトを自然言語で指定することができます．（つまり，mask prompt で指定した領域以外が編集されます．）ただし，保持対象のオブジェクトについて，正確かつ詳細に説明する必要があります．

以下のコードでは，入力画像と `"A cute brown puppy"` という mask prompt ，`"A dog riding in a small boat."` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "OUTPAINTING",
        "outPaintingParams": {
            "text": "A dog riding in a small boat.",
            "image": input_image,  # Required
            "maskPrompt": "A cute brown puppy",  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
            "outPaintingMode": "DEFAULT",  # One of "PRECISE" or "DEFAULT"
        },
    },
)
```

> - テキストプロンプト: "A dog riding in a small boat."
> - マスクプロンプト: "A cute brown puppy"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                                 |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_outpaint_default_mask_prompt.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c0d27be8-3d80-14a1-18b9-a05acc11f4e4.png) |

mask prompt で指定した領域以外が，prompt で指定した内容で編集されていることが確認できます．

#### mask image を利用する場合

mask image として，2 値のマスク画像を利用することができ，0 値のピクセル (黒塗り部分) が保持するオブジェクトの領域を示し，255 値のピクセル (白塗り部分) が編集対象の領域を示します．

本検証では，[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) を利用して，高精度の犬の mask image を生成しました．また，比較のため，[labelme](https://github.com/wkentaro/labelme) を利用して，矩形で犬の領域を示した mask image も作成しました．

以下のコードでは，入力画像と 犬の領域を黒で示した mask image， `"A dog riding in a small boat."` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

with open("/path/to/mask_img", "rb") as image_file:
    mask_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "OUTPAINTING",
        "outPaintingParams": {
            "text": "A dog riding in a small boat.",
            "image": input_image,  # Required
            "maskImage": mask_image,  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
            "outPaintingMode": "DEFAULT",  # One of "PRECISE" or "DEFAULT"
        },
    },
)
```

> - テキストプロンプト: "A dog riding in a small boat."
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | マスク画像                                                                                                                              | 生成画像                                                                                                                                                            |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8e76ae64-1d1b-5b9e-2b66-f384bd7431ea.png)             | ![dogcat_outpaint_default_mask_image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/4dcb2c9a-3867-acd2-2439-0a21a63515fb.png)             |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_dog_rectangle.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/cfce07c2-6003-f825-6afa-db2df6300b4d.png) | ![dogcat_outpaint_default_mask_image_rectangle_2.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/293bf576-5f83-c581-6710-cc027695fe7b.png) |

mask image で指定した領域以外が，prompt で指定した内容で編集されていることが確認できます．また，矩形の mask image を利用した場合，バケツの部分 (mask image で保持対象として指定した領域) が背景に合わせて編集されていることが確認できます．先程の mask prompt の場合と比較すると，結果の質の差は少ないように見えます．

:::note
[AWS ブログ](https://aws.amazon.com/jp/blogs/machine-learning/use-amazon-titan-models-for-image-generation-editing-and-searching/)によると，DEFAULT モードは，mask image の精度が低い場合 (mask image がオブジェクトを正確に指定できてない場合) に推奨され，mask image の精度が高い場合は，後述の PRECISE モードを利用することが推奨されています．

> “ If set as DEFAULT, pixels inside of the mask are allowed to be modified so that the reconstructed image will be consistent overall. This option is recommended if the maskImage provided doesn’t represent the object with pixel-level precision. If set as PRECISE, the modification of pixels inside of the mask is prevented. This option is recommended if using a maskPrompt or a maskImage that represents the object with pixel-level precision. ”

:::

### アウトペインティング(Precise)

mask prompt，または mask image を利用することで，入力画像内の任意のオブジェクトの背景を変更することが可能です．特に， **PRECISE モード**では，マスク内のオブジェクトが変更されることなく，オブジェクトがそのまま全体の画像が一貫性を持つように調整されます．本機能は，mask image が正確である場合に適しています．

#### mask prompt を利用する場合

mask prompt には，入力画像内で保持するオブジェクトを自然言語で指定することができます．（つまり，mask prompt で指定した領域以外が編集されます．）ただし，保持対象のオブジェクトについて，正確かつ詳細に説明する必要があります．

以下のコードでは，入力画像と `"A cute brown puppy"` という mask prompt ，`"A dog riding in a small boat."` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "OUTPAINTING",
        "outPaintingParams": {
            "text": "A dog riding in a small boat.",
            "image": input_image,  # Required
            "maskPrompt": "A cute brown puppy",  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
            "outPaintingMode": "PRECISE",  # One of "PRECISE" or "DEFAULT"
        },
    },
)
```

> - テキストプロンプト: "A dog riding in a small boat."
> - マスクプロンプト: "A cute brown puppy"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                                 |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_outpaint_precise_mask_prompt.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/3a959847-a487-435f-d664-561ff3d42b30.png) |

mask prompt で指定した領域以外が，prompt で指定した内容で編集されていることが確認できます．

#### mask image を利用する場合

mask image として，2 値のマスク画像を利用することができ，0 値のピクセル (黒塗り部分) が保持するオブジェクトの領域を示し，255 値のピクセル (白塗り部分) が編集対象の領域を示します．

本検証では，[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) を利用して，高精度の犬の mask image を生成しました．また，比較のため，[labelme](https://github.com/wkentaro/labelme) を利用して，矩形で犬の領域を示した mask image も作成しました．

以下のコードでは，入力画像と 犬の領域を黒で示した mask image， `"A dog riding in a small boat."` というテキストプロンプトから画像を生成しています．

```python
with open("/path/to/img", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

with open("/path/to/mask_img", "rb") as image_file:
    mask_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "OUTPAINTING",
        "outPaintingParams": {
            "text": "A dog riding in a small boat.",
            "image": input_image,  # Required
            "maskImage": mask_image,  # One of "maskImage" or "maskPrompt" is required
            "negativeText": "bad quality, low res, noise",  # Optional
            "outPaintingMode": "PRECISE",  # One of "PRECISE" or "DEFAULT"
        },
    },
)
```

> - テキストプロンプト: "A dog riding in a small boat."
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | マスク画像                                                                                                                              | 生成画像                                                                                                                                                          |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8e76ae64-1d1b-5b9e-2b66-f384bd7431ea.png)             | ![dogcat_outpaint_precise_mask_image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/41b3390f-0955-f868-7deb-a9d3dc1675a7.png)           |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![mask_dog_rectangle.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/cfce07c2-6003-f825-6afa-db2df6300b4d.png) | ![dogcat_outpaint_precise_mask_image_rectangle.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7fa0b2e5-ab9a-41b8-86dd-7387f7867849.png) |

mask image で指定した領域以外が，prompt で指定した内容で編集されていることが確認できます．また，mask image が矩形の場合，つまり，mask iamge がオブジェクトの輪郭を正確に示せていない場合，機能の仕様上，アウトペインティングの結果が不自然となってしまうことが確認できます．（矩形領域のみ一切編集がなされていないことも確認できます．）

:::note

入力画像と mask image を縮小し，1024x1024 などの大きな白いキャンバス上に貼り付けたものを利用することで，ズームアウト効果を出すことも可能です．例として，以下に示す入力画像，mask image と `"ocean"` というテキストプロンプトを利用して生成した画像を示します．

| 入力画像                                                                                                                            | マスク画像                                                                                                                                 | 生成画像                                                                                                                                                       |
| ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![resized_dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1b88fa03-6575-8d58-89f6-1b149b1f7fa4.png) | ![resized_mask_combined.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/596a5642-c89b-ad02-0db4-321717994ec5.png) | ![dogcat_outpaint_precise_mask_image_zoomin.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1de4b66c-7998-42e0-1741-ebefe5e97f82.png) |

> - テキストプロンプト: "ocean"
> - ネガティブプロンプト: "bad quality, low res, noise"

犬と猫が壮大な冒険に出発する様子が描かれています．
:::

### 画像バリエーション

入力画像から，入力画像と類似した画像のバリエーションを生成する機能です．オプションとしてテキストプロンプトを利用でき，入力画像の詳細な説明や，入力画像内で保持したい部分や変更する部分を指定することができます．

以下のコードでは，`"A smiling dog and cat inside a red bucket"` というテキストプロンプトを利用して画像を生成しています．ここで，推論パラメータの `images` はリストで与える必要があり，1~5 個の画像を含めることができる点に注意が必要です．また，`similarityStrength` は，入力画像とどの程度類似させるかを調整する設定値であり，デフォルト値は 0.7 です．

```python
with open("/path/to/img.png", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "IMAGE_VARIATION",
        "imageVariationParams": {
            "text": "A smiling dog and cat inside a red bucket", # Optional
            "images": [input_image],  # Required
            "negativeText": "bad quality, low res, noise",  # Optional
            "similarityStrength": 0.7,  # Range: 0.2 to 1.0
        },
    },
)
```

> - テキストプロンプト: "A smiling dog and cat inside a red bucket"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像 1                                                                                                                              | 生成画像 2                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_variation_1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8a309f9c-05dd-81e2-b87f-120ebb100169.png) | ![dogcat_variation_2.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/92ae23a7-0a0f-4a53-c3e4-00f50974b3d8.png) |

テキストプロンプトで指定した `"A smiling dog"` という内容が反映されており，入力画像と類似した画像が生成されていることを確認できます．

:::note warn
[AWS 公式のプロンプトエンジニアリングガイドブック](https://d2eo22ngex1n9g.cloudfront.net/Documentation/User+Guides/Titan/Amazon+Titan+Image+Generator+Prompt+Engineering+Guidelines.pdf)によると，本機能を利用する際，テキストプロンプトは入力画像を説明し，画像内で保持したい部分を全て詳細に指定する必要があると記載されていますが，こちらは，入力画像に非常に類似した画像を生成させたい場合に有効だと考えられます．

> “ The text prompt should describe the input image, and specify all the details that you want to preserve about the image ”

以下に示す通り，テキストプロンプトとして，`"A cute brown puppy and a white cat inside a red bucket"` という内容を指定して実験したところ，入力画像と非常に類似した画像を生成させることができました．

> - テキストプロンプト: "A cute brown puppy and a white cat inside a red bucket"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像 1                                                                                                                              | 生成画像 2                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_variation_3.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f1176d27-e4d5-36a1-51cf-dbbaf77e8f5f.png) | ![dogcat_variation_4.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7fc2bb36-ef9a-b100-0314-0b8ab38d0817.png) |

:::

:::note
ここで，画像コンディショニング (Canny, Segmentation) と本機能が類似していると感じたかもしれません．公式ドキュメントには言及がありませんが，本機能と画像コンディショニングとの使い分けとしては，例えば画像バリエーションで候補画像を複数生成し，その中から選んだ画像で追加で細かい修正を行いたい場合に画像コンディショニングを利用すると良いと考えております．
:::

### カラーパレットによる画像ガイダンス

テキストプロンプトと 16 進数のカラーコード (カラーパレット) のリストから，特定の色調や配色に従って画像を生成する機能です．オプションとして参照画像を入力することができ，画像の配置や構成を指定することができます．

以下のコードでは，オレンジ色と水色のカラーパレットと，`"A cute brown puppy and a white cat inside a blue bucket, an orange sunset in the evening"` というテキストプロンプト，参照画像を利用して画像を生成しています．ここで，推論パラメータの `colors` はリストで与える必要があり，1~10 の 16 進数のカラーコードを含めることができます．

```python
with open("/path/to/img.png", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "COLOR_GUIDED_GENERATION",
        "colorGuidedGenerationParams": {
            "text": "A cute brown puppy and a white cat inside a blue bucket, an orange sunset in the evening",
            "negativeText": "bad quality, low res, noise",  # Optional
            "referenceImage": input_image,  # Optional
            "colors": ["#FFA500", "#87CEEB"],  # list of color hex codes
        },
    },
)
```

> - テキストプロンプト: "A cute brown puppy and a white cat inside a blue bucket, an orange sunset in the evening"
> - ネガティブプロンプト: "bad quality, low res, noise"

| 入力画像                                                                                                                    | カラーパレット                                                                                                                   | 生成画像                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![color_codes.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8481ebc6-610b-1da9-a421-bde1656410a5.png) | ![dogcat_color_guidence.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a2ab208b-e5b2-a675-7e71-b2aa6708d893.png) |

カラーパレットとして指定した色が反映されており，入力画像と類似した画像が生成されていることを確認できます．

### 背景の削除

入力画像からオブジェクトを識別し，背景を削除する機能です．生成画像の背景は透明になります．本機能ではテキストプロンプトを利用しない点に注意が必要です．

以下のコードでは，入力画像から背景を除去した画像を生成しています．ここで，推論パラメータは `image` のみであり，全機能で共通の推論パラメータである `numberOfImages` や `seed` は利用できません．

```python
with open("/path/to/img.png", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

generate_image(
    {
        "taskType": "BACKGROUND_REMOVAL",
        "backgroundRemovalParams": {
            "image": input_image,
        },
    },
)
```

| 入力画像                                                                                                                    | 生成画像                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_background_removal.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/98ec2b81-c5b9-aabf-12f8-7e608d5a9c83.png) |

犬と猫以外の背景が全て透明となっていることが確認できます．一方，必ずしも希望するオブジェクト以外の背景を除去できるとは限らない (今回の例で言うと，赤いバケツは削除されている) ため，より高精度に背景を除去したい場合は，別のセグメンテーションモデルなどを利用する必要があるかもしれません．

### サブジェクトの一貫性

Bedrock の fine-tuning により，訓練データ内における特定のオブジェクトの特徴とその名称を関連付けることができる機能です．例えば，「ロン」という名前の犬の画像とその説明文をデータセットとして fine-tuning することで，以下のように「ロン」の特徴を持つ犬の画像を生成することができます．

![aws-blog-img.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/3b8d0d8f-aa84-6bde-a097-e4e5a3fdce94.jpeg)

> 上図は，以下の AWS ブログから引用しています．

https://aws.amazon.com/jp/blogs/news/amazon-titan-image-generator-v2-is-now-available-in-amazon-bedrock/

執筆時点 (2024/09/24) では，[公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-prepare.html)には Amazon Titan Image Generator v2 の fine-tuning に関する情報は記載されていませんが，基本的には v1 と同様で，以下のような画像と各画像のキャプションを記録した jsonl ファイルを S3 にアップロードすることで，fine-tuning が可能です．なお，画像も S3 にアップロードする必要があります．

```json
{"image-ref": "<S3_BUCKET_URL>/ron_01.jpg", "caption": "Ron the dog laying on a white dog bed"}
{"image-ref": "<S3_BUCKET_URL>/ron_02.jpg", "caption": "Ron the dog sitting on a tile floor"}
{"image-ref": "<S3_BUCKET_URL>/ron_03.jpg", "caption": "Ron the dog laying on a car seat"}
{"image-ref": "<S3_BUCKET_URL>/smila_01.jpg", "caption": "Smila the cat lying on a couch"}
{"image-ref": "<S3_BUCKET_URL>/smila_02.jpg", "caption": "Smila the cat sitting next to the window next to a statue cat"}
{"image-ref": "<S3_BUCKET_URL>/smila_03.jpg", "caption": "Smila the cat lying on a pet carrier"}
```

fine-tuning 用のデータセットの準備が難しかったため，今回は検証を行っておりませんが，fine-tuning 実施時には，以下の公式ドキュメントや公式ブログが参考になりそうです．

https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html#titanimage-finetuning

https://aws.amazon.com/jp/blogs/news/fine-tune-your-amazon-titan-image-generator-g1-model-using-amazon-bedrock-model-customization/

## プロンプトエンジニアリングについて

Amazon Titan Image Generator v2 を利用する際，一般的な LLM と同様，プロンプトエンジニアリングが重要です．プロンプトエンジニアリングには以下の推奨事項があります．詳細は，[公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html#titanimage-prompt)や[プロンプトエンジニアリングガイドブック](https://d2eo22ngex1n9g.cloudfront.net/Documentation/User+Guides/Titan/Amazon+Titan+Image+Generator+Prompt+Engineering+Guidelines.pdf)を参照下さい．

- **画像生成の際，プロンプトを主題から始める．**
  - 例: An image of a ...
- **詳細情報をプロンプトに含める．**
  - 例: 表現方法（油彩/水彩画など），色，照明，備考，形容詞，品質，スタイル（印象派，写実的など）
- **テキストを囲む場合，ダブルクオーテーション ("") を使用する．**
  - 例: An image of a boy holding a sign that says "success"
- **プロンプトの要素を論理的に順序付け，句読点を使用して関係性を示す．**
  - 例: An image of a cup of coffee from the side, steam rising, on a wooden table,...
- **プロンプトでは具体的な単語を使用し，必要に応じてネガティブプロンプトを使用する．**
  - ネガティブプロンプトには，画像に含めたくない要素を指定する（否定語は利用しない）
- **インペインティング・アウトペインティングの場合，マスク領域内部だけでなく，マスク領域外部（背景）との関連性を記述する．**
  - 例: A dog sitting on a bench next to a woman

また，モデルの推論パラメータ (`cfgScale` や `numberOfImages`，各機能固有のパラメータなど) を調整することも重要です．

## まとめ

本稿では，Amazon Titan Image Generator v2 の全 11 機能について詳細な検証を行い，コードの実行例と生成画像を示しました．主に，画像生成 (text2img)，インペインティング，アウトペインティング，画像バリエーション，カラーパレットによる画像ガイダンス，背景の削除というタスクタイプが存在し，その中でも複数の機能が利用可能であることを確認しました．

特に，インペインティングやアウトペインティングでは，mask prompt の利用が有効である点や，高精度な mask image が必要な場合，SAM2 などを利用することが有効である点を確認しました．

最後に，Amazon Titan Image Generator v2 のプロンプトエンジニアリングについても解説しました．重要な点として，詳細な説明の提供，論理的な順序付け，具体的な単語の使用などが挙げられます．

本稿が，Amazon Titan Image Generator v2 の各機能の理解と効果的な利用の一助となれば幸いです．

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

～データ活用基盤の段階的な拡張支援 (Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
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
