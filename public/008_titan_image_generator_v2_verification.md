---
title: Amazon Titan Image Generator v2の Deep Dive
tags:
  - AWS
  - bedrock
  - Python
  -
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

v2 が使えるようになった．

https://aws.amazon.com/jp/about-aws/whats-new/2024/08/titan-image-generator-v2-amazon-bedrock/

機能が沢山増えた．改めて何ができるのかを確認する．

https://aws.amazon.com/jp/blogs/news/amazon-titan-image-generator-v2-is-now-available-in-amazon-bedrock/

## 目次

- はじめに
- Amazon Titan Image Generator v2 とは
- Amazon Titan Image Generator v2 の機能
- 各機能の紹介
- プロンプトエンジニアリングについて
- まとめ

## Amazon Titan Image Generator v2 とは

- Amazon 謹製の画像生成 AI
- 多機能
- 生成したという印もついてる
- データセットも安全なものを利用している
- その他あれば

入力の言語は**英語のみ**対応しており，最大 512 文字まで入力が可能です．その他詳細な仕様については，公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html)に記載があります．

## Amazon Titan Image Generator v2 の機能一覧

| タスクタイプ | 機能                               | 説明                                           |
| ------------ | ---------------------------------- | ---------------------------------------------- |
| TEXT_IMAGE   | 画像生成                           | テキストプロンプトを使用して画像を生成します。 |
| TEXT_IMAGE   | 画像コンディショニング(Canny Edge) | Canny Edge 画像を生成します。                  |

---

| タスクタイプ              | 機能                               | 説明                                                                                                   |
| ------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `TEXT_IMAGE`              | 画像生成                           | テキストプロンプトを使用して画像を生成。                                                               |
| `TEXT_IMAGE`              | 画像コンディショニング(Canny Edge) | 入力条件画像のレイアウトと構図に従う画像も生成可能。                                                   |
| `INPAINTING`              | 画像修正                           | マスクの内側を周囲の背景に合わせて変更し、画像を修正。                                                 |
| `OUTPAINTING`             | 画像拡張                           | マスクで定義された領域をシームレスに拡張し、画像を修正。                                               |
| `IMAGE_VARIATION`         | バリエーション生成                 | 元の画像のバリエーションを生成して画像を修正。                                                         |
| `COLOR_GUIDED_GENERATION` | 色指定画像生成                     | テキストプロンプトと Hex カラーコードのリストを使用し、指定カラーパレットに従う画像を生成（V2 のみ）。 |
| `BACKGROUND_REMOVAL`      | 背景除去                           | 複数のオブジェクトを識別し背景を削除、透明な背景の画像を出力（V2 のみ）。                              |

## 機能解説

本節では，AWS SDK for Python (boto3) を使用し，Amazon Titan Image Generator v2 の各機能を紹介します．

説明のため，画像を生成して表示するヘルパー関数 `generate_image` を定義しておきます．

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

`imageGenerationConfig`は各機能で共通の推論パラメータであり，以下の設定が可能です．その他詳細な情報は公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-image.html)に記載があります．

- `numberOfImages`: 生成する画像の数
- `quality`: 生成される画像の品質 (standard or premium)
- `height`: 出力画像の高さ
- `width`: 出力画像の幅
- `cfgScale`: 生成画像に対するプロンプトの影響度合い（忠実度）
- `seed`: 再現性のために使用するシード値

ヘルパー関数の引数 `payload` には，各機能独自の設定 (dict) を指定します．例えば，画像生成の機能の場合，`invoke_model` の最終的な body は以下のように指定する必要があります．以降，具体的な設定項目も提示しつつ解説していきます．なお，本解説で利用した jupyter notebook はこちらにございます．★

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
[What's news](https://aws.amazon.com/about-aws/whats-new/2024/08/titan-image-generator-v2-amazon-bedrock/?nc1=h_ls) によると，生成画像の制御には ControlNet を利用しているようです．（憶測ですが，Amazon Titan Image Generator のアーキテクチャは Unet ベースなのかもしれません．）
:::

### 画像コンディショニング(Segmentation)

入力画像をセグメンテーションすることにより，入力画像内のオブジェクトや領域を特定したマスクを生成し，テキストプロンプトからマスクに従った画像を生成する機能です．なお，本機能で利用されるセグメンテーションアルゴリズムは非公開です．SoTA なセグメンテーションモデルの中でも，代表的なものとして[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) が挙げられます．

SAM2 は，Meta が公開したセグメンテーションのための基盤モデルであり，ゼロショットで画像・動画内の任意のオブジェクトや領域のセグメンテーションを行うことができます．モデルは[OSS として公開](https://github.com/facebookresearch/segment-anything-2)されており，Apache-2.0 ライセンスの下，利用が可能です．参考のため，SAM2 によるセグメンテーション結果の例を示します．

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

入力画像のセグメンテーション領域に対して，忠実に画像が生成されていることが確認できます．ここで，先程の画像コンディショニング(Canny Edge) と比較すると，犬の目線やバケツの模様，猫の右足などは，入力画像とは異なることがわかります．入力画像の細かな特徴を生成画像に反映したい場合は，Canny Edge の利用が適していると考えられます．

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

mask image には，2 値のマスク画像を指定することができ，0 値のピクセル (黒塗り部分) が編集対象の領域を示し，255 値のピクセル (白塗り部分) が編集対象外の領域を示します．

:::note
[DALL-E-3](https://platform.openai.com/docs/api-reference/images/createEdit#images-createedit-mask) や [Stable Diffusion XL Inpainting 0.1](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1) の場合，mask image は白塗り部分が編集対象の領域を示す点に注意が必要です．
:::

今回の検証では，[SAM2 (Segment Anything Model 2)](https://ai.meta.com/sam2/) を利用して，高精度の犬の mask image を生成しました．(SAM2 で得られるセグメンテーション結果の色を反転させています．)

以下のコードでは，入力画像と 犬の領域を黒で示した mask image， `"A black cat inside a red bucket, background is dim green nature"` というテキストプロンプトから画像を生成しています．

```python
with open("/app/sam2/notebooks/images/dogcat.png", "rb") as image_file:
    input_image = base64.b64encode(image_file.read()).decode("utf8")

with open("/app/sam2/notebooks/masks/dogcat/mask_1.png", "rb") as image_file:
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

実際に検証したノートブックも公開しているので，是非ご参照ください．★

また，以下の AWS ブログでのソリューションでも Amazon Titan Image Generator G1 による Inpaint が利用されていますが，その際，[rembg](https://github.com/danielgatis/rembg) という Python ライブラリを利用して，マスク画像を生成しているようです．バックエンドで利用されているモデルは[U2-Net](https://github.com/xuebinqin/U-2-Net) などが利用されているようです．
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
    seed=7,
)
```

> - マスクプロンプト: "A white cat"
> - ネガティブプロンプト: "deformed ears, bad quality, low res, noise"

| 入力画像                                                                                                                    | 生成画像                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ![dogcat.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/7905b8de-bbe7-7709-fc31-00dac19eec0c.png) | ![dogcat_remove_mask_prompt.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/b3fcdcae-5f5f-17b1-c966-a64c7cde98c7.png) |

mask prompt で指示した通り，入力画像中の猫のみが削除されていることが確認できます．

#### mask image を利用する場合

小さいオブジェクトだとうまくいくかも

猫と犬が走ってる画像（画像中で中くらいにうつってる）を生成する

---

### アウトペインティング(Default)

### アウトペインティング(Precise)

マスク外部の情報も与えると良いらしい．

### イメージバリエーション

### カラーパレットによる画像ガイダンス

### 背景の削除

### サブジェクトの一貫性

fine-tuning のことでは？

fine-tuning 用のデータセットの準備が難しかったため，今回は検証を行っておりません．データセットの構造とかは以下の公式ドキュメントや公式ブログが参考になりそうです．

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

また，モデルの推論パラメータ (`cfgScale` や `numberOfImages`など) を調整することも重要です．

## まとめ

summary

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
